from __future__ import annotations

import fcntl
import hashlib
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import yaml

from .models import CandidateHandoff, CandidateMemory, MemoryRecord, QueueJob, SessionHandoff

VAULT_DIRECTORIES = (
    "00-system",
    "10-global/memories",
    "20-projects",
    "30-runbooks",
    "40-decisions",
    "60-handoffs",
    "70-projections",
    "80-audit",
    "90-quarantine",
    "99-archive",
)

MEMORY_SCHEMA = """\
# Canonical Memory Schema

Canonical records are the authoritative evidence layer. Generated projections
must never be used as a source when creating or correcting a canonical record.

## Required frontmatter

- `id`: deterministic stable identity.
- `type`: preference, decision, project-state, runbook, fact, or lesson.
- `status`: active, stale, superseded, or archived.
- `scope`: global or project:<slug>.
- `source`: eligibility kind, session reference, and transcript SHA-256.
- `evidence`: a short locally redacted supporting excerpt.
- `created`, `recorded_at`, `effective_from`, `effective_to`, and `review_after`:
  lifecycle and temporal-validity dates.
- `priority`: low, medium, or high.
- `entities` and `concepts`: optional grounded machine-retrieval labels.
- `relations`: optional typed links to memory IDs, entities, or concepts.

## Layer boundary

- Canonical records: `10-global`, `20-projects`, `30-runbooks`, `40-decisions`.
- Expiring session continuity: `60-handoffs` (not canonical memory).
- Fluid generated views: `70-projections`.
- Non-sensitive audit: `80-audit`.
- Raw transcripts, queue state, credentials, and unredacted text stay outside the vault.
"""

PROJECTION_CONTRACT = """\
# Agent Projection Contract

Everything below `70-projections` is deterministic, fluid, and replaceable.
Agents may use projections to navigate the vault, then follow links to canonical
records for provenance and lifecycle status.

Projection files may be deleted and rebuilt with:

`memory-vault rebuild-projections`

Do not manually store unique facts, decisions, or evidence in a projection.
The projection builder replaces stale files and regenerates active-memory,
project, entity, concept, relation, and supersession views from canonical records.
"""


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "memory"


def memory_id(candidate: CandidateMemory) -> str:
    digest = hashlib.sha256(
        f"{candidate.type}|{candidate.scope}|{candidate.content}".encode()
    ).hexdigest()[:12]
    return f"{slugify(candidate.type)}-{slugify(candidate.content)[:36]}-{digest}"


def _content_terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_]{1,79}", text.casefold().replace("-", " ")))


def is_near_duplicate(candidate: CandidateMemory, record: MemoryRecord) -> bool:
    """Reject only highly overlapping active records in the same semantic scope."""
    if (
        record.status != "active"
        or record.type != candidate.type
        or record.scope != candidate.scope
    ):
        return False
    candidate_terms = _content_terms(candidate.content)
    record_terms = _content_terms(record.content)
    if not candidate_terms or not record_terms:
        return candidate.content.casefold() == record.content.casefold()
    overlap = len(candidate_terms & record_terms) / len(candidate_terms | record_terms)
    return overlap >= 0.85


def split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise ValueError("unterminated YAML frontmatter")
    metadata = yaml.safe_load(text[4:marker]) or {}
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter must be a mapping")
    return metadata, text[marker + 5 :].lstrip("\n")


def render_record(record: MemoryRecord) -> str:
    metadata = record.model_dump(
        mode="json",
        exclude={"content", "path"},
        exclude_none=True,
    )
    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{frontmatter}\n---\n\n# {record.content}\n\n{record.content}\n"


def render_handoff(handoff: SessionHandoff) -> str:
    metadata = handoff.model_dump(mode="json", exclude={"path"}, exclude_none=True)
    metadata.update({"kind": "agent-session-handoff", "canonical": False})
    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    sections = [f"# Project handoff: {handoff.project_slug}", "", handoff.summary]
    for heading, values in (
        ("Completed", handoff.completed),
        ("Changed files", handoff.changed_files),
        ("Verification", handoff.verification),
        ("Blockers", handoff.blockers),
        ("Next steps", handoff.next_steps),
        ("Open questions", handoff.open_questions),
    ):
        if values:
            sections.extend(["", f"## {heading}", "", *[f"- {value}" for value in values]])
    sections.extend(
        [
            "",
            "> Expiring session continuity, generated from a redacted transcript.",
            "> It is not canonical memory; verify against repository state and "
            "source-cited records.",
        ]
    )
    return f"---\n{frontmatter}\n---\n\n" + "\n".join(sections) + "\n"


def load_record(path: Path) -> MemoryRecord:
    metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
    heading = next((line[2:] for line in body.splitlines() if line.startswith("# ")), "")
    paragraphs = [
        line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#")
    ]
    content = paragraphs[0] if paragraphs else heading
    return MemoryRecord.model_validate({**metadata, "content": content, "path": path})


def load_handoff(path: Path) -> SessionHandoff:
    metadata, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in metadata.items() if key not in {"kind", "canonical"}}
    return SessionHandoff.model_validate({**payload, "path": path})


@contextmanager
def vault_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".memory-vault.lock"
    with lock_path.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class Vault:
    def __init__(self, root: Path):
        self.root = root

    def initialize(self) -> None:
        for directory in VAULT_DIRECTORIES:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        system_files = {
            self.root / "00-system/memory-schema.md": MEMORY_SCHEMA,
            self.root / "00-system/projection-contract.md": PROJECTION_CONTRACT,
        }
        for path, content in system_files.items():
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                path.write_text(content, encoding="utf-8")
        gitignore = self.root / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                ".memory-vault.lock\n"
                ".obsidian/workspace*.json\n"
                ".trash/\n",
                encoding="utf-8",
            )
        from .projections import rebuild_projections

        rebuild_projections(self.root)

    def memory_files(self) -> Iterator[Path]:
        for prefix in ("10-global", "20-projects", "30-runbooks", "40-decisions"):
            root = self.root / prefix
            if root.exists():
                yield from root.rglob("*.md")

    def find_by_id(self, identifier: str) -> Path | None:
        for path in self.memory_files():
            try:
                metadata, _ = split_frontmatter(path.read_text(encoding="utf-8"))
            except OSError, ValueError, yaml.YAMLError:
                continue
            if metadata.get("id") == identifier:
                return path
        return None

    def find_near_duplicate(self, candidate: CandidateMemory) -> MemoryRecord | None:
        for path in self.memory_files():
            try:
                record = load_record(path)
            except (OSError, ValueError, yaml.YAMLError):
                continue
            if is_near_duplicate(candidate, record):
                return record
        return None

    def handoff_path(self, project_slug: str) -> Path:
        return self.root / "60-handoffs" / f"{slugify(project_slug)}.md"

    def load_current_handoff(
        self, project_slug: str, today: date | None = None
    ) -> SessionHandoff | None:
        path = self.handoff_path(project_slug)
        if not path.exists():
            return None
        try:
            handoff = load_handoff(path)
        except (OSError, ValueError, yaml.YAMLError):
            return None
        if handoff.expires_at < (today or date.today()):
            return None
        return handoff

    def write_handoff(
        self,
        candidate: CandidateHandoff,
        job: QueueJob,
        *,
        ttl_days: int,
    ) -> Path | None:
        if not job.project_slug:
            return None
        self.initialize()
        handoff = SessionHandoff(
            **candidate.model_dump(),
            project_slug=slugify(job.project_slug),
            session_id=job.session_id,
            expires_at=date.today().fromordinal(date.today().toordinal() + ttl_days),
        )
        path = self.handoff_path(job.project_slug)
        with vault_lock(self.root):
            path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(path, render_handoff(handoff))
        return path

    def destination(self, candidate: CandidateMemory, identifier: str) -> Path:
        if candidate.scope.startswith("project:"):
            project = slugify(candidate.scope.split(":", 1)[1])
            return self.root / "20-projects" / project / "memories" / f"{identifier}.md"
        if candidate.type == "runbook":
            return self.root / "30-runbooks" / f"{identifier}.md"
        if candidate.type == "decision":
            return self.root / "40-decisions" / f"{identifier}.md"
        return self.root / "10-global/memories" / f"{identifier}.md"

    def write_batch(
        self,
        candidates: list[CandidateMemory],
        job: QueueJob,
    ) -> tuple[list[Path], list[str]]:
        self.initialize()
        written: list[Path] = []
        rejected: list[str] = []
        backups: dict[Path, bytes | None] = {}
        with vault_lock(self.root):
            try:
                for candidate in candidates:
                    if candidate.scope.startswith("project:") and not job.project_slug:
                        rejected.append("project-scoped memory from non-project session")
                        continue
                    if candidate.scope.startswith("project:") and slugify(
                        candidate.scope.split(":", 1)[1]
                    ) != slugify(job.project_slug or ""):
                        rejected.append("classifier returned a different project scope")
                        continue
                    identifier = memory_id(candidate)
                    destination = self.destination(candidate, identifier)
                    if destination.exists():
                        continue
                    if candidate.supersedes_id is None:
                        duplicate = self.find_near_duplicate(candidate)
                        if duplicate is not None:
                            rejected.append(f"near-duplicate active memory {duplicate.id}")
                            continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    backups[destination] = None

                    supersedes = None
                    if candidate.supersedes_id:
                        old_path = self.find_by_id(candidate.supersedes_id)
                        if old_path:
                            old = load_record(old_path)
                            backups[old_path] = old_path.read_bytes()
                            old.status = "superseded"
                            old.superseded_by = identifier
                            old.effective_to = date.today()
                            self._atomic_write(old_path, render_record(old))
                            written.append(old_path)
                            supersedes = old.id
                        else:
                            rejected.append(
                                f"unknown supersedes_id {candidate.supersedes_id}; "
                                "saved without link"
                            )

                    record = MemoryRecord(
                        id=identifier,
                        type=candidate.type,
                        status="active",
                        scope=candidate.scope,
                        source={
                            "kind": candidate.eligibility,
                            "reference": f"codex-session:{job.session_id}",
                            "transcript_sha256": job.transcript_sha256,
                        },
                        evidence={"excerpt": candidate.evidence_excerpt},
                        created=date.today(),
                        recorded_at=date.today(),
                        review_after=candidate.review_after,
                        effective_from=candidate.effective_from or date.today(),
                        effective_to=candidate.effective_to,
                        priority="medium",
                        supersedes=supersedes,
                        entities=candidate.entities,
                        concepts=candidate.concepts,
                        relations=self._validated_relations(candidate.relations),
                        content=candidate.content,
                    )
                    self._atomic_write(destination, render_record(record))
                    written.append(destination)
            except Exception:
                for path, original in backups.items():
                    if original is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_bytes(original)
                raise
        from .projections import rebuild_projections

        rebuild_projections(self.root)
        return written, rejected

    def _validated_relations(self, relations):
        valid = []
        for relation in relations:
            if relation.target_kind == "memory" and self.find_by_id(relation.target) is None:
                continue
            valid.append(relation)
        return valid

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)

    def mark_overdue_stale(self, today: date | None = None) -> list[Path]:
        current = today or date.today()
        changed: list[Path] = []
        with vault_lock(self.root):
            for path in self.memory_files():
                try:
                    record = load_record(path)
                except OSError, ValueError, yaml.YAMLError:
                    continue
                if record.status == "active" and record.review_after < current:
                    record.status = "stale"
                    self._atomic_write(path, render_record(record))
                    changed.append(path)
        if changed:
            from .projections import rebuild_projections

            rebuild_projections(self.root)
        return changed
