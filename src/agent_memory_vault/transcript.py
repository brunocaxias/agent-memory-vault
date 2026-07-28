from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TranscriptError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptMessage:
    role: str
    text: str


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for item in content:
        if isinstance(item, str):
            chunks.append(item)
        elif isinstance(item, dict):
            for key in ("text", "input_text", "output_text"):
                value = item.get(key)
                if isinstance(value, str):
                    chunks.append(value)
                    break
    return "\n".join(chunks)


def _find_messages(value: Any) -> Iterable[TranscriptMessage]:
    if isinstance(value, list):
        for item in value:
            yield from _find_messages(item)
        return
    if not isinstance(value, dict):
        return

    role = value.get("role")
    content = value.get("content")
    if role in {"user", "assistant"} and content is not None:
        text = _text_from_content(content).strip()
        if text:
            yield TranscriptMessage(role, text)
            return

    item_type = value.get("type")
    if item_type in {"function_call_output", "custom_tool_call_output"}:
        output = value.get("output")
        text = _text_from_content(output).strip()
        if text:
            yield TranscriptMessage("tool", text)
            return

    payload = value.get("payload")
    if isinstance(payload, dict):
        yield from _find_messages(payload)
    item = value.get("item")
    if isinstance(item, dict):
        yield from _find_messages(item)


def parse_transcript(path: Path) -> list[TranscriptMessage]:
    if not path.exists():
        raise TranscriptError("transcript is unavailable")
    messages: list[TranscriptMessage] = []
    seen: set[tuple[str, str]] = set()
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise TranscriptError(f"invalid JSONL at line {line_number}") from exc
                for message in _find_messages(event):
                    key = (message.role, message.text)
                    if key not in seen:
                        seen.add(key)
                        messages.append(message)
    except OSError as exc:
        raise TranscriptError(f"could not read transcript: {exc}") from exc
    if not messages:
        raise TranscriptError("no supported user or assistant messages found")
    return messages


def build_classifier_excerpt(
    messages: list[TranscriptMessage],
    *,
    max_total_chars: int = 48_000,
    max_message_chars: int = 8_000,
) -> str:
    selected: list[str] = []
    remaining = max_total_chars
    for message in messages:
        if remaining <= 0:
            break
        text = message.text[:max_message_chars]
        labels = {
            "user": "USER_STATEMENT",
            "assistant": "ASSISTANT_RESULT",
            "tool": "VERIFICATION_OUTPUT",
        }
        label = labels.get(message.role, "OTHER")
        block = f"[{label}]\n{text}\n"
        block = block[:remaining]
        selected.append(block)
        remaining -= len(block)
    return "\n".join(selected)
