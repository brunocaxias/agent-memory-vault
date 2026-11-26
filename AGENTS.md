# Repository guidance

- Python package: `src/agent_memory_vault`; tests: `tests`; configuration examples:
  `config`; lifecycle templates: `hooks` and `systemd`; contracts: `00-system` and `docs`.
- Setup: `uv sync --extra dev`. Validate: `uv run pytest` and `uv run ruff check .`.
- Keep CLI behavior in `cli.py`, configuration in `config.py`/`paths.py`, and memory
  writes behind worker validation, audit, and Git handling. Markdown is canonical;
  SQLite retrieval state and projections must remain rebuildable.
- Preserve project eligibility, redaction, scope checks, and budget limits. Keep
  classifier tests mocked; never invoke live provider calls in routine validation.
- Use temporary vault/config/state/Codex/XDG paths in tests. Do not run installation,
  systemd activation, or a worker against a contributor's actual home or transcripts.
- Never commit vaults, transcripts, API keys, runtime queues, audit logs, or derived private context.
- The MCP tool allowlist is read-only in Codex; do not describe it as an OS sandbox.
- A task is complete when relevant tests and Ruff pass, documented commands match the
  parser, and installation or privacy changes are reflected in the README and runbook.
