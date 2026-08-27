from __future__ import annotations

import subprocess
from pathlib import Path

MANAGED_PATHS = (
    "00-system",
    "10-global",
    "20-projects",
    "30-runbooks",
    "40-decisions",
    "60-handoffs",
    "70-projections",
    "80-audit",
    "90-quarantine",
    "99-archive",
)


class GitError(RuntimeError):
    pass


def _run(
    root: Path,
    arguments: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=check,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise GitError(f"git {' '.join(arguments)} failed") from exc


def commit_memory_batch(root: Path, session_id: str) -> bool:
    if not (root / ".git").exists():
        raise GitError("vault is not a Git repository")
    existing = [name for name in MANAGED_PATHS if (root / name).exists()]
    if not existing:
        return False
    _run(root, ["add", "--", *existing])
    staged = _run(root, ["diff", "--cached", "--quiet"], check=False)
    if staged.returncode == 0:
        return False
    if staged.returncode != 1:
        raise GitError("could not inspect staged memory changes")
    safe_session = "".join(c for c in session_id if c.isalnum() or c in "-_")[:48]
    _run(root, ["commit", "-m", f"memory: capture {safe_session}"])
    return True


def initialize_vault_repository(root: Path) -> bool:
    root.mkdir(parents=True, exist_ok=True)
    created = not (root / ".git").exists()
    if created:
        _run(root, ["init"])
    has_head = _run(root, ["rev-parse", "--verify", "HEAD"], check=False)
    if has_head.returncode == 0:
        return created
    if has_head.returncode not in {1, 128}:
        raise GitError("could not inspect initial vault repository")
    initial = [name for name in MANAGED_PATHS if (root / name).exists()]
    if (root / ".gitignore").exists():
        initial.insert(0, ".gitignore")
    if initial:
        _run(root, ["add", "--", *initial])
        staged = _run(root, ["diff", "--cached", "--quiet"], check=False)
        if staged.returncode == 1:
            _run(root, ["commit", "-m", "memory: initialize vault"])
        elif staged.returncode != 0:
            raise GitError("could not inspect initial vault changes")
    return created


def run_backup(command: list[str], root: Path) -> bool:
    if not command:
        return False
    try:
        subprocess.run(command, cwd=root, check=True, timeout=600)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError("backup command failed") from exc
    return True
