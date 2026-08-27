# Operations Runbook

## Install

Prerequisites include Python 3.14, `uv`, Node.js 20 or newer, and `npx`.
The application remains in
`/mnt/Dump/Coding/Projects/agent-memory-vault`; the installer creates and uses
`/mnt/Dump/Obsidian/Vaults/Agent-Memory` as the separate canonical vault.

```bash
cd /mnt/Dump/Coding/Projects/agent-memory-vault
uv sync --extra dev
uv run memory-vault install
systemctl --user daemon-reload
systemctl --user enable --now agent-memory-vault.service
systemctl --user enable --now agent-memory-vault-curator.timer
```

The installer creates timestamped backups before modifying existing Codex
configuration or hooks. It pins MCPVault 0.12.4 and configures only its approved
read/search tools. For a new vault, it also initializes a private local Git
repository and commits the schema plus empty projection baseline.

## Required Manual Steps

1. Put the DeepSeek key in
   `~/.config/agent-memory-vault/agent-memory-vault.env`.
2. Keep that file mode `600`.
3. Restart Codex, run `/hooks`, inspect the exact SessionStart, UserPromptSubmit,
   PreCompact, and SessionEnd
   commands, and trust them.
4. Run `/mcp` and inspect `agent_memory_vault`, or run
   `codex mcp get agent_memory_vault` in a terminal. Confirm the package is
   pinned to `@bitbonsai/mcpvault@0.12.4` and only read/search tools are enabled.
5. Add any approved non-project directory to
   `allowed_non_project_roots` in the application configuration.

The DeepSeek key is the only remaining required secret. Never paste it into a
chat, vault note, repository file, or Codex configuration.

Without a classifier key, capture jobs remain queued in
`configuration_wait`; they are not discarded.

## Inspect

```bash
memory-vault status
memory-vault validate
memory-vault rebuild-projections
memory-vault curate
codex mcp list
codex mcp get agent_memory_vault
systemctl --user status agent-memory-vault.service
systemctl --user status agent-memory-vault-curator.timer
journalctl --user -u agent-memory-vault.service
```

Runtime queue and logs live under the XDG user-state directory, outside the
Obsidian vault. Canonical notes and non-sensitive audits live in the vault.
Agent-facing fluid views live under `70-projections`; start discovery at
`70-projections/manifest.md`.
The current per-project handoff is in `60-handoffs/`; it expires automatically
and is never canonical evidence. Local FTS5 retrieval state is under the XDG
state directory and can be deleted/rebuilt from canonical Markdown.

## Recovery

- Provider outage: jobs retry with exponential backoff.
- Budget pause: review cost configuration, then run
  `memory-vault resume-budget`.
- Hook failure: inspect `/hooks`, the user journal, and runtime `events.jsonl`.
- Incorrect memory: edit, supersede, archive, or delete the Markdown note and
  commit the correction normally.
- Backup failure: the local Git commit remains canonical; retry the configured
  backup independently.
- MCP startup failure: verify `node --version`, `npx --version`, network access
  for the first pinned-package fetch, and `codex mcp get agent_memory_vault`.
  Hooks and the worker remain operational while MCP is unavailable.
- Unexpected MCP mutation tool: stop using the server, rerun the installer to
  restore the managed allowlist, and audit `~/.codex/config.toml` before restart.
- Missing/outdated projection: run `memory-vault rebuild-projections`, then
  `memory-vault validate`. Unique information must never be stored only in
  `70-projections`.
- Unhelpful prompt recall: run `memory-vault curate`, verify source labels and
  scope, then delete the local `retrieval/canonical-memory.sqlite3` state file;
  the next prompt rebuilds it from canonical Markdown.

## Uninstall or Disable

Disable the worker and curator timer, remove only the four Agent Memory Vault hook definitions,
and run `codex mcp remove agent_memory_vault` if read-only MCP access is no
longer wanted. Re-enable Codex native memories only if returning to that memory
layer. Preserve the Obsidian vault and Git history unless explicitly choosing
to delete them.
