from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import QueueJob


def transcript_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def job_id(session_id: str, transcript_hash: str) -> str:
    return hashlib.sha256(f"{session_id}:{transcript_hash}".encode()).hexdigest()


class FileQueue:
    STATES = ("pending", "processing", "completed", "failed", "budget_paused")

    def __init__(self, state_root: Path):
        self.root = state_root / "queue"
        for state in self.STATES:
            (self.root / state).mkdir(parents=True, exist_ok=True)

    def path_for(self, state: str, identifier: str) -> Path:
        return self.root / state / f"{identifier}.json"

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    def enqueue(
        self,
        *,
        session_id: str,
        transcript_path: Path,
        transcript_hash: str,
        cwd: Path,
        project_slug: str | None,
    ) -> tuple[QueueJob, bool]:
        identifier = job_id(session_id, transcript_hash)
        for state in self.STATES:
            existing = self.path_for(state, identifier)
            if existing.exists():
                return QueueJob.model_validate_json(existing.read_text(encoding="utf-8")), False
        job = QueueJob(
            id=identifier,
            session_id=session_id,
            transcript_path=transcript_path,
            transcript_sha256=transcript_hash,
            cwd=cwd,
            project_slug=project_slug,
        )
        self._atomic_json(self.path_for("pending", identifier), job.model_dump(mode="json"))
        return job, True

    def claim(self) -> QueueJob | None:
        now = datetime.now(UTC)
        for pending in sorted((self.root / "pending").glob("*.json")):
            try:
                job = QueueJob.model_validate_json(pending.read_text(encoding="utf-8"))
            except OSError, ValueError:
                continue
            if job.next_attempt_at > now:
                continue
            processing = self.path_for("processing", job.id)
            try:
                os.replace(pending, processing)
            except FileNotFoundError:
                continue
            return job
        return None

    def complete(self, job: QueueJob) -> None:
        source = self.path_for("processing", job.id)
        destination = self.path_for("completed", job.id)
        self._atomic_json(destination, job.model_dump(mode="json"))
        source.unlink(missing_ok=True)

    def fail(self, job: QueueJob, message: str) -> None:
        job.last_error = message
        source = self.path_for("processing", job.id)
        destination = self.path_for("failed", job.id)
        self._atomic_json(destination, job.model_dump(mode="json"))
        source.unlink(missing_ok=True)

    def retry(self, job: QueueJob, message: str, *, maximum_attempts: int) -> bool:
        job.attempts += 1
        job.last_error = message
        if job.attempts >= maximum_attempts:
            self.fail(job, message)
            return False
        delay = min(3600, 15 * (2 ** (job.attempts - 1)))
        job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
        destination = self.path_for("pending", job.id)
        self._atomic_json(destination, job.model_dump(mode="json"))
        self.path_for("processing", job.id).unlink(missing_ok=True)
        return True

    def release(self, job: QueueJob, message: str, *, delay_seconds: int = 300) -> None:
        job.last_error = message
        job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        destination = self.path_for("pending", job.id)
        self._atomic_json(destination, job.model_dump(mode="json"))
        self.path_for("processing", job.id).unlink(missing_ok=True)

    def pause_for_budget(self, job: QueueJob) -> None:
        destination = self.path_for("budget_paused", job.id)
        self._atomic_json(destination, job.model_dump(mode="json"))
        self.path_for("processing", job.id).unlink(missing_ok=True)

    def resume_budget_jobs(self) -> int:
        moved = 0
        for paused in (self.root / "budget_paused").glob("*.json"):
            os.replace(paused, self.root / "pending" / paused.name)
            moved += 1
        return moved
