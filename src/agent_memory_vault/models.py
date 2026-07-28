from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MemoryType = Literal["preference", "decision", "project-state", "runbook", "fact", "lesson"]
Eligibility = Literal["explicit-user-statement", "verified-project-outcome"]


class HookInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    transcript_path: Path | None = None
    cwd: Path
    hook_event_name: str
    reason: str | None = None
    source: str | None = None
    model: str | None = None


class QueueJob(BaseModel):
    id: str
    session_id: str
    transcript_path: Path
    transcript_sha256: str
    cwd: Path
    project_slug: str | None = None
    attempts: int = 0
    next_attempt_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_error: str | None = None


class CandidateMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: MemoryType
    scope: str
    content: str
    eligibility: Eligibility
    evidence_excerpt: str
    supersedes_id: str | None = None
    review_after: date

    @field_validator("content", "evidence_excerpt")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be empty")
        return normalized

    @field_validator("scope")
    @classmethod
    def valid_scope(cls, value: str) -> str:
        if value == "global" or value.startswith("project:"):
            return value
        raise ValueError("scope must be global or project:<slug>")


class ClassifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memories: list[CandidateMemory]


class MemoryRecord(BaseModel):
    id: str
    type: MemoryType
    status: Literal["active", "stale", "superseded", "archived"]
    scope: str
    source: dict[str, str]
    evidence: dict[str, str]
    created: date
    review_after: date
    priority: Literal["low", "medium", "high"] = "medium"
    supersedes: str | None = None
    superseded_by: str | None = None
    content: str
    path: Path | None = None

    @model_validator(mode="after")
    def project_scope_is_named(self) -> MemoryRecord:
        if self.scope != "global" and not self.scope.startswith("project:"):
            raise ValueError("invalid memory scope")
        return self
