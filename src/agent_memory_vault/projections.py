from __future__ import annotations

import os
import re
from collections import defaultdict
from contextlib import suppress
from datetime import date
from pathlib import Path

import yaml

from .models import MemoryRecord

PROJECTION_ROOT = Path("70-projections")


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:60] or "memory"


def _frontmatter(name: str) -> str:
    metadata = {
        "kind": "agent-projection",
        "projection": name,
        "generated": True,
        "canonical": False,
    }
    rendered = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{rendered}\n---\n\n"


def _link(record: MemoryRecord, root: Path) -> str:
    if record.path is None:
        return f"`{record.id}`"
    relative = record.path.relative_to(root).with_suffix("").as_posix()
    return f"[[{relative}|{record.id}]]"


def _record_line(record: MemoryRecord, root: Path) -> str:
    labels = []
    if record.entities:
        labels.append("entities=" + ", ".join(record.entities))
    if record.concepts:
        labels.append("concepts=" + ", ".join(record.concepts))
    suffix = f"; {'; '.join(labels)}" if labels else ""
    return (
        f"- {_link(record, root)} | type={record.type}; scope={record.scope}; "
        f"priority={record.priority}; effective_from={record.effective_from}; "
        f"effective_to={record.effective_to}; review_after={record.review_after}{suffix} | "
        f"{record.content}"
    )


def _projection_document(name: str, title: str, body: list[str]) -> str:
    return _frontmatter(name) + "\n".join(
        [
            f"# {title}",
            "",
            "> Deterministic generated view. Do not treat this file as canonical memory.",
            "> Rebuild it from the source-cited records when organization changes.",
            "",
            *body,
            "",
        ]
    )


def _active(records: list[MemoryRecord]) -> list[MemoryRecord]:
    today = date.today()
    return [
        record
        for record in records
        if record.status == "active"
        and record.review_after >= today
        and (record.effective_from is None or record.effective_from <= today)
        and (record.effective_to is None or record.effective_to >= today)
    ]


def _load_records(root: Path) -> list[MemoryRecord]:
    from .vault import Vault, load_record

    records: list[MemoryRecord] = []
    for path in Vault(root).memory_files():
        try:
            records.append(load_record(path))
        except (OSError, ValueError, yaml.YAMLError):
            continue
    return sorted(records, key=lambda item: (item.scope, item.type, item.id))


def render_projections(root: Path) -> dict[Path, str]:
    records = _load_records(root)
    active = _active(records)
    documents: dict[Path, str] = {}

    status_counts: dict[str, int] = defaultdict(int)
    for record in records:
        status_counts[record.status] += 1
    manifest_body = [
        "## Layer contract",
        "",
        (
            "- Canonical records live in `10-global`, `20-projects`, "
            "`30-runbooks`, and `40-decisions`."
        ),
        (
            "- Files below `70-projections` are fluid, replaceable, and "
            "derived only from canonical records."
        ),
        (
            "- Raw transcripts, queues, credentials, and unredacted evidence "
            "remain outside this vault."
        ),
        "",
        "## Counts",
        "",
        f"- canonical_total: {len(records)}",
        f"- active: {status_counts.get('active', 0)}",
        f"- stale: {status_counts.get('stale', 0)}",
        f"- superseded: {status_counts.get('superseded', 0)}",
        f"- archived: {status_counts.get('archived', 0)}",
        "",
        "## Agent entry points",
        "",
        "- [[70-projections/active-memory-index|Active memory index]]",
        "- [[70-projections/entities|Entity index]]",
        "- [[70-projections/concepts|Concept index]]",
        "- [[70-projections/relations|Relation graph]]",
        "- [[70-projections/supersession|Supersession graph]]",
    ]
    documents[PROJECTION_ROOT / "manifest.md"] = _projection_document(
        "manifest", "Agent Memory Projection Manifest", manifest_body
    )

    active_body = ["## Global", ""]
    global_records = [record for record in active if record.scope == "global"]
    active_body.extend(
        [_record_line(record, root) for record in global_records]
        or ["- No active global memories."]
    )
    projects: dict[str, list[MemoryRecord]] = defaultdict(list)
    for record in active:
        if record.scope.startswith("project:"):
            projects[_safe_slug(record.scope.split(":", 1)[1])].append(record)
    for project, project_records in sorted(projects.items()):
        active_body.extend(
            ["", f"## Project: {project}", ""]
            + [_record_line(record, root) for record in project_records]
        )
    documents[PROJECTION_ROOT / "active-memory-index.md"] = _projection_document(
        "active-memory-index", "Active Memory Index", active_body
    )

    for project, project_records in sorted(projects.items()):
        body = [f"- scope: `project:{project}`", ""]
        by_type: dict[str, list[MemoryRecord]] = defaultdict(list)
        for record in project_records:
            by_type[record.type].append(record)
        for memory_type, typed_records in sorted(by_type.items()):
            body.extend(
                [f"## {memory_type}", ""]
                + [_record_line(record, root) for record in typed_records]
                + [""]
            )
        documents[PROJECTION_ROOT / "projects" / f"{project}.md"] = (
            _projection_document(
                f"project:{project}", f"Project Dossier: {project}", body
            )
        )

    for field_name, filename, title in (
        ("entities", "entities.md", "Entity Index"),
        ("concepts", "concepts.md", "Concept Index"),
    ):
        grouped: dict[str, list[MemoryRecord]] = defaultdict(list)
        display: dict[str, str] = {}
        for record in active:
            for label in getattr(record, field_name):
                key = label.casefold()
                display.setdefault(key, label)
                grouped[key].append(record)
        body: list[str] = []
        for key, grouped_records in sorted(grouped.items()):
            body.extend(
                [f"## {display[key]}", ""]
                + [_record_line(record, root) for record in grouped_records]
                + [""]
            )
        if not body:
            body = [f"- No active {field_name} have been extracted yet."]
        documents[PROJECTION_ROOT / filename] = _projection_document(
            field_name, title, body
        )

    edges: set[tuple[str, str, str]] = set()
    by_id = {record.id: record for record in records}
    for record in records:
        if record.supersedes:
            edges.add((record.id, "supersedes", record.supersedes))
        if record.superseded_by:
            edges.add((record.id, "superseded-by", record.superseded_by))
    edge_lines = []
    for source, relation, target in sorted(edges):
        source_record = by_id.get(source)
        target_record = by_id.get(target)
        source_link = _link(source_record, root) if source_record else f"`{source}`"
        target_link = _link(target_record, root) if target_record else f"`{target}`"
        edge_lines.append(f"- {source_link} --{relation}--> {target_link}")
    documents[PROJECTION_ROOT / "supersession.md"] = _projection_document(
        "supersession", "Supersession Graph", edge_lines or ["- No supersession edges."]
    )
    relation_lines = []
    for record in active:
        for relation in record.relations:
            relation_lines.append(
                f"- {_link(record, root)} --{relation.type}--> "
                f"`{relation.target_kind}:{relation.target}`"
            )
    documents[PROJECTION_ROOT / "relations.md"] = _projection_document(
        "relations",
        "Relation Graph",
        relation_lines or ["- No typed relations have been extracted yet."],
    )
    return documents


def rebuild_projections(root: Path) -> list[Path]:
    desired = render_projections(root)
    projection_root = root / PROJECTION_ROOT
    projection_root.mkdir(parents=True, exist_ok=True)
    changed: list[Path] = []

    desired_paths = {root / relative for relative in desired}
    for path in sorted(projection_root.rglob("*.md")):
        if path not in desired_paths:
            path.unlink()
            changed.append(path)

    for relative, content in sorted(desired.items(), key=lambda item: str(item[0])):
        path = root / relative
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
        changed.append(path)

    for directory in sorted(
        (path for path in projection_root.rglob("*") if path.is_dir()),
        reverse=True,
    ):
        with suppress(OSError):
            directory.rmdir()
    return changed
