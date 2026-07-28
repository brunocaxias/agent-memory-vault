# Agent Memory Vault

A local-first persistent memory layer for Codex. It captures eligible completed
Codex sessions, stores durable memories as Obsidian-compatible Markdown, and
injects bounded global and project context into later sessions.

The Markdown vault is authoritative. Codex's built-in generated memories should
be disabled when this system is installed.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

## Local installation

```bash
uv sync --extra dev
uv run memory-vault install
```

The installer writes user configuration, Codex hooks, and a user-level systemd
unit. It creates timestamped backups before modifying existing files.

The classifier remains safely paused until `DEEPSEEK_API_KEY` is placed in the
mode-600 environment file printed by the installer.

See [`docs/`](docs/) for the product and pipeline contracts.

