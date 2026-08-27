from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path

import yaml

from .models import MemoryRecord
from .vault import Vault, load_record

_QUERY_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{1,79}", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    return list(dict.fromkeys(token.casefold() for token in _QUERY_TOKEN.findall(text)))


def _active_records(
    vault_root: Path,
    project_slug: str | None,
    *,
    include_all_scopes: bool = False,
) -> list[MemoryRecord]:
    today = date.today()
    records: list[MemoryRecord] = []
    for path in Vault(vault_root).memory_files():
        try:
            record = load_record(path)
        except (OSError, ValueError, yaml.YAMLError):
            continue
        if record.status != "active" or record.review_after < today:
            continue
        if record.effective_from and record.effective_from > today:
            continue
        if record.effective_to and record.effective_to < today:
            continue
        if include_all_scopes or record.scope == "global" or (
            project_slug and record.scope == f"project:{project_slug}"
        ):
            records.append(record)
    return records


def _database_path(state_root: Path) -> Path:
    return state_root / "retrieval" / "canonical-memory.sqlite3"


def refresh_index(vault_root: Path, state_root: Path) -> Path:
    """Rebuild the disposable local FTS index from canonical Markdown."""
    path = _database_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("DROP TABLE IF EXISTS records")
        connection.execute(
            "CREATE VIRTUAL TABLE records USING fts5("
            "id UNINDEXED, scope UNINDEXED, priority UNINDEXED, kind UNINDEXED, "
            "content, entities, concepts, relations, path UNINDEXED)"
        )
        for record in _active_records(vault_root, project_slug=None, include_all_scopes=True):
            connection.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.scope,
                    record.priority,
                    record.type,
                    record.content,
                    " ".join(record.entities),
                    " ".join(record.concepts),
                    " ".join(f"{relation.type} {relation.target}" for relation in record.relations),
                    str(record.path or ""),
                ),
            )
        connection.commit()
    finally:
        connection.close()
    return path


def _fts_ids(index_path: Path, query: str, project_slug: str | None) -> dict[str, float]:
    tokens = _tokens(query)
    if not tokens or not index_path.exists():
        return {}
    match = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)
    connection = sqlite3.connect(index_path)
    try:
        if project_slug:
            rows = connection.execute(
                "SELECT id, bm25(records) FROM records "
                "WHERE records MATCH ? AND (scope = 'global' OR scope = ?) "
                "ORDER BY bm25(records) LIMIT 30",
                (match, f"project:{project_slug}"),
            )
        else:
            rows = connection.execute(
                "SELECT id, bm25(records) FROM records "
                "WHERE records MATCH ? AND scope = 'global' "
                "ORDER BY bm25(records) LIMIT 30",
                (match,),
            )
        return {identifier: -float(rank) for identifier, rank in rows}
    except sqlite3.OperationalError:
        return {}
    finally:
        connection.close()


def rank_records(
    vault_root: Path,
    state_root: Path,
    *,
    project_slug: str | None,
    query: str,
) -> list[MemoryRecord]:
    """Rank active scope-eligible records using FTS plus deterministic authority signals."""
    index_path = refresh_index(vault_root, state_root)
    lexical = _fts_ids(index_path, query, project_slug)
    query_tokens = set(_tokens(query))
    priority = {"high": 3.0, "medium": 2.0, "low": 1.0}
    authority = {
        "decision": 2.5,
        "runbook": 2.5,
        "preference": 2.0,
        "project-state": 1.5,
        "lesson": 1.0,
        "fact": 1.0,
    }

    scored: list[tuple[float, MemoryRecord]] = []
    for record in _active_records(vault_root, project_slug):
        labels = set(_tokens(" ".join([*record.entities, *record.concepts])))
        relation_tokens = set(
            _tokens(" ".join(f"{relation.type} {relation.target}" for relation in record.relations))
        )
        score = lexical.get(record.id, 0.0) * 4.0
        score += len(query_tokens & labels) * 3.0
        score += len(query_tokens & relation_tokens) * 1.5
        score += priority[record.priority] + authority[record.type]
        if record.scope != "global":
            score += 0.5
        if score > priority[record.priority] + authority[record.type]:
            scored.append((score, record))
    ranked = sorted(
        scored,
        key=lambda item: (item[0], item[1].created, item[1].id),
        reverse=True,
    )
    return [record for _, record in ranked]
