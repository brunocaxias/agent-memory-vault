from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from agent_memory_vault.config import Settings
from agent_memory_vault.models import CandidateMemory, MemoryRelation, QueueJob
from agent_memory_vault.projections import rebuild_projections
from agent_memory_vault.selector import build_context_pack, build_prompt_context_pack
from agent_memory_vault.vault import Vault, load_record


def candidate(
    content: str,
    *,
    scope: str = "global",
    supersedes_id: str | None = None,
    review_delta: int = 30,
    entities: list[str] | None = None,
    concepts: list[str] | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    relations: list[MemoryRelation] | None = None,
) -> CandidateMemory:
    return CandidateMemory(
        type="preference",
        scope=scope,
        content=content,
        eligibility="explicit-user-statement",
        evidence_excerpt=content,
        supersedes_id=supersedes_id,
        review_after=date.today() + timedelta(days=review_delta),
        entities=entities or [],
        concepts=concepts or [],
        effective_from=effective_from,
        effective_to=effective_to,
        relations=relations or [],
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
    assert "Use SQLite here." not in build_context_pack(settings, project_slug="alpha").text
    prompt_pack = build_prompt_context_pack(
        settings, project_slug="alpha", prompt="Which database should this project use?"
    )
    assert "Use SQLite here." in prompt_pack.text
    assert "Use SQLite here." not in build_prompt_context_pack(
        settings, project_slug="beta", prompt="Which database should this project use?"
    ).text


def test_near_duplicate_memory_is_rejected(settings: Settings, tmp_path: Path) -> None:
    vault = Vault(settings.vault_root)
    first, rejected = vault.write_batch(
        [candidate("Use SQLite for local prompt memory indexing.")], job(tmp_path)
    )
    assert first and not rejected
    written, rejected = vault.write_batch(
        [candidate("Use SQLite for local prompt-memory indexing.")], job(tmp_path)
    )
    assert not written
    assert any("near-duplicate active memory" in reason for reason in rejected)


def test_agent_projections_are_rich_rebuildable_and_not_injected(
    settings: Settings, tmp_path: Path
) -> None:
    vault = Vault(settings.vault_root)
    memory = candidate(
        "Use SQLite as the canonical project store.",
        scope="project:alpha",
        entities=["SQLite", "Alpha"],
        concepts=["canonical storage", "local first"],
    )
    written, _ = vault.write_batch([memory], job(tmp_path, "alpha"))
    canonical = next(path for path in written if path.suffix == ".md")

    project = settings.vault_root / "70-projections/projects/alpha.md"
    entities = settings.vault_root / "70-projections/entities.md"
    concepts = settings.vault_root / "70-projections/concepts.md"
    active = settings.vault_root / "70-projections/active-memory-index.md"
    assert "Use SQLite as the canonical project store." in project.read_text()
    assert "## SQLite" in entities.read_text()
    assert "## canonical storage" in concepts.read_text()
    assert str(canonical.relative_to(settings.vault_root).with_suffix("")) in active.read_text()

    pack = build_context_pack(settings, project_slug="alpha")
    assert pack.files == ()
    assert all("70-projections" not in str(path) for path in pack.files)
    prompt_pack = build_prompt_context_pack(
        settings, project_slug="alpha", prompt="What is the canonical project store?"
    )
    assert prompt_pack.files == (canonical,)

    obsolete = settings.vault_root / "70-projections/projects/obsolete.md"
    obsolete.write_text("stale projection\n", encoding="utf-8")
    changed = rebuild_projections(settings.vault_root)
    assert obsolete in changed
    assert not obsolete.exists()


def test_candidate_labels_are_normalized_and_bounded() -> None:
    memory = candidate(
        "Use Obsidian.",
        entities=["  Obsidian  ", "obsidian"],
        concepts=[" persistent   memory "],
    )
    assert memory.entities == ["Obsidian"]
    assert memory.concepts == ["persistent memory"]


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


def test_prompt_recall_uses_labels_and_relations(settings: Settings, tmp_path: Path) -> None:
    vault = Vault(settings.vault_root)
    first, _ = vault.write_batch([candidate("Use SQLite for local indexing.")], job(tmp_path))
    target = load_record(next(path for path in first if path.suffix == ".md"))
    vault.write_batch(
        [
            candidate(
                "Use FTS5 for prompt-aware memory retrieval.",
                scope="project:alpha",
                entities=["SQLite", "FTS5"],
                concepts=["prompt recall"],
                relations=[
                    MemoryRelation(type="uses", target=target.id, target_kind="memory"),
                    MemoryRelation(
                        type="implements", target="prompt recall", target_kind="concept"
                    ),
                ],
            )
        ],
        job(tmp_path, "alpha"),
    )
    pack = build_prompt_context_pack(
        settings,
        project_slug="alpha",
        prompt="How does FTS5 prompt recall work?",
    )
    assert "Use FTS5 for prompt-aware memory retrieval." in pack.text
    relation_projection = settings.vault_root / "70-projections/relations.md"
    assert "--uses-->" in relation_projection.read_text(encoding="utf-8")


def test_supersession_closes_previous_effective_window(settings: Settings, tmp_path: Path) -> None:
    vault = Vault(settings.vault_root)
    first, _ = vault.write_batch([candidate("Use the old tool.")], job(tmp_path))
    old = load_record(next(path for path in first if path.suffix == ".md"))
    vault.write_batch(
        [candidate("Use the new tool.", supersedes_id=old.id)],
        job(tmp_path),
    )
    updated = load_record(vault.find_by_id(old.id))
    assert updated.effective_to == date.today()
