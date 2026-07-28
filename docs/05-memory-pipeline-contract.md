# Memory Pipeline Contract

## Purpose

This document fixes the v1 boundary between Codex hooks, the local worker, DeepSeek, and canonical Markdown. It is implementation guidance, not runtime configuration.

## Hook Contract

### SessionStart

The global hook invokes `memory-context --hook`, which reads the Codex event JSON
from stdin. If the current context is eligible, stdout returns
`hookSpecificOutput.additionalContext` containing:

- global context, capped at 1,500 tokens;
- project context, capped at 3,000 tokens;
- a compact manifest of included source notes.

Only `active` notes are eligible. `stale`, `superseded`, and `archived` notes are
excluded. Absence of a dossier returns only global context and does not fail
Codex. The hook matches `startup`, `resume`, `clear`, and `compact`.

### SessionEnd

The global hook receives Codex JSON containing `session_id`, `transcript_path`, `cwd`, `reason`, and `hook_event_name`. It must:

1. Resolve the Git root and apply the trusted-project and opt-out predicates.
2. Hash the referenced transcript without copying it into the vault.
3. Persist an idempotent queue job keyed by `(session_id, transcript_sha256)`.
4. Exit successfully within the three-second Codex SessionEnd maximum.

It must not call DeepSeek, write canonical notes, create Git commits, or run backup itself.

## Worker Contract

The user-level systemd worker drains persistent jobs one at a time. For each job it:

1. Reads the original transcript at processing time; if unavailable, marks the job source-unavailable in audit.
2. Extracts deterministic local candidates: explicit user statements and verified task results only.
3. Applies scope filtering and secret detection/redaction before any cloud request.
4. Sends a concise JSON-oriented prompt containing local summary and selected redacted excerpts to `deepseek-v4-flash`.
5. Validates JSON, eligibility, evidence, note metadata, duplicate IDs, links, and secrets locally.
6. Creates a minimum project dossier if needed; writes notes, indexes, and audit records atomically.
7. Commits one successful session batch to local Git.
8. Attempts encrypted backup if configured; backup failure does not revert the commit.

Retries use exponential backoff for provider/network/temporary validation failures. The worker stops new API calls when the configurable monthly estimate reaches US$5, retaining jobs in `budget_paused` state.

## Classifier Output Contract

The model must return one JSON object containing a `memories` array. Every item requires:

```json
{
  "type": "preference | decision | project-state | runbook | fact | lesson",
  "scope": "global | project:<slug>",
  "content": "short durable statement",
  "eligibility": "explicit-user-statement | verified-project-outcome",
  "evidence_excerpt": "redacted supporting excerpt",
  "supersedes_id": "optional stable note id",
  "review_after": "YYYY-MM-DD"
}
```

The local validator, not the model, assigns IDs, status, timestamps, source references, transcript hash, and priority. Empty arrays are valid. Any inferred, speculative, secret-bearing, or out-of-scope item is rejected and is not converted into a note.

## Configuration Boundary

- Global behavior: `~/.codex/hooks.json` and `~/.config/agent-memory-vault/config.toml`.
- Secrets: a mode-600 environment file outside the repository, loaded only by the worker service.
- Project exclusion: `.codex/agent-memory.toml` with `enabled = false`.
- Capture allowlists and deny roots: global Agent Memory Vault configuration.
- Codex native memory: `features.memories`,
  `memories.generate_memories`, and `memories.use_memories` are disabled.
- Runtime queue/logs: an XDG user state directory outside the canonical vault.
- Backup: `restic` repository and object-storage credentials are optional configuration. Until configured, backup is logged as disabled.

## Review and Audit Rules

- Project state is reviewed after 30 days; decisions and runbooks after 180; global preferences and stable facts after 365.
- An overdue note is marked `stale` and remains inspectable but is not automatically injected.
- A direct newer user statement may supersede an active note. Other apparent conflicts are rejected and audited.
- Audit records must never contain raw transcripts, API keys, detected secret values, or unredacted snippets.
