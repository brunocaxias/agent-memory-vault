from __future__ import annotations

import time
from dataclasses import dataclass

from .audit import write_runtime_event, write_vault_audit
from .budget import MonthlyBudget
from .classifier import (
    ClassifierError,
    ClassifierNotConfigured,
    DeepSeekClassifier,
)
from .config import Settings
from .gitops import GitError, commit_memory_batch, run_backup
from .queue import FileQueue
from .redaction import detect_out_of_scope, redact
from .retrieval import refresh_index
from .transcript import TranscriptError, build_classifier_excerpt, parse_transcript
from .vault import Vault


@dataclass(frozen=True)
class WorkResult:
    state: str
    job_id: str | None = None
    memories_written: int = 0


class MemoryWorker:
    def __init__(
        self,
        settings: Settings,
        *,
        classifier: DeepSeekClassifier | None = None,
    ):
        self.settings = settings
        self.queue = FileQueue(settings.state_root)
        self.vault = Vault(settings.vault_root)
        self.classifier = classifier or DeepSeekClassifier(settings)
        self.budget = MonthlyBudget(settings.state_root, settings)

    def run_once(self) -> WorkResult:
        job = self.queue.claim()
        if job is None and not self.budget.exhausted():
            resumed = self.queue.resume_budget_jobs()
            if resumed:
                write_runtime_event(
                    self.settings.state_root,
                    "budget_jobs_resumed",
                    count=resumed,
                )
                job = self.queue.claim()
        if job is None:
            return WorkResult("idle")
        if self.budget.exhausted():
            self.queue.pause_for_budget(job)
            write_runtime_event(
                self.settings.state_root,
                "budget_paused",
                job_id=job.id,
                spent_usd=self.budget.spent(),
            )
            return WorkResult("budget_paused", job.id)

        try:
            messages = parse_transcript(job.transcript_path)
            excerpt = build_classifier_excerpt(messages)
        except TranscriptError as exc:
            self.queue.fail(job, str(exc))
            write_runtime_event(
                self.settings.state_root,
                "source_unavailable",
                job_id=job.id,
            )
            return WorkResult("failed", job.id)

        redaction = redact(excerpt)
        if redaction.secret_detected:
            audit_path = write_vault_audit(
                self.settings.vault_root,
                "secret-blocked",
                job.session_id,
                "Capture was blocked locally because the transcript matched a secret pattern.",
            )
            try:
                self._commit_and_backup(job.session_id)
            except GitError as exc:
                retried = self.queue.retry(
                    job,
                    str(exc),
                    maximum_attempts=self.settings.max_attempts,
                )
                return WorkResult("retry" if retried else "failed", job.id)
            self.queue.complete(job)
            write_runtime_event(
                self.settings.state_root,
                "secret_blocked",
                job_id=job.id,
                kinds=list(redaction.kinds),
                audit_path=str(audit_path.relative_to(self.settings.vault_root)),
            )
            return WorkResult("blocked", job.id)

        scope = detect_out_of_scope(redaction.text)
        if scope.blocked:
            write_vault_audit(
                self.settings.vault_root,
                "scope-blocked",
                job.session_id,
                "Capture was blocked locally because the transcript matched "
                "excluded personal content.",
            )
            try:
                self._commit_and_backup(job.session_id)
            except GitError as exc:
                retried = self.queue.retry(
                    job,
                    str(exc),
                    maximum_attempts=self.settings.max_attempts,
                )
                return WorkResult("retry" if retried else "failed", job.id)
            self.queue.complete(job)
            write_runtime_event(
                self.settings.state_root,
                "scope_blocked",
                job_id=job.id,
                kinds=list(scope.kinds),
            )
            return WorkResult("blocked", job.id)

        try:
            result = self.classifier.classify(redaction.text, job.project_slug)
        except ClassifierNotConfigured as exc:
            self.queue.release(job, str(exc), delay_seconds=300)
            write_runtime_event(
                self.settings.state_root,
                "configuration_wait",
                job_id=job.id,
                setting=self.settings.classifier_api_key_env,
            )
            return WorkResult("configuration_wait", job.id)
        except ClassifierError as exc:
            retried = self.queue.retry(
                job,
                str(exc),
                maximum_attempts=self.settings.max_attempts,
            )
            write_runtime_event(
                self.settings.state_root,
                "classifier_retry" if retried else "classifier_failed",
                job_id=job.id,
                attempts=job.attempts,
            )
            return WorkResult("retry" if retried else "failed", job.id)

        self.budget.record(result.input_tokens, result.output_tokens)
        valid = []
        rejected_evidence = 0
        role_text = {
            role: " ".join(
                " ".join(message.text.split()) for message in messages if message.role == role
            ).casefold()
            for role in ("user", "assistant", "tool")
        }
        for candidate in result.output.memories:
            evidence = " ".join(candidate.evidence_excerpt.split()).casefold()
            explicit_supported = (
                candidate.eligibility == "explicit-user-statement"
                and evidence
                and evidence in role_text["user"]
            )
            outcome_supported = (
                candidate.eligibility == "verified-project-outcome"
                and evidence
                and evidence in f"{role_text['assistant']} {role_text['tool']}"
                and bool(role_text["tool"])
            )
            if explicit_supported or outcome_supported:
                valid.append(candidate)
            else:
                rejected_evidence += 1

        written, policy_rejections = self.vault.write_batch(valid, job)
        handoff_path = None
        if result.output.handoff is not None:
            handoff_path = self.vault.write_handoff(
                result.output.handoff,
                job,
                ttl_days=self.settings.handoff_ttl_days,
            )
        if rejected_evidence or policy_rejections:
            write_vault_audit(
                self.settings.vault_root,
                "candidate-rejected",
                job.session_id,
                (
                    f"Rejected {rejected_evidence} candidate(s) with unsupported evidence "
                    f"and {len(policy_rejections)} candidate(s) for scope or lifecycle policy."
                ),
            )
        self.vault.mark_overdue_stale()
        refresh_index(self.settings.vault_root, self.settings.state_root)
        try:
            self._commit_and_backup(job.session_id)
        except GitError as exc:
            retried = self.queue.retry(
                job,
                str(exc),
                maximum_attempts=self.settings.max_attempts,
            )
            return WorkResult("retry" if retried else "failed", job.id)
        self.queue.complete(job)
        write_runtime_event(
            self.settings.state_root,
            "capture_completed",
            job_id=job.id,
            memories_written=len(written),
            candidates=len(result.output.memories),
            handoff_written=bool(handoff_path),
            capture_event=job.capture_event,
        )
        return WorkResult("completed", job.id, len(written))

    def _commit_and_backup(self, session_id: str) -> None:
        try:
            committed = commit_memory_batch(self.settings.vault_root, session_id)
        except GitError as exc:
            write_runtime_event(
                self.settings.state_root,
                "git_failure",
                session_id=session_id,
                error=str(exc),
            )
            raise
        if not committed:
            return
        try:
            backed_up = run_backup(self.settings.backup_command, self.settings.vault_root)
        except RuntimeError:
            write_runtime_event(
                self.settings.state_root,
                "backup_failure",
                session_id=session_id,
            )
        else:
            write_runtime_event(
                self.settings.state_root,
                "backup_completed" if backed_up else "backup_disabled",
                session_id=session_id,
            )

    def watch(self) -> None:
        while True:
            result = self.run_once()
            if result.state in {"idle", "configuration_wait"}:
                time.sleep(self.settings.worker_poll_seconds)
