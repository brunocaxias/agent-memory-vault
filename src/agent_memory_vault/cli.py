from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_settings
from .gitops import initialize_vault_repository
from .hooks import run_pre_compact, run_session_end, run_session_start, run_user_prompt_submit
from .installer import install_user_files
from .projections import rebuild_projections
from .queue import FileQueue
from .seed import initialize_vault
from .validation import validate_vault
from .worker import MemoryWorker


def context_main() -> int:
    parser = argparse.ArgumentParser(description="Emit bounded persistent memory context")
    parser.add_argument("--hook", action="store_true", help="read a SessionStart hook from stdin")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    settings = load_settings(args.config)
    if not args.hook:
        parser.error("--hook is required; direct context inspection is available via memory-vault")
    return run_session_start(settings)


def hook_main() -> int:
    parser = argparse.ArgumentParser(description="Codex lifecycle hook adapter")
    parser.add_argument("event", choices=["session-end", "pre-compact", "user-prompt-submit"])
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    settings = load_settings(args.config)
    if args.event == "session-end":
        return run_session_end(settings)
    if args.event == "pre-compact":
        return run_pre_compact(settings)
    return run_user_prompt_submit(settings)


def worker_main() -> int:
    parser = argparse.ArgumentParser(description="Process persistent memory jobs")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    settings = load_settings(args.config)
    worker = MemoryWorker(settings)
    if args.watch:
        worker.watch()
        return 0
    result = worker.run_once()
    print(json.dumps(result.__dict__))
    return 0 if result.state not in {"failed"} else 1


def seed_main() -> int:
    parser = argparse.ArgumentParser(description="Initialize approved vault structures")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    settings = load_settings(args.config)
    created = initialize_vault(settings)
    print(json.dumps({"created": [str(path) for path in created]}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Agent Memory Vault")
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install", help="install user hooks and service files")
    install_parser.add_argument("--config", type=Path)
    install_parser.add_argument(
        "--executable-directory",
        type=Path,
        default=Path(sys.executable).parent,
    )
    status_parser = subparsers.add_parser("status", help="show queue and configuration status")
    status_parser.add_argument("--config", type=Path)
    resume_parser = subparsers.add_parser("resume-budget", help="resume budget-paused jobs")
    resume_parser.add_argument("--config", type=Path)
    validate_parser = subparsers.add_parser("validate", help="validate canonical memory notes")
    validate_parser.add_argument("--config", type=Path)
    rebuild_parser = subparsers.add_parser(
        "rebuild-projections", help="regenerate all fluid agent projections"
    )
    rebuild_parser.add_argument("--config", type=Path)
    curator_parser = subparsers.add_parser(
        "curate", help="report proposal-only memory maintenance findings"
    )
    curator_parser.add_argument("--config", type=Path)
    curator_parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    settings = load_settings(getattr(args, "config", None))
    if args.command == "install":
        initialize_vault(settings)
        initialize_vault_repository(settings.vault_root)
        result = install_user_files(settings, args.executable_directory.resolve())
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "status":
        queue = FileQueue(settings.state_root)
        counts = {state: len(list((queue.root / state).glob("*.json"))) for state in queue.STATES}
        print(
            json.dumps(
                {
                    "vault_root": str(settings.vault_root),
                    "state_root": str(settings.state_root),
                    "queue": counts,
                },
                indent=2,
            )
        )
        return 0
    if args.command == "resume-budget":
        count = FileQueue(settings.state_root).resume_budget_jobs()
        print(json.dumps({"resumed": count}))
        return 0
    if args.command == "validate":
        issues = validate_vault(settings.vault_root)
        print(json.dumps([issue.__dict__ for issue in issues], indent=2))
        return 1 if issues else 0
    if args.command == "rebuild-projections":
        changed = rebuild_projections(settings.vault_root)
        print(json.dumps({"changed": [str(path) for path in changed]}, indent=2))
        return 0
    if args.command == "curate":
        from .curator import curate_vault, write_curator_report

        report = curate_vault(settings.vault_root)
        path = (
            write_curator_report(settings.vault_root, report)
            if args.write_report and report.findings
            else None
        )
        if path is not None:
            from .gitops import commit_memory_batch

            commit_memory_batch(settings.vault_root, f"curator-{report.generated_on.isoformat()}")
        print(
            json.dumps(
                {
                    "findings": [item.__dict__ for item in report.findings],
                    "report": str(path or ""),
                },
                indent=2,
            )
        )
        return 0
    return 2
