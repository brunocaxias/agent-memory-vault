from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RedactionResult:
    text: str
    secret_detected: bool
    kinds: tuple[str, ...]


@dataclass(frozen=True)
class ScopeResult:
    blocked: bool
    kinds: tuple[str, ...]


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "generic-secret",
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|client[_-]?secret|password)\b"
            r"\s*[:=]\s*[\"']?([^\s\"']{8,})"
        ),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
)


def redact(text: str) -> RedactionResult:
    redacted = text
    detected: list[str] = []
    for kind, pattern in _PATTERNS:
        if pattern.search(redacted):
            detected.append(kind)
            redacted = pattern.sub(f"[REDACTED:{kind}]", redacted)
    return RedactionResult(redacted, bool(detected), tuple(sorted(set(detected))))


_OUT_OF_SCOPE: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "personal-health",
        re.compile(
            r"(?is)\b(?:my|i have|i was diagnosed|my doctor|my therapist)\b.{0,100}"
            r"\b(?:diagnosis|medication|illness|symptoms?|therapy|medical|health)\b"
        ),
    ),
    (
        "personal-finance",
        re.compile(
            r"(?is)\b(?:my|i owe|i earn|i make)\b.{0,100}"
            r"\b(?:salary|income|debt|bank balance|credit card|loan|investment account)\b"
        ),
    ),
    (
        "personal-contact",
        re.compile(
            r"(?is)\b(?:my home address|my phone number|my personal email|contact details)\b"
        ),
    ),
    ("diary", re.compile(r"(?i)\b(?:dear diary|private diary|journal entry)\b")),
)


def detect_out_of_scope(text: str) -> ScopeResult:
    kinds = tuple(kind for kind, pattern in _OUT_OF_SCOPE if pattern.search(text))
    return ScopeResult(bool(kinds), kinds)
