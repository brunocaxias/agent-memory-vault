# Agent Memory Vault

A local-first persistent memory layer for Codex. It captures eligible completed
Codex sessions, stores durable memories as Obsidian-compatible Markdown, and
injects bounded global and project context into later sessions.

The Markdown vault is authoritative. Codex's built-in generated memories should
be disabled when this system is installed.

The software repository and memory vault are separate. The default canonical
vault is `/mnt/Dump/Obsidian/Vaults/Agent-Memory`. Canonical source-cited
records remain stable, while deterministic views under `70-projections` are
fluid and rebuildable for agent navigation.

Automatic augmentation has three bounded layers: stable global/project memory
at `SessionStart`, an expiring per-project handoff from the last redacted work
session, and a prompt-relevant pack selected locally at `UserPromptSubmit`.
The local SQLite FTS5 index is disposable state rebuilt from canonical Markdown;
it is never a second source of truth. `PreCompact` only queues a checkpoint so
continuity survives context compression without delaying Codex.

The installer also configures the pinned MCPVault package as a local STDIO MCP
server for ad-hoc reading and BM25 search. Its Codex tool allowlist is strictly
read-only; all canonical memory writes still pass through the hook, worker,
redaction, validation, audit, and Git pipeline.

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
unit. It also adds the read-only `agent_memory_vault` MCP server to Codex. It
creates timestamped backups before modifying existing files, initializes the
separate vault, and creates its private local Git repository when needed.

Regenerate all agent-facing indexes, project dossiers, entity/concept views, and
supersession relationships at any time:

```bash
uv run memory-vault rebuild-projections
uv run memory-vault curate
```

Node.js 20 or newer and `npx` are required for MCPVault. Restart Codex after
installation, then run `/mcp` or `codex mcp get agent_memory_vault` to inspect
the configured server and tool policy.

`memory-vault curate --write-report` writes a proposal-only maintenance report
only when deterministic issues are found. The installer also writes a daily
user-systemd timer for that command; enable it after review with
`systemctl --user enable --now agent-memory-vault-curator.timer`.

The classifier remains safely paused until `DEEPSEEK_API_KEY` is placed in the
mode-600 environment file printed by the installer.

See [`docs/`](docs/) for the product and pipeline contracts.
