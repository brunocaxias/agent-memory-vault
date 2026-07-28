from __future__ import annotations

from pathlib import Path

from agent_memory_vault.config import Settings, load_settings
from agent_memory_vault.eligibility import resolve_capture_context


def test_load_settings_from_toml(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        f'vault_root = "{tmp_path}/vault"\n'
        f'state_root = "{tmp_path}/state"\n'
        f'allowed_project_roots = ["{tmp_path}/projects"]\n'
        "global_token_budget = 900\n",
        encoding="utf-8",
    )
    loaded = load_settings(path)
    assert loaded.global_token_budget == 900
    assert loaded.vault_root == (tmp_path / "vault").resolve()


def test_trusted_project_is_eligible(
    settings: Settings,
    codex_home_dir: Path,
) -> None:
    project = settings.allowed_project_roots[0] / "sample"
    (project / ".git").mkdir(parents=True)
    (codex_home_dir / "config.toml").write_text(
        f'[projects."{settings.allowed_project_roots[0]}"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    context = resolve_capture_context(project, settings)
    assert context.eligible is True
    assert context.project_slug == "sample"


def test_project_optout_wins(
    settings: Settings,
    codex_home_dir: Path,
) -> None:
    project = settings.allowed_project_roots[0] / "sample"
    (project / ".git").mkdir(parents=True)
    (project / ".codex").mkdir()
    (project / ".codex/agent-memory.toml").write_text("enabled = false\n", encoding="utf-8")
    (codex_home_dir / "config.toml").write_text(
        f'[projects."{settings.allowed_project_roots[0]}"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    context = resolve_capture_context(project, settings)
    assert context.eligible is False
    assert "opted out" in context.reason


def test_allowlisted_non_project_is_eligible(settings: Settings) -> None:
    path = settings.allowed_non_project_roots[0] / "chat"
    path.mkdir(parents=True)
    assert resolve_capture_context(path, settings).eligible is True


def test_denied_root_wins(settings: Settings, codex_home_dir: Path) -> None:
    path = settings.denied_roots[0] / "secret"
    (path / ".git").mkdir(parents=True)
    (codex_home_dir / "config.toml").write_text(
        f'[projects."{settings.allowed_project_roots[0]}"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    context = resolve_capture_context(path, settings)
    assert context.eligible is False
    assert "denied" in context.reason
