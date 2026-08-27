from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings
from .paths import codex_home, xdg_config_home

MCP_SERVER_NAME = "agent_memory_vault"
MCPVAULT_PACKAGE = "@bitbonsai/mcpvault@0.12.4"
MCP_READ_ONLY_TOOLS = (
    "read_note",
    "read_multiple_notes",
    "search_notes",
    "get_frontmatter",
    "get_notes_info",
    "get_vault_stats",
    "list_directory",
    "list_all_tags",
    "wiki_link",
)


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = path.with_name(f"{path.name}.bak.{stamp}")
    shutil.copy2(path, destination)
    return destination


def _set_toml_value(text: str, section: str, key: str, value: str) -> str:
    lines = text.splitlines()
    header = f"[{section}]"
    start = next((index for index, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([header, f"{key} = {value}"])
        return "\n".join(lines) + "\n"

    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].strip().startswith("[")),
        len(lines),
    )
    for index in range(start + 1, end):
        stripped = lines[index].strip()
        if stripped.startswith(f"{key} ") or stripped.startswith(f"{key}="):
            indentation = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
            lines[index] = f"{indentation}{key} = {value}"
            return "\n".join(lines) + "\n"
    lines.insert(end, f"{key} = {value}")
    return "\n".join(lines) + "\n"


def _disable_native_memories(text: str) -> str:
    updated = _set_toml_value(text, "features", "memories", "false")
    updated = _set_toml_value(updated, "memories", "generate_memories", "false")
    return _set_toml_value(updated, "memories", "use_memories", "false")


def _configure_mcpvault(text: str, vault_root: Path) -> str:
    section = f"mcp_servers.{MCP_SERVER_NAME}"
    values = {
        "command": json.dumps("npx"),
        "args": json.dumps(["-y", MCPVAULT_PACKAGE, str(vault_root)]),
        "enabled": "true",
        "required": "false",
        "startup_timeout_sec": "30",
        "tool_timeout_sec": "60",
        "enabled_tools": json.dumps(list(MCP_READ_ONLY_TOOLS)),
        "default_tools_approval_mode": json.dumps("auto"),
    }
    updated = text
    for key, value in values.items():
        updated = _set_toml_value(updated, section, key, value)
    return updated


def _write_codex_config(config_path: Path, original: str, updated: str) -> Path | None:
    if updated == original:
        return None
    backup = _backup(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path.with_suffix(".tmp")
    temporary.write_text(updated, encoding="utf-8")
    os.replace(temporary, config_path)
    return backup


def disable_native_memories(config_path: Path) -> Path | None:
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    return _write_codex_config(config_path, text, _disable_native_memories(text))


def install_mcpvault(config_path: Path, vault_root: Path) -> Path | None:
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    return _write_codex_config(config_path, text, _configure_mcpvault(text, vault_root))


def configure_codex(config_path: Path, vault_root: Path) -> Path | None:
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    updated = _disable_native_memories(text)
    updated = _configure_mcpvault(updated, vault_root)
    return _write_codex_config(config_path, text, updated)


def install_hooks(hooks_path: Path, executable_directory: Path) -> Path | None:
    if hooks_path.exists():
        payload = json.loads(hooks_path.read_text(encoding="utf-8"))
    else:
        payload = {
            "description": "Global user hooks, including persistent Obsidian memory.",
            "hooks": {},
        }
    hooks = payload.setdefault("hooks", {})
    start_command = f"{executable_directory / 'memory-context'} --hook"
    end_command = f"{executable_directory / 'memory-hook'} session-end"
    compact_command = f"{executable_directory / 'memory-hook'} pre-compact"
    prompt_command = f"{executable_directory / 'memory-hook'} user-prompt-submit"
    managed = {
        "SessionStart": {
            "matcher": "startup|resume|clear|compact",
            "hooks": [
                {
                    "type": "command",
                    "command": start_command,
                    "statusMessage": "Loading persistent Obsidian memory",
                    "additionalContextLimit": 1200,
                }
            ],
        },
        "SessionEnd": {
            "hooks": [
                {
                    "type": "command",
                    "command": end_command,
                    "timeout": 3,
                }
            ],
        },
        "PreCompact": {
            "matcher": "manual|auto",
            "hooks": [
                {
                    "type": "command",
                    "command": compact_command,
                    "timeout": 3,
                }
            ],
        },
        "UserPromptSubmit": {
            "hooks": [
                {
                    "type": "command",
                    "command": prompt_command,
                    "statusMessage": "Retrieving relevant persistent memory",
                    "additionalContextLimit": 600,
                }
            ],
        },
    }
    changed = False
    for event, definition in managed.items():
        existing = hooks.setdefault(event, [])
        filtered = [
            group
            for group in existing
            if not any(
                "memory-context" in handler.get("command", "")
                or "memory-hook" in handler.get("command", "")
                for handler in group.get("hooks", [])
            )
        ]
        filtered.append(definition)
        if filtered != existing:
            hooks[event] = filtered
            changed = True
    if not changed and hooks_path.exists():
        return None
    backup = _backup(hooks_path)
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = hooks_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, hooks_path)
    return backup


def render_config(settings: Settings) -> str:
    def quoted(path: Path) -> str:
        return json.dumps(str(path))

    def path_list(paths: list[Path]) -> str:
        return "[" + ", ".join(quoted(path) for path in paths) + "]"

    backup = "[" + ", ".join(json.dumps(part) for part in settings.backup_command) + "]"
    return (
        f"vault_root = {quoted(settings.vault_root)}\n"
        f"state_root = {quoted(settings.state_root)}\n"
        f"allowed_project_roots = {path_list(settings.allowed_project_roots)}\n"
        f"allowed_non_project_roots = {path_list(settings.allowed_non_project_roots)}\n"
        f"denied_roots = {path_list(settings.denied_roots)}\n\n"
        f"global_token_budget = {settings.global_token_budget}\n"
        f"project_token_budget = {settings.project_token_budget}\n"
        f"handoff_token_budget = {settings.handoff_token_budget}\n"
        f"prompt_token_budget = {settings.prompt_token_budget}\n"
        f"max_context_files = {settings.max_context_files}\n\n"
        f"max_prompt_context_files = {settings.max_prompt_context_files}\n"
        f"handoff_ttl_days = {settings.handoff_ttl_days}\n\n"
        f"classifier_model = {json.dumps(settings.classifier_model)}\n"
        f"classifier_base_url = {json.dumps(settings.classifier_base_url)}\n"
        f"classifier_api_key_env = {json.dumps(settings.classifier_api_key_env)}\n"
        f"classifier_max_tokens = {settings.classifier_max_tokens}\n"
        f"monthly_budget_usd = {settings.monthly_budget_usd}\n"
        f"input_cost_per_million = {settings.input_cost_per_million}\n"
        f"output_cost_per_million = {settings.output_cost_per_million}\n\n"
        f"worker_poll_seconds = {settings.worker_poll_seconds}\n"
        f"max_attempts = {settings.max_attempts}\n"
        f"backup_command = {backup}\n"
    )


def install_app_config(config_path: Path, settings: Settings) -> Path | None:
    rendered = render_config(settings)
    if config_path.exists() and config_path.read_text(encoding="utf-8") == rendered:
        return None
    backup = _backup(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path.with_suffix(".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, config_path)
    return backup


def install_user_files(settings: Settings, executable_directory: Path) -> dict[str, object]:
    config_dir = xdg_config_home() / "agent-memory-vault"
    app_config = config_dir / "config.toml"
    environment = config_dir / "agent-memory-vault.env"
    codex_config = codex_home() / "config.toml"
    hooks_path = codex_home() / "hooks.json"
    unit_path = xdg_config_home() / "systemd/user/agent-memory-vault.service"
    curator_unit_path = xdg_config_home() / "systemd/user/agent-memory-vault-curator.service"
    curator_timer_path = xdg_config_home() / "systemd/user/agent-memory-vault-curator.timer"

    config_dir.mkdir(parents=True, exist_ok=True)
    app_config_backup = install_app_config(app_config, settings)
    if not environment.exists():
        environment.write_text(
            "# Keep this file mode 600 and outside Git.\nDEEPSEEK_API_KEY=\n",
            encoding="utf-8",
        )
        environment.chmod(0o600)

    codex_backup = configure_codex(codex_config, settings.vault_root)
    hooks_backup = install_hooks(hooks_path, executable_directory)
    unit = (
        "[Unit]\n"
        "Description=Agent Memory Vault worker\n"
        "After=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={executable_directory / 'memory-worker'} --watch\n"
        f"EnvironmentFile=-{environment}\n"
        "Restart=on-failure\n"
        "RestartSec=15\n"
        "NoNewPrivileges=true\n"
        "PrivateTmp=true\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    if not unit_path.exists() or unit_path.read_text(encoding="utf-8") != unit:
        _backup(unit_path)
        unit_path.write_text(unit, encoding="utf-8")

    curator_unit = (
        "[Unit]\n"
        "Description=Agent Memory Vault proposal-only curator\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={executable_directory / 'memory-vault'} curate --write-report\n"
        f"EnvironmentFile=-{environment}\n"
        "NoNewPrivileges=true\n"
        "PrivateTmp=true\n"
    )
    curator_timer = (
        "[Unit]\n"
        "Description=Daily Agent Memory Vault curator\n\n"
        "[Timer]\n"
        "OnCalendar=daily\n"
        "Persistent=true\n"
        "RandomizedDelaySec=15m\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )
    for path, content in ((curator_unit_path, curator_unit), (curator_timer_path, curator_timer)):
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            _backup(path)
            path.write_text(content, encoding="utf-8")

    return {
        "app_config": str(app_config),
        "app_config_backup": str(app_config_backup or ""),
        "environment": str(environment),
        "codex_config_backup": str(codex_backup or ""),
        "mcp_server": MCP_SERVER_NAME,
        "mcp_package": MCPVAULT_PACKAGE,
        "mcp_enabled_tools": list(MCP_READ_ONLY_TOOLS),
        "hooks_backup": str(hooks_backup or ""),
        "hooks": str(hooks_path),
        "systemd_unit": str(unit_path),
        "curator_systemd_unit": str(curator_unit_path),
        "curator_systemd_timer": str(curator_timer_path),
    }
