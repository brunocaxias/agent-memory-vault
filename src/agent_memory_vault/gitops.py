from __future__ import annotations

import subprocess
from pathlib import Path

CANONICAL_PATHS = (
    "00-system",
    "10-global",
    "20-projects",
    "30-runbooks",
    "40-decisions",
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
    existing = [name for name in CANONICAL_PATHS if (root / name).exists()]
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


def run_backup(command: list[str], root: Path) -> bool:
    if not command:
        return False
    try:
        subprocess.run(command, cwd=root, check=True, timeout=600)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError("backup command failed") from exc
    return True
