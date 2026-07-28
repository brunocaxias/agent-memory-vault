from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .redaction import redact
from .vault import Vault, load_record

_WIKILINK = re.compile(r"\[\[([^]|#]+)(?:#[^]|]+)?(?:\|[^]]+)?]]")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def validate_vault(root: Path) -> list[ValidationIssue]:
    vault = Vault(root)
    issues: list[ValidationIssue] = []
    ids: dict[str, Path] = {}
    all_markdown = list(root.rglob("*.md")) if root.exists() else []
    by_stem: dict[str, list[Path]] = {}
    for path in all_markdown:
        by_stem.setdefault(path.stem.casefold(), []).append(path)

    for path in vault.memory_files():
        relative = str(path.relative_to(root))
        try:
            record = load_record(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            issues.append(ValidationIssue("invalid-memory", relative, str(exc)))
            continue
        if record.id in ids:
            issues.append(
                ValidationIssue(
                    "duplicate-id",
                    relative,
                    f"memory id also exists at {ids[record.id].relative_to(root)}",
                )
            )
        else:
            ids[record.id] = path
        redaction = redact(path.read_text(encoding="utf-8"))
        if redaction.secret_detected:
            issues.append(
                ValidationIssue(
                    "secret-pattern",
                    relative,
                    f"matched secret categories: {', '.join(redaction.kinds)}",
                )
            )

    for path in all_markdown:
        relative = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(ValidationIssue("unreadable", relative, str(exc)))
            continue
        for target in _WIKILINK.findall(text):
            candidate = (path.parent / target).with_suffix(".md")
            if candidate.exists() or by_stem.get(Path(target).stem.casefold()):
                continue
            issues.append(
                ValidationIssue(
                    "broken-link",
                    relative,
                    f"cannot resolve [[{target}]]",
                )
            )
    return issues
