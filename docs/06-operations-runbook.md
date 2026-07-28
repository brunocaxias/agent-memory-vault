# Operations Runbook

## Install

```bash
cd /mnt/Dump/Coding/Projects/agent-memory-vault
uv sync --extra dev
uv run memory-vault install
systemctl --user daemon-reload
systemctl --user enable --now agent-memory-vault.service
```

The installer creates timestamped backups before modifying existing Codex
configuration or hooks.

## Required Manual Steps

1. Put the DeepSeek key in
   `~/.config/agent-memory-vault/agent-memory-vault.env`.
2. Keep that file mode `600`.
3. Restart Codex, run `/hooks`, inspect the exact SessionStart and SessionEnd
   commands, and trust them.
4. Add any approved non-project directory to
   `allowed_non_project_roots` in the application configuration.

Without a classifier key, capture jobs remain queued in
`configuration_wait`; they are not discarded.

## Inspect

```bash
memory-vault status
systemctl --user status agent-memory-vault.service
journalctl --user -u agent-memory-vault.service
```

Runtime queue and logs live under the XDG user-state directory, outside the
Obsidian vault. Canonical notes and non-sensitive audits live in the vault.

## Recovery

- Provider outage: jobs retry with exponential backoff.
- Budget pause: review cost configuration, then run
  `memory-vault resume-budget`.
- Hook failure: inspect `/hooks`, the user journal, and runtime `events.jsonl`.
- Incorrect memory: edit, supersede, archive, or delete the Markdown note and
  commit the correction normally.
- Backup failure: the local Git commit remains canonical; retry the configured
  backup independently.

## Uninstall or Disable

Disable the service and remove only the two Agent Memory Vault hook definitions.
Re-enable Codex native memories only if returning to that memory layer. Preserve
the Obsidian vault and Git history unless explicitly choosing to delete them.

