from __future__ import annotations

import subprocess
from datetime import date, timedelta
from pathlib import Path

from agent_memory_vault.gitops import commit_memory_batch
from agent_memory_vault.models import CandidateMemory, QueueJob
from agent_memory_vault.validation import validate_vault
from agent_memory_vault.vault import Vault


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
