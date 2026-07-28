from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent_memory_vault.queue import FileQueue, transcript_sha256
from agent_memory_vault.redaction import detect_out_of_scope, redact
from agent_memory_vault.transcript import build_classifier_excerpt, parse_transcript


def write_transcript(path: Path) -> None:
    events = [
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "I prefer local-first tools."}],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "output": "18 passed in 0.2s",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Tests passed: 12."}],
            },
        },
    ]
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def test_parse_and_excerpt(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    write_transcript(path)
    messages = parse_transcript(path)
    assert [message.role for message in messages] == ["user", "tool", "assistant"]
    excerpt = build_classifier_excerpt(messages)
    assert "[USER_STATEMENT]" in excerpt
    assert "[ASSISTANT_RESULT]" in excerpt
    assert "[VERIFICATION_OUTPUT]" in excerpt


def test_redaction_detects_and_removes_secret() -> None:
    result = redact("api_key = sk-abcdefghijklmnopqrstuvwxyz123456")
    assert result.secret_detected
    assert "abcdefghijklmnopqrstuvwxyz" not in result.text
    assert "[REDACTED:" in result.text


def test_personal_sensitive_scope_is_blocked_but_project_finance_is_not() -> None:
    assert detect_out_of_scope("I have a medical diagnosis affecting my health.").blocked
    assert detect_out_of_scope("Implement the finance assistant database.").blocked is False


def test_queue_is_idempotent(tmp_path: Path) -> None:
    transcript = tmp_path / "rollout.jsonl"
    write_transcript(transcript)
    digest = transcript_sha256(transcript)
    queue = FileQueue(tmp_path / "state")
    first, created = queue.enqueue(
        session_id="session-1",
        transcript_path=transcript,
        transcript_hash=digest,
        cwd=tmp_path,
        project_slug="sample",
    )
    second, created_again = queue.enqueue(
        session_id="session-1",
        transcript_path=transcript,
        transcript_hash=digest,
        cwd=tmp_path,
        project_slug="sample",
    )
    assert created is True
    assert created_again is False
    assert first.id == second.id
    claimed = queue.claim()
    assert claimed and claimed.id == first.id
    queue.complete(claimed)
    assert queue.claim() is None


def test_queue_retry_backoff(tmp_path: Path) -> None:
    transcript = tmp_path / "rollout.jsonl"
    write_transcript(transcript)
    queue = FileQueue(tmp_path / "state")
    job, _ = queue.enqueue(
        session_id="session-1",
        transcript_path=transcript,
        transcript_hash=transcript_sha256(transcript),
        cwd=tmp_path,
        project_slug=None,
    )
    claimed = queue.claim()
    assert claimed
    assert queue.retry(claimed, "temporary", maximum_attempts=3)
    pending = queue.path_for("pending", job.id)
    payload = json.loads(pending.read_text(encoding="utf-8"))
    assert payload["attempts"] == 1
    assert datetime.fromisoformat(payload["next_attempt_at"]) > datetime.now(UTC)
