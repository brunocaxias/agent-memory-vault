from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def write_runtime_event(state_root: Path, event: str, **fields: Any) -> None:
    log_path = state_root / "events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    descriptor = os.open(log_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, line.encode())
    finally:
        os.close(descriptor)


def write_vault_audit(vault_root: Path, event: str, session_id: str, detail: str) -> Path:
    timestamp = datetime.now(UTC)
    safe_session = "".join(
        character for character in session_id if character.isalnum() or character in "-_"
    )
    path = (
        vault_root
        / "80-audit"
        / f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{event}-{safe_session[:24]}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "---\n"
        f"event: {event}\n"
        f"session_id: {safe_session}\n"
        f"created: {timestamp.date().isoformat()}\n"
        "---\n\n"
        f"{detail}\n"
    )
    temporary = path.with_suffix(".tmp")
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)
    return path
