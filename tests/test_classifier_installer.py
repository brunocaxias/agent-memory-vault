from __future__ import annotations

import json
import tomllib
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from agent_memory_vault.classifier import DeepSeekClassifier
from agent_memory_vault.config import Settings
from agent_memory_vault.installer import (
    MCP_READ_ONLY_TOOLS,
    MCP_SERVER_NAME,
    MCPVAULT_PACKAGE,
    configure_codex,
    disable_native_memories,
    install_app_config,
    install_hooks,
    install_mcpvault,
)


def test_classifier_validates_json(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    output = {
        "memories": [
            {
                "type": "preference",
                "scope": "global",
                "content": "Prefer local tools.",
                "eligibility": "explicit-user-statement",
                "evidence_excerpt": "Prefer local tools.",
                "supersedes_id": None,
                "review_after": (date.today() + timedelta(days=365)).isoformat(),
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["thinking"] == {"type": "disabled"}
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(output)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.deepseek.com",
    )
    result = DeepSeekClassifier(settings, client).classify("Prefer local tools.", None)
    assert result.output.memories[0].content == "Prefer local tools."
    assert result.input_tokens == 100


def test_disable_native_memories_preserves_other_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'model = "gpt-test"\n\n[features]\nmemories = true\nmulti_agent = true\n',
        encoding="utf-8",
    )
    disable_native_memories(path)
    text = path.read_text(encoding="utf-8")
    assert 'model = "gpt-test"' in text
    assert "multi_agent = true" in text
    assert "memories = false" in text
    assert "[memories]" in text
    assert "generate_memories = false" in text
    assert "use_memories = false" in text


def test_install_app_config_updates_root_with_backup_and_is_idempotent(
    settings: Settings, tmp_path: Path
) -> None:
    path = tmp_path / "config.toml"
    path.write_text('vault_root = "/old/vault"\n', encoding="utf-8")

    backup = install_app_config(path, settings)

    assert backup is not None
    assert backup.read_text(encoding="utf-8") == 'vault_root = "/old/vault"\n'
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    assert config["vault_root"] == str(settings.vault_root)
    assert install_app_config(path, settings) is None


def test_install_hooks_preserves_unrelated_hooks(tmp_path: Path) -> None:
    path = tmp_path / "hooks.json"
    path.write_text(
        json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]}}),
        encoding="utf-8",
    )
    install_hooks(path, Path("/opt/memory/bin"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["hooks"]["Stop"]
    assert payload["hooks"]["SessionStart"][0]["hooks"][0]["additionalContextLimit"] == 1200
    assert payload["hooks"]["SessionEnd"][0]["hooks"][0]["timeout"] == 3
    assert payload["hooks"]["PreCompact"][0]["hooks"][0]["command"].endswith("pre-compact")
    assert payload["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"].endswith(
        "user-prompt-submit"
    )


def test_install_mcpvault_is_pinned_read_only_and_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    vault_root = tmp_path / "vault"
    path.write_text(
        'model = "gpt-test"\n\n[mcp_servers.unrelated]\ncommand = "other-server"\n',
        encoding="utf-8",
    )

    assert install_mcpvault(path, vault_root) is not None
    first = path.read_text(encoding="utf-8")
    assert install_mcpvault(path, vault_root) is None
    assert path.read_text(encoding="utf-8") == first

    config = tomllib.loads(first)
    assert config["model"] == "gpt-test"
    assert config["mcp_servers"]["unrelated"]["command"] == "other-server"
    mcp = config["mcp_servers"][MCP_SERVER_NAME]
    assert mcp["command"] == "npx"
    assert mcp["args"] == ["-y", MCPVAULT_PACKAGE, str(vault_root)]
    assert mcp["enabled"] is True
    assert mcp["required"] is False
    assert mcp["enabled_tools"] == list(MCP_READ_ONLY_TOOLS)
    assert mcp["default_tools_approval_mode"] == "auto"
    assert not {
        "write_note",
        "patch_note",
        "delete_note",
        "move_note",
        "move_file",
        "update_frontmatter",
        "manage_tags",
    }.intersection(mcp["enabled_tools"])


def test_configure_codex_applies_memory_and_mcp_policy_with_one_backup(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('model = "gpt-test"\n', encoding="utf-8")

    backup = configure_codex(path, tmp_path / "vault")

    assert backup is not None
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    assert config["features"]["memories"] is False
    assert config["memories"]["generate_memories"] is False
    assert config["memories"]["use_memories"] is False
    assert config["mcp_servers"][MCP_SERVER_NAME]["enabled_tools"] == list(
        MCP_READ_ONLY_TOOLS
    )
