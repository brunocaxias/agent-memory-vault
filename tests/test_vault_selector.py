from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from agent_memory_vault.config import Settings
from agent_memory_vault.models import CandidateMemory, QueueJob
from agent_memory_vault.selector import build_context_pack
from agent_memory_vault.vault import Vault, load_record


def candidate(
    content: str,
    *,
    scope: str = "global",
    supersedes_id: str | None = None,
    review_delta: int = 30,
) -> CandidateMemory:
    return CandidateMemory(
        type="preference",
        scope=scope,
        content=content,
        eligibility="explicit-user-statement",
        evidence_excerpt=content,
        supersedes_id=supersedes_id,
        review_after=date.today() + timedelta(days=review_delta),
    )


def job(tmp_path: Path, project_slug: str | None = None) -> QueueJob:
    return QueueJob(
        id="job",
        session_id="session",
        transcript_path=tmp_path / "rollout.jsonl",
        transcript_sha256="a" * 64,
        cwd=tmp_path,
        project_slug=project_slug,
    )


def test_write_and_select_global_memory(settings: Settings, tmp_path: Path) -> None:
    vault = Vault(settings.vault_root)
    written, rejected = vault.write_batch([candidate("Prefer local tools.")], job(tmp_path))
    assert not rejected
    assert written
    pack = build_context_pack(settings, project_slug=None)
    assert "Prefer local tools." in pack.text
    assert "source:" in pack.text


def test_project_scope_isolated(settings: Settings, tmp_path: Path) -> None:
    vault = Vault(settings.vault_root)
    memory = candidate("Use SQLite here.", scope="project:alpha")
    vault.write_batch([memory], job(tmp_path, "alpha"))
    assert "Use SQLite here." in build_context_pack(settings, project_slug="alpha").text
    assert "Use SQLite here." not in build_context_pack(settings, project_slug="beta").text


def test_supersession_updates_old_record(settings: Settings, tmp_path: Path) -> None:
    vault = Vault(settings.vault_root)
    written, _ = vault.write_batch([candidate("Use the old tool.")], job(tmp_path))
    old = load_record(next(path for path in written if path.name.endswith(".md")))
    vault.write_batch(
        [candidate("Use the new tool.", supersedes_id=old.id)],
        job(tmp_path),
    )
    updated = load_record(vault.find_by_id(old.id))
    assert updated.status == "superseded"
    assert updated.superseded_by
    pack = build_context_pack(settings, project_slug=None)
    assert "Use the old tool." not in pack.text
    assert "Use the new tool." in pack.text


def test_overdue_memory_becomes_stale(settings: Settings, tmp_path: Path) -> None:
    vault = Vault(settings.vault_root)
    written, _ = vault.write_batch(
        [candidate("Temporary state.", review_delta=-1)],
        job(tmp_path),
    )
    changed = vault.mark_overdue_stale()
    assert changed
    record = load_record(next(path for path in written if path.name.endswith(".md")))
    assert record.status == "stale"
    assert "Temporary state." not in build_context_pack(settings, project_slug=None).text
