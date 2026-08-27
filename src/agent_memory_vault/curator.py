from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from .vault import Vault, load_record


@dataclass(frozen=True)
class CuratorFinding:
    code: str
    severity: str
    records: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class CuratorReport:
    generated_on: date
    findings: tuple[CuratorFinding, ...]


def curate_vault(root: Path, today: date | None = None) -> CuratorReport:
    """Return deterministic maintenance proposals without changing canonical memory."""
    current = today or date.today()
    records = []
    for path in Vault(root).memory_files():
        try:
            records.append(load_record(path))
        except (OSError, ValueError, yaml.YAMLError):
            continue

    findings: list[CuratorFinding] = []
    by_id = {record.id: record for record in records}
    by_content: dict[tuple[str, str, str], list[str]] = {}
    for record in records:
        normalized = " ".join(record.content.casefold().split())
        by_content.setdefault((record.scope, record.type, normalized), []).append(record.id)
        if record.status == "active" and record.review_after < current:
            findings.append(
                CuratorFinding(
                    "stale-review", "medium", (record.id,), "Active record is past review_after.")
            )
        for relation in record.relations:
            if relation.target_kind == "memory" and relation.target not in by_id:
                findings.append(
                    CuratorFinding(
                        "dangling-relation",
                        "high",
                        (record.id,),
                        f"Relation {relation.type} points to missing memory {relation.target}.",
                    )
                )
        if record.status == "active" and record.effective_to and record.effective_to < current:
            findings.append(
                CuratorFinding(
                    "expired-effective-window",
                    "medium",
                    (record.id,),
                    "Active record has an expired effective_to date.",
                )
            )
    for identifiers in by_content.values():
        if len(identifiers) > 1:
            findings.append(
                CuratorFinding(
                    "duplicate-content",
                    "low",
                    tuple(sorted(identifiers)),
                    "Records have identical normalized content in the same scope and type.",
                )
            )
    ordered = sorted(findings, key=lambda item: (item.severity, item.code, item.records))
    return CuratorReport(current, tuple(ordered))


def render_curator_report(report: CuratorReport) -> str:
    metadata = {
        "kind": "agent-curator-report",
        "generated": True,
        "canonical": False,
        "created": report.generated_on.isoformat(),
        "proposal_only": True,
    }
    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    lines = ["# Memory curator proposals", "", "> This report never changes canonical memory.", ""]
    if not report.findings:
        lines.append("- No deterministic maintenance proposals.")
    for finding in report.findings:
        lines.extend(
            [
                f"## {finding.code}",
                "",
                f"- severity: {finding.severity}",
                f"- records: {', '.join(finding.records)}",
                f"- proposal: {finding.message}",
                "",
            ]
        )
    return f"---\n{frontmatter}\n---\n\n" + "\n".join(lines) + "\n"


def write_curator_report(root: Path, report: CuratorReport) -> Path:
    path = root / "80-audit" / "curator-proposals.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(render_curator_report(report), encoding="utf-8")
    os.replace(temporary, path)
    return path
