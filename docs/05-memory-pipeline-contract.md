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
- an unexpired project handoff, capped at 800 tokens;
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

### PreCompact and UserPromptSubmit

`PreCompact` uses the same scope checks and queue-only capture path as
`SessionEnd`; it is a checkpoint before Codex summarizes history. `UserPromptSubmit`
never writes: it rebuilds/queries a local FTS5 index from active canonical Markdown,
then combines lexical, entity, concept, relation, scope, lifecycle, and authority
signals into a 1,200-token source-cited context pack.

## Worker Contract

The user-level systemd worker drains persistent jobs one at a time. For each job it:

1. Reads the original transcript at processing time; if unavailable, marks the job source-unavailable in audit.
2. Extracts deterministic local candidates: explicit user statements and verified task results only.
3. Applies scope filtering and secret detection/redaction before any cloud request.
4. Sends a concise JSON-oriented prompt containing local summary and selected redacted excerpts to `deepseek-v4-flash`.
5. Validates JSON, eligibility, evidence, note metadata, duplicate IDs, links, and secrets locally.
6. Writes canonical notes and audit records atomically, then deterministically
   rebuilds fluid agent projections.
7. Commits one successful session batch to local Git.
8. Attempts encrypted backup if configured; backup failure does not revert the commit.

Retries use exponential backoff for provider/network/temporary validation failures. The worker stops new API calls when the configurable monthly estimate reaches US$5, retaining jobs in `budget_paused` state.

## Classifier Output Contract

The model must return one JSON object containing a `memories` array and optional
`handoff` object. Every memory item requires:

```json
{
  "type": "preference | decision | project-state | runbook | fact | lesson",
  "scope": "global | project:<slug>",
  "content": "short durable statement",
  "eligibility": "explicit-user-statement | verified-project-outcome",
  "evidence_excerpt": "redacted supporting excerpt",
  "supersedes_id": "optional stable note id",
  "review_after": "YYYY-MM-DD",
  "entities": ["up to 12 grounded named labels"],
  "concepts": ["up to 12 grounded durable topics"],
  "effective_from": "optional YYYY-MM-DD",
  "effective_to": "optional YYYY-MM-DD",
  "relations": [{"type": "requires", "target": "entity or memory id", "target_kind": "entity | concept | memory"}]
}
```

The local validator, not the model, assigns IDs, status, timestamps, source references, transcript hash, and priority. Empty arrays are valid. Any inferred, speculative, secret-bearing, or out-of-scope item is rejected and is not converted into a note.

## Storage Layer Contract

The canonical vault is
`/mnt/Dump/Obsidian/Vaults/Agent-Memory`. The application repository is not a
vault and must never be used as the MCP root.

Canonical scan roots are `10-global`, `20-projects`, `30-runbooks`, and
`40-decisions`. Only valid `MemoryRecord` files in those roots may enter
`SessionStart` context.

`60-handoffs/<project>.md` is an expiring, non-canonical session-continuity
record. It is overwritten atomically from redacted classifier output, expires
after seven days by default, and is never used as evidence for canonical memory.

`70-projections` is a generated boundary:

- `manifest.md`: layer contract, counts, and agent entry points;
- `active-memory-index.md`: active global/project records;
- `projects/<slug>.md`: type-grouped project dossiers;
- `entities.md` and `concepts.md`: shared-label navigation;
- `relations.md`: typed relation edges;
- `supersession.md`: explicit lifecycle edges.

Every projection declares `kind: agent-projection`, `generated: true`, and
`canonical: false`. The builder removes obsolete Markdown only inside
`70-projections`, writes changed projections atomically, and is idempotent.
Validation reports missing, unexpected, or outdated projections. Agents follow
projection links to canonical notes before relying on provenance or lifecycle
status.

## Configuration Boundary

### MCP Access Boundary

The installer adds one local STDIO server to `~/.codex/config.toml`:

- name: `agent_memory_vault`;
- command: `npx -y @bitbonsai/mcpvault@0.12.4 <vault-root>`;
- enabled tools: `read_note`, `read_multiple_notes`, `search_notes`,
  `get_frontmatter`, `get_notes_info`, `get_vault_stats`, `list_directory`,
  `list_all_tags`, and `wiki_link`;
- default approval mode: `auto`, safe only because the enabled-tool allowlist
  contains no mutation tool;
- `required = false`, so MCP startup failure cannot block Codex startup.

MCPVault never participates in SessionEnd capture, classification, promotion,
stale handling, audit, or Git commits. It may return note content to a client
model on demand. The client/provider data boundary therefore applies to every
note selected through MCP even though the server itself is local.

- Global behavior: `~/.codex/hooks.json` and `~/.config/agent-memory-vault/config.toml`.
- Read-only client access: the managed `agent_memory_vault` table in `~/.codex/config.toml`.
- Secrets: a mode-600 environment file outside the repository, loaded only by the worker service.
- Project exclusion: `.codex/agent-memory.toml` with `enabled = false`.
- Capture allowlists and deny roots: global Agent Memory Vault configuration.
- Codex native memory: `features.memories`,
  `memories.generate_memories`, and `memories.use_memories` are disabled.
- Runtime queue/logs: an XDG user state directory outside the canonical vault.
- Fluid views: `70-projections`, rebuilt with
  `memory-vault rebuild-projections`.
- Backup: `restic` repository and object-storage credentials are optional configuration. Until configured, backup is logged as disabled.

## Review and Audit Rules

- Project state is reviewed after 30 days; decisions and runbooks after 180; global preferences and stable facts after 365.
- An overdue note is marked `stale` and remains inspectable but is not automatically injected.
- A direct newer user statement may supersede an active note. Other apparent conflicts are rejected and audited.
- `memory-vault curate` only reports deterministic maintenance proposals; it never rewrites canonical records.
- Audit records must never contain raw transcripts, API keys, detected secret values, or unredacted snippets.
