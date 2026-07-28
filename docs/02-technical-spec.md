# Technical Spec

## Architecture Overview

Use a layered architecture in which Markdown is the source of truth and every intelligent/retrieval capability is disposable. Codex hooks provide lifecycle integration; a Python worker performs all slow or network-dependent work outside the hook timeout.

```text
Codex SessionStart --> context selector --> global + project pack --> Codex
       |
Codex SessionEnd --> global hook --> persistent local queue --> systemd worker
                                                            |       |
                                                            |       +--> DeepSeek V4 Flash
                                                            v
                                                   Markdown vault + Git --> optional restic backup
```

The hook is global in `~/.codex/hooks.json`. It applies to trusted Git projects beneath configured allowed roots and explicitly allowlisted non-project directories. Denied roots and `.codex/agent-memory.toml` with `enabled = false` take precedence. The initial interface is `SessionStart` context injection and `SessionEnd` capture; MCP is deferred.

## Tech Stack

### Decision Drivers

- Privacy, local operation, and portability matter more than automatic recall volume.
- The information must remain useful to humans in Obsidian and to multiple LLMs.
- The owner wants low operational cost and controllable access.
- Memory quality and provenance are more important than a flashy vector search demo.

### Confirmed Tech Stack

| Area | Choice | Status | Rationale |
| --- | --- | --- | --- |
| Canonical data | Markdown with YAML frontmatter, Obsidian-compatible | Confirmed | Portable, inspectable, recoverable without services. |
| Runtime | Python 3.14 with `uv` | Confirmed | Available locally and well suited to hook, queue, validation, and system service code. |
| HTTP/schema | `httpx`, Pydantic, PyYAML | Confirmed | Small mature dependencies for direct provider calls and strict local validation. |
| Capture integration | Global Codex `SessionEnd` and `SessionStart` command hooks | Confirmed | Captures transcript references and injects context at supported lifecycle events. |
| Background jobs | User-level `systemd` service plus persistent filesystem queue | Confirmed | Survives hook timeout, network failures, logout, and reboot. |
| Classifier | DeepSeek `deepseek-v4-flash`, JSON output, non-thinking mode | Confirmed | Cheap structured classification; no native Codex-provider coupling. |
| Retrieval | Deterministic selector over active Markdown notes | Confirmed | Predictable, cited, and cheaper than RAG for v1. |
| Versioning | Local Git, one commit per successful session batch | Confirmed | Exact change history and source auditability. |
| Secret controls | Local redaction, Gitleaks, schema/link linting | Confirmed | Blocks sensitive data before network submission or commits. |
| Backup | `restic`, encrypted object storage when configured | Confirmed | Keeps backup provider separate from canonical data and Git. |
| Client/UI | Obsidian | Confirmed | Human inspection and correction without building a UI. |
| Auth | Local user permissions; environment-file secrets | Confirmed | Single owner and no network listener in v1. |
| MCP/vector DB | Not applicable in v1 | Confirmed | Add only after measured deterministic-retrieval failures. |
| Competing memory | Codex native memory generation/injection disabled | Confirmed | The Obsidian vault must be the only authoritative and injected memory layer. |

### Alternatives Considered

- Obsidian-plugin-first capture: rejected because Codex hooks already provide the needed lifecycle entry points.
- Vector database-first retrieval: deferred because it adds opaque recall and operations before the note corpus is proven.
- Codex as the classifier: rejected because a session-ending hook needs a cheap external runner and must avoid recursive Codex work.
- Manual approval inbox: rejected in favor of automatic promotion constrained to explicit user statements and verified outcomes.

### Consequences

- Automatic promotion requires strict local redaction, schema validation, idempotency, audit records, and stale-memory handling.
- A configured provider token-cost table must be reviewed when DeepSeek pricing changes.
- Object storage is optional at deployment time; the backup command is inactive until the owner provides a destination.

### Sources

- [Codex Hooks](https://learn.chatgpt.com/docs/hooks)
- [Codex Memories](https://learn.chatgpt.com/docs/customization/memories)
- [DeepSeek Create Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion)
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)

## Data Model

Each memory note uses YAML frontmatter such as:

```yaml
id: pref-terminal-appearance
type: preference # preference | decision | project-state | runbook | fact | lesson
status: active # active | stale | superseded | archived
scope: global # global | project:<slug>
source:
  kind: user-confirmed # user-confirmed | verified-outcome | seeded-document
  reference: "codex-session:<session-id>"
  transcript_sha256: "..."
evidence:
  excerpt: "Redacted, short supporting statement."
created: 2026-07-24
review_after: 2027-01-24
priority: high
```

Proposed paths:

```text
00-system/        policy, schema, capture rules, source manifests
10-global/        stable owner preferences and environment context
20-projects/      one dossier per active project
30-runbooks/      verified operational instructions
40-decisions/     cross-project decisions and their rationale
80-audit/         non-sensitive block, retry, budget, and backup events
90-quarantine/    malformed classifier output retained only when safe
99-archive/       superseded or retired notes
```

`10-global/agent-context.md` is intentionally short and links outward; it is not a dumping ground. Each project dossier begins with `context.md`, `decisions.md`, and `current-state.md`. Runtime queue data, logs, API keys, and raw transcripts live outside the repository under the user's state/config directories.

## API Design

The implementation exposes local CLI interfaces only:

- `memory-hook session-end`: reads Codex hook JSON from stdin and enqueues an idempotent job.
- `memory-context --hook`: reads Codex `SessionStart` JSON from stdin and emits `hookSpecificOutput.additionalContext` containing the bounded context and source manifest.
- `memory-worker`: drains the queue, calls the classifier, validates/writes notes, commits, and backs up.
- `memory-seed`: creates initial approved notes from the defined seed sources.

No HTTP server, MCP server, or remote write API exists in v1.

`SessionStart` matches `startup|resume|clear|compact` and uses
`additionalContextLimit = 5000`. `SessionEnd` uses the documented three-second
maximum and performs only transcript hashing plus an atomic queue write.
Because Codex documents the transcript file format as unstable, JSONL parsing is
isolated behind a version-tolerant adapter and fails closed when no supported
messages can be extracted.

## Key Components

- **Memory policy:** eligibility, sensitivity, expiry, and correction rules.
- **Canonical notes:** approved Markdown records with stable IDs and metadata.
- **Curated indexes:** low-token entry points that link to active details.
- **Project dossiers:** isolated, up-to-date context for each project.
- **Hook adapter:** fast global command-hook entry points for session start/end.
- **Queue and worker:** persistent, idempotent processing outside Codex hook limits.
- **Redactor/classifier:** deterministic local filtering followed by structured DeepSeek extraction.
- **Validator:** future checks for required metadata, broken links, duplicate IDs, stale notes, and secrets.
- **Selector:** bounded active-note retrieval that emits citations/manifest.
- **Audit writer:** records blocked, retried, stale, budget-paused, and backup events without secrets.

## State Management

The note status is authoritative. Optional indexes can be regenerated from active Markdown notes. Queue job identity is `(session_id, transcript_sha256)`; completed identities cannot write a second commit. Git records content changes; it is not an authorization system.

## Auth & Permissions

Local filesystem permissions restrict the vault to Bruno. The DeepSeek key and future `restic` credentials are held in a mode-600 environment file outside the repo. The worker sends only locally redacted excerpts to DeepSeek. Hosted-LM use is fixed to this narrowly scoped classifier call in v1.

## Error Handling

- Missing or malformed classifier JSON or metadata: keep the job queued/retry it; never partially write a note.
- Conflicting active facts: supersede only when newer evidence is an explicit user statement; otherwise reject and audit.
- Oversized context: return the index/manifest and ask for narrower scope rather than truncating arbitrarily.
- Suspected secret or out-of-scope content: block promotion and cloud submission, then retain only a non-sensitive audit event.
- Budget exhausted: pause API calls and retain jobs until the next budget period or configuration change.
- Backup unavailable: keep the Git commit and retry backup without rolling back canonical memory.

## Testing Strategy

Test unit-level transcript parsing/redaction, eligibility, schema validation, deduplication, supersession, stale status, token budgets, and cost accounting. Test integration with a fake DeepSeek client and a temporary Git repository. Test hook payloads, systemd queue recovery, budget pause, opt-out, and backup command invocation separately.

## Deployment / Operations

The vault is a local Git directory opened by Obsidian. A user-level `systemd` service is always on while the user session is active. Installation updates Codex configuration with timestamped backups, disables `features.memories`, `memories.generate_memories`, and `memories.use_memories`, and installs global hooks that still require Codex trust review. `restic` backs up after each successful commit only when the owner configures an object-storage repository; no public Git remote is permitted.

## Technical Risks

- **Context bloat:** controlled by small indexes, quotas, and project scoping.
- **False/stale memories:** controlled by narrow eligibility, source evidence, review dates, supersession, and automatic stale exclusion.
- **Secret leakage:** controlled by narrow eligibility, scanning, and no transcript dumps.
- **Tool lock-in:** controlled by Markdown as canonical format.
- **Provider outage/cost:** controlled by persistent queue, retries, and a US$5 monthly cap.
- **Overengineering RAG:** deferred until deterministic retrieval shows measurable limits.
