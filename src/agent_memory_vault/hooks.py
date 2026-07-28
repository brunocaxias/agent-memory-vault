from __future__ import annotations

import json
import sys
from typing import TextIO

from pydantic import ValidationError

from .audit import write_runtime_event
from .config import Settings
from .eligibility import resolve_capture_context
from .models import HookInput
from .queue import FileQueue, transcript_sha256
from .selector import build_context_pack


def read_hook_input(stream: TextIO) -> HookInput:
    try:
        return HookInput.model_validate_json(stream.read())
    except ValidationError as exc:
        raise ValueError(f"invalid Codex hook input: {exc}") from exc


def session_end(settings: Settings, event: HookInput) -> tuple[bool, str]:
    if event.hook_event_name != "SessionEnd":
        return False, "ignored non-SessionEnd event"
    context = resolve_capture_context(event.cwd, settings)
    if not context.eligible:
        write_runtime_event(
            settings.state_root,
            "capture_skipped",
            session_id=event.session_id,
            reason=context.reason,
        )
        return False, context.reason
    if event.transcript_path is None or not event.transcript_path.exists():
        write_runtime_event(
            settings.state_root,
            "source_unavailable",
            session_id=event.session_id,
        )
        return False, "transcript unavailable"
    digest = transcript_sha256(event.transcript_path)
    queue = FileQueue(settings.state_root)
    _, created = queue.enqueue(
        session_id=event.session_id,
        transcript_path=event.transcript_path.resolve(),
        transcript_hash=digest,
        cwd=event.cwd.resolve(),
        project_slug=context.project_slug,
    )
    write_runtime_event(
        settings.state_root,
        "capture_enqueued" if created else "capture_duplicate",
        session_id=event.session_id,
        job_created=created,
    )
    return created, "enqueued" if created else "duplicate"


def session_start(settings: Settings, event: HookInput) -> str:
    if event.hook_event_name != "SessionStart":
        return ""
    context = resolve_capture_context(event.cwd, settings)
    if not context.eligible:
        return ""
    pack = build_context_pack(settings, project_slug=context.project_slug)
    if not pack.text:
        return ""
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": pack.text,
            }
        }
    )


def run_session_end(settings: Settings, stream: TextIO = sys.stdin) -> int:
    try:
        event = read_hook_input(stream)
        session_end(settings, event)
    except Exception as exc:
        write_runtime_event(settings.state_root, "hook_failure", error=type(exc).__name__)
        print(f"agent-memory-vault SessionEnd failed: {exc}", file=sys.stderr)
        return 1
    return 0


def run_session_start(settings: Settings, stream: TextIO = sys.stdin) -> int:
    try:
        event = read_hook_input(stream)
        output = session_start(settings, event)
    except Exception as exc:
        write_runtime_event(settings.state_root, "hook_failure", error=type(exc).__name__)
        print(f"agent-memory-vault SessionStart failed: {exc}", file=sys.stderr)
        return 1
    if output:
        print(output)
    return 0
