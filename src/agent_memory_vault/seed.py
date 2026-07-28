from __future__ import annotations

from pathlib import Path

from .config import Settings
from .vault import Vault


def initialize_vault(settings: Settings) -> list[Path]:
    vault = Vault(settings.vault_root)
    before = (
        {path for path in settings.vault_root.rglob("*")} if settings.vault_root.exists() else set()
    )
    vault.initialize()
    after = {path for path in settings.vault_root.rglob("*")}
    return sorted(path for path in after - before if path.is_file())
