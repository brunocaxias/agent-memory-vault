from __future__ import annotations

from pathlib import Path

import pytest

from agent_memory_vault.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        vault_root=tmp_path / "vault",
        state_root=tmp_path / "state",
        allowed_project_roots=[tmp_path / "projects"],
        allowed_non_project_roots=[tmp_path / "notes"],
        denied_roots=[tmp_path / "projects/denied"],
        worker_poll_seconds=1,
    ).resolved()


@pytest.fixture
def codex_home_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "codex"
    root.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(root))
    return root
