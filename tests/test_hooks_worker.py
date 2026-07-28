from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from agent_memory_vault.classifier import Classification
from agent_memory_vault.config import Settings
from agent_memory_vault.hooks import session_end, session_start
from agent_memory_vault.models import (
    CandidateMemory,
    ClassifierOutput,
    HookInput,
)
from agent_memory_vault.queue import FileQueue
from agent_memory_vault.worker import MemoryWorker


def write_transcript(path: Path, text: str = "I prefer local tools.") -> None:
    event = {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")


def eligible_project(
    settings: Settings,
    codex_home_dir: Path,
) -> Path:
    project = settings.allowed_project_roots[0] / "alpha"
    (project / ".git").mkdir(parents=True)
    (codex_home_dir / "config.toml").write_text(
        f'[projects."{settings.allowed_project_roots[0]}"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    return project


class FakeClassifier:
    def classify(self, excerpt: str, project_slug: str | None) -> Classification:
        assert "I prefer local tools." in excerpt
        memory = CandidateMemory(
            type="preference",
            scope=f"project:{project_slug}",
            content="I prefer local tools.",
            eligibility="explicit-user-statement",
            evidence_excerpt="I prefer local tools.",
            review_after=date.today() + timedelta(days=365),
        )
        return Classification(ClassifierOutput(memories=[memory]), 100, 20)


def test_hooks_and_worker_pipeline(
    settings: Settings,
    codex_home_dir: Path,
    monkeypatch,
) -> None:
    project = eligible_project(settings, codex_home_dir)
    transcript = project / "rollout.jsonl"
    write_transcript(transcript)
    event = HookInput(
        session_id="session-1",
        transcript_path=transcript,
        cwd=project,
        hook_event_name="SessionEnd",
        reason="other",
    )
    created, _ = session_end(settings, event)
    assert created
    worker = MemoryWorker(settings, classifier=FakeClassifier())
    monkeypatch.setattr(worker, "_commit_and_backup", lambda session_id: None)
    result = worker.run_once()
    assert result.state == "completed"
    assert result.memories_written >= 1
    start = HookInput(
        session_id="session-2",
        transcript_path=transcript,
        cwd=project,
        hook_event_name="SessionStart",
        source="startup",
    )
    output = json.loads(session_start(settings, start))
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "I prefer local tools." in context
    assert FileQueue(settings.state_root).claim() is None


def test_secret_blocks_classifier(
    settings: Settings,
    codex_home_dir: Path,
    monkeypatch,
) -> None:
    project = eligible_project(settings, codex_home_dir)
    transcript = project / "rollout.jsonl"
    write_transcript(transcript, "api_key = sk-abcdefghijklmnopqrstuvwxyz123456")
    event = HookInput(
        session_id="secret-session",
        transcript_path=transcript,
        cwd=project,
        hook_event_name="SessionEnd",
        reason="other",
    )
    session_end(settings, event)

    class MustNotRun:
        def classify(self, excerpt: str, project_slug: str | None) -> Classification:
            raise AssertionError("classifier must not receive secret-bearing session")

    worker = MemoryWorker(settings, classifier=MustNotRun())
    monkeypatch.setattr(worker, "_commit_and_backup", lambda session_id: None)
    result = worker.run_once()
    assert result.state == "blocked"
    assert list((settings.vault_root / "80-audit").glob("*secret-blocked*.md"))
