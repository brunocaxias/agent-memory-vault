from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .paths import codex_home


@dataclass(frozen=True)
class CaptureContext:
    eligible: bool
    cwd: Path
    project_root: Path | None
    project_slug: str | None
    reason: str


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def find_git_root(path: Path) -> Path | None:
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def project_opted_out(project_root: Path) -> bool:
    optout = project_root / ".codex/agent-memory.toml"
    if not optout.exists():
        return False
    try:
        with optout.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError, tomllib.TOMLDecodeError:
        return True
    return data.get("enabled") is False


def trusted_codex_project(project_root: Path) -> bool:
    config_path = codex_home() / "config.toml"
    if not config_path.exists():
        return False
    try:
        with config_path.open("rb") as handle:
            config = tomllib.load(handle)
    except OSError, tomllib.TOMLDecodeError:
        return False

    configured = config.get("projects", {})
    trusted_roots: list[Path] = []
    for raw_path, values in configured.items():
        if isinstance(values, dict) and values.get("trust_level") == "trusted":
            trusted_roots.append(Path(raw_path).expanduser().resolve())
    return any(is_within(project_root, root) for root in trusted_roots)


def resolve_capture_context(cwd: Path, settings: Settings) -> CaptureContext:
    path = cwd.expanduser().resolve()
    if any(is_within(path, root) for root in settings.denied_roots):
        return CaptureContext(False, path, None, None, "cwd is under a denied root")

    if any(is_within(path, root) for root in settings.allowed_non_project_roots):
        return CaptureContext(True, path, None, None, "allowlisted non-project directory")

    project_root = find_git_root(path)
    if project_root is not None:
        if not any(is_within(project_root, root) for root in settings.allowed_project_roots):
            return CaptureContext(
                False, path, project_root, None, "project is outside allowed roots"
            )
        if not trusted_codex_project(project_root):
            return CaptureContext(
                False, path, project_root, None, "project is not trusted by Codex"
            )
        if project_opted_out(project_root):
            return CaptureContext(False, path, project_root, None, "project opted out")
        return CaptureContext(
            True, path, project_root, project_root.name, "trusted allowed project"
        )

    return CaptureContext(False, path, None, None, "non-project directory is not allowlisted")
