from __future__ import annotations

import subprocess
from datetime import date, timedelta
from pathlib import Path

from agent_memory_vault.curator import curate_vault, render_curator_report
from agent_memory_vault.gitops import commit_memory_batch, initialize_vault_repository
from agent_memory_vault.models import CandidateMemory, MemoryRecord, MemoryRelation, QueueJob
from agent_memory_vault.validation import validate_vault
from agent_memory_vault.vault import Vault, render_record


def test_validate_clean_vault(settings, tmp_path: Path) -> None:
    candidate = CandidateMemory(
        type="fact",
        scope="global",
        content="The services host runs Linux.",
        eligibility="explicit-user-statement",
        evidence_excerpt="The services host runs Linux.",
        review_after=date.today() + timedelta(days=365),
    )
    job = QueueJob(
        id="job",
        session_id="session",
        transcript_path=tmp_path / "rollout.jsonl",
        transcript_sha256="f" * 64,
        cwd=tmp_path,
    )
    Vault(settings.vault_root).write_batch([candidate], job)
    assert validate_vault(settings.vault_root) == []


def test_git_commit_only_canonical_memory_paths(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Memory Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "memory@example.invalid"],
        check=True,
    )
    (root / "10-global").mkdir()
    (root / "10-global/memory.md").write_text("memory\n", encoding="utf-8")
    (root / "unrelated.txt").write_text("do not stage\n", encoding="utf-8")
    assert commit_memory_batch(root, "session-1")
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert tracked == ["10-global/memory.md"]


def test_initialize_vault_repository_commits_managed_layers(
    settings, monkeypatch
) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Memory Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "memory@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Memory Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "memory@example.invalid")
    Vault(settings.vault_root).initialize()

    assert initialize_vault_repository(settings.vault_root)
    assert not initialize_vault_repository(settings.vault_root)
    status = subprocess.run(
        ["git", "-C", str(settings.vault_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""
    tracked = subprocess.run(
        ["git", "-C", str(settings.vault_root), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "00-system/memory-schema.md" in tracked
    assert "70-projections/manifest.md" in tracked


def test_validation_detects_projection_drift(settings, tmp_path: Path) -> None:
    candidate = CandidateMemory(
        type="fact",
        scope="global",
        content="The vault is local.",
        eligibility="explicit-user-statement",
        evidence_excerpt="The vault is local.",
        review_after=date.today() + timedelta(days=365),
    )
    job = QueueJob(
        id="job-projection",
        session_id="session-projection",
        transcript_path=tmp_path / "rollout.jsonl",
        transcript_sha256="e" * 64,
        cwd=tmp_path,
    )
    Vault(settings.vault_root).write_batch([candidate], job)
    projection = settings.vault_root / "70-projections/active-memory-index.md"
    projection.write_text("tampered\n", encoding="utf-8")

    issues = validate_vault(settings.vault_root)

    assert any(issue.code == "outdated-projection" for issue in issues)


def test_curator_only_reports_stale_and_dangling_relation(settings, tmp_path: Path) -> None:
    candidate = CandidateMemory(
        type="fact",
        scope="global",
        content="The legacy integration is expired.",
        eligibility="explicit-user-statement",
        evidence_excerpt="The legacy integration is expired.",
        review_after=date.today() - timedelta(days=1),
        relations=[MemoryRelation(type="uses", target="missing-memory", target_kind="memory")],
    )
    record = MemoryRecord(
        id="legacy-integration",
        type=candidate.type,
        status="active",
        scope=candidate.scope,
        source={"kind": candidate.eligibility, "reference": "test", "transcript_sha256": "a" * 64},
        evidence={"excerpt": candidate.evidence_excerpt},
        created=date.today(),
        review_after=candidate.review_after,
        relations=candidate.relations,
        content=candidate.content,
    )
    path = settings.vault_root / "10-global/memories/legacy-integration.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_record(record), encoding="utf-8")

    report = curate_vault(settings.vault_root)

    assert {finding.code for finding in report.findings} >= {"stale-review", "dangling-relation"}
    assert "proposal_only: true" in render_curator_report(report)
    assert path.read_text(encoding="utf-8") == render_record(record)
