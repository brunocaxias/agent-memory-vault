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

from .models import CandidateMemory, MemoryRecord, QueueJob

VAULT_DIRECTORIES = (
    "00-system",
    "10-global/memories",
    "20-projects",
    "30-runbooks",
    "40-decisions",
    "80-audit",
    "90-quarantine",
    "99-archive",
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "memory"


def memory_id(candidate: CandidateMemory) -> str:
    digest = hashlib.sha256(
        f"{candidate.type}|{candidate.scope}|{candidate.content}".encode()
    ).hexdigest()[:12]
    return f"{slugify(candidate.type)}-{slugify(candidate.content)[:36]}-{digest}"


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


def load_record(path: Path) -> MemoryRecord:
    metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
    heading = next((line[2:] for line in body.splitlines() if line.startswith("# ")), "")
    paragraphs = [
        line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#")
    ]
    content = paragraphs[0] if paragraphs else heading
    return MemoryRecord.model_validate({**metadata, "content": content, "path": path})


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
        schema_path = self.root / "00-system/memory-schema.md"
        if not schema_path.exists():
            schema_path.write_text(
                "# Memory Schema\n\n"
                "Canonical memories require stable identity, lifecycle status, scope, "
                "source provenance, redacted evidence, and a review date.\n",
                encoding="utf-8",
            )

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

    def destination(self, candidate: CandidateMemory, identifier: str) -> Path:
        if candidate.scope.startswith("project:"):
            project = slugify(candidate.scope.split(":", 1)[1])
            return self.root / "20-projects" / project / "memories" / f"{identifier}.md"
        if candidate.type == "runbook":
            return self.root / "30-runbooks" / f"{identifier}.md"
        if candidate.type == "decision":
            return self.root / "40-decisions" / f"{identifier}.md"
        return self.root / "10-global/memories" / f"{identifier}.md"

    def ensure_project_dossier(self, project_slug: str) -> list[Path]:
        root = self.root / "20-projects" / slugify(project_slug)
        created: list[Path] = []
        templates = {
            "context.md": f"# {project_slug} Context\n\nActive project memories are linked here.\n",
            "decisions.md": f"# {project_slug} Decisions\n\nSee linked decision memories.\n",
            "current-state.md": (
                f"# {project_slug} Current State\n\nSee active project-state memories.\n"
            ),
        }
        for name, content in templates.items():
            path = root / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                created.append(path)
        return created

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
                if job.project_slug:
                    written.extend(self.ensure_project_dossier(job.project_slug))
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
                        review_after=candidate.review_after,
                        priority="medium",
                        supersedes=supersedes,
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
        return written, rejected

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
        return changed
