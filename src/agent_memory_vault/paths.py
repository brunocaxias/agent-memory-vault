from __future__ import annotations

import os
from pathlib import Path


def xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def xdg_state_home() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))


def xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))


def default_config_path() -> Path:
    override = os.environ.get("AGENT_MEMORY_VAULT_CONFIG")
    return Path(override) if override else xdg_config_home() / "agent-memory-vault/config.toml"


def default_state_root() -> Path:
    override = os.environ.get("AGENT_MEMORY_VAULT_STATE")
    return Path(override) if override else xdg_state_home() / "agent-memory-vault"


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
