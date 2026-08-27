from __future__ import annotations

import re
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
    prompt: str | None = None
    trigger: Literal["manual", "auto"] | None = None
    turn_id: str | None = None


class QueueJob(BaseModel):
    id: str
    session_id: str
    transcript_path: Path
    transcript_sha256: str
    cwd: Path
    project_slug: str | None = None
    capture_event: Literal["session-end", "pre-compact"] = "session-end"
    attempts: int = 0
    next_attempt_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_error: str | None = None


class MemoryRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    target: str
    target_kind: Literal["memory", "entity", "concept"] = "entity"

    @field_validator("type")
    @classmethod
    def normalized_type(cls, value: str) -> str:
        normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", normalized):
            raise ValueError("relation type must be a short snake_case label")
        return normalized

    @field_validator("target")
    @classmethod
    def normalized_target(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized or len(normalized) > 160:
            raise ValueError("relation target must contain 1 to 160 characters")
        return normalized


class CandidateHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    completed: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def concise_summary(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized or len(normalized) > 600:
            raise ValueError("handoff summary must contain 1 to 600 characters")
        return normalized

    @field_validator(
        "completed",
        "changed_files",
        "verification",
        "blockers",
        "next_steps",
        "open_questions",
    )
    @classmethod
    def concise_items(cls, values: list[str]) -> list[str]:
        normalized = list(
            dict.fromkeys(" ".join(value.split()) for value in values if value.strip())
        )
        if len(normalized) > 12 or any(len(value) > 300 for value in normalized):
            raise ValueError("handoff lists support at most 12 concise items")
        return normalized


class SessionHandoff(CandidateHandoff):
    project_slug: str
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: date
    path: Path | None = None


class CandidateMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: MemoryType
    scope: str
    content: str
    eligibility: Eligibility
    evidence_excerpt: str
    supersedes_id: str | None = None
    review_after: date
    entities: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    effective_from: date | None = None
    effective_to: date | None = None
    relations: list[MemoryRelation] = Field(default_factory=list)

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

    @field_validator("entities", "concepts")
    @classmethod
    def normalized_labels(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in values:
            label = " ".join(raw.split())
            if not label or len(label) > 80:
                raise ValueError("labels must contain 1 to 80 characters")
            key = label.casefold()
            if key not in seen:
                seen.add(key)
                normalized.append(label)
        if len(normalized) > 12:
            raise ValueError("at most 12 labels are allowed")
        return normalized

    @model_validator(mode="after")
    def effective_window_is_ordered(self) -> CandidateMemory:
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValueError("effective_from cannot be after effective_to")
        return self


class ClassifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memories: list[CandidateMemory]
    handoff: CandidateHandoff | None = None


class MemoryRecord(BaseModel):
    id: str
    type: MemoryType
    status: Literal["active", "stale", "superseded", "archived"]
    scope: str
    source: dict[str, str]
    evidence: dict[str, str]
    created: date
    recorded_at: date | None = None
    review_after: date
    effective_from: date | None = None
    effective_to: date | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    supersedes: str | None = None
    superseded_by: str | None = None
    entities: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    relations: list[MemoryRelation] = Field(default_factory=list)
    content: str
    path: Path | None = None

    @model_validator(mode="after")
    def project_scope_is_named(self) -> MemoryRecord:
        if self.scope != "global" and not self.scope.startswith("project:"):
            raise ValueError("invalid memory scope")
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValueError("effective_from cannot be after effective_to")
        return self
