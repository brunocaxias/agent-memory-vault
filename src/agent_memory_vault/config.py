from __future__ import annotations

import shlex
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .paths import default_config_path, default_state_root


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vault_root: Path = Path("/mnt/Dump/Obsidian/Vaults/Agent-Memory")
    state_root: Path = Field(default_factory=default_state_root)
    allowed_project_roots: list[Path] = Field(
        default_factory=lambda: [Path("/mnt/Dump/Coding/Projects")]
    )
    allowed_non_project_roots: list[Path] = Field(default_factory=list)
    denied_roots: list[Path] = Field(default_factory=list)

    global_token_budget: int = 400
    project_token_budget: int = 800
    handoff_token_budget: int = 400
    prompt_token_budget: int = 450
    max_context_files: int = 4
    max_prompt_context_files: int = 3
    handoff_ttl_days: int = 7

    classifier_model: str = "deepseek-v4-flash"
    classifier_base_url: str = "https://api.deepseek.com"
    classifier_api_key_env: str = "DEEPSEEK_API_KEY"
    classifier_max_tokens: int = 1200
    monthly_budget_usd: float = 5.0
    input_cost_per_million: float = 0.14
    output_cost_per_million: float = 0.28

    worker_poll_seconds: int = 30
    max_attempts: int = 3
    backup_command: list[str] = Field(default_factory=list)

    @field_validator(
        "global_token_budget",
        "project_token_budget",
        "handoff_token_budget",
        "prompt_token_budget",
        "max_context_files",
        "max_prompt_context_files",
        "handoff_ttl_days",
        "classifier_max_tokens",
        "worker_poll_seconds",
        "max_attempts",
    )
    @classmethod
    def positive_integer(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator("monthly_budget_usd", "input_cost_per_million", "output_cost_per_million")
    @classmethod
    def nonnegative_number(cls, value: float) -> float:
        if value < 0:
            raise ValueError("must be non-negative")
        return value

    @field_validator("backup_command", mode="before")
    @classmethod
    def normalize_command(cls, value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return shlex.split(value)
        return list(value)

    def resolved(self) -> Settings:
        payload = self.model_dump()
        for field in (
            "vault_root",
            "state_root",
        ):
            payload[field] = Path(payload[field]).expanduser().resolve()
        for field in ("allowed_project_roots", "allowed_non_project_roots", "denied_roots"):
            payload[field] = [Path(item).expanduser().resolve() for item in payload[field]]
        return Settings.model_validate(payload)


def load_settings(path: Path | None = None) -> Settings:
    config_path = path or default_config_path()
    if not config_path.exists():
        return Settings().resolved()
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    return Settings.model_validate(data).resolved()
