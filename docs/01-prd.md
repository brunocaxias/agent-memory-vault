# PRD

## Overview

The Agent Memory Vault is a curated, local-first memory layer for Codex-assisted work. It favors small, reliable context packs over unlimited recall. Obsidian is the editor and browser; Markdown is canonical; the v1 pipeline automatically extracts strictly eligible memories from trusted-project Codex sessions.

## User Personas

- **Owner/curator:** defines scope, storage credentials, project exclusions, and corrections; reviews audit records when automation blocks or fails.
- **Codex session:** automatically receives relevant global and project context before work and creates memory candidates when it ends.
- **Background worker:** classifies redacted session excerpts, validates results, writes canonical notes, commits changes, and triggers backup.

## Core User Journeys

1. Codex starts in a trusted project; `SessionStart` injects a compact global pack and that project's active pack.
2. When the session ends, `SessionEnd` enqueues its transcript path and hash without blocking the Codex client.
3. A user-level worker extracts only eligible, locally redacted evidence, calls DeepSeek V4 Flash, validates its JSON, and promotes valid memories automatically.
4. The worker creates a dossier for a new eligible project, commits each successful session batch, and attempts an encrypted backup if configured.
5. Bruno inspects memories and audit records in Obsidian, corrects a note normally, or disables a project with `.codex/agent-memory.toml`.

## Functional Requirements

- FR-001: The system must store canonical memories as UTF-8 Markdown files with YAML frontmatter.
- FR-002: The vault must provide a concise global context entry point for agent-readable preferences, working rules, and stable environment facts.
- FR-003: The vault must organize content into global profile, project dossiers, decisions, operational runbooks, archive, and non-sensitive audit records.
- FR-004: Every durable note must declare `id`, `type`, `status`, `scope`, `source`, `evidence`, `created`, and `review_after`; project-scoped notes must identify the project.
- FR-005: The owner must be able to mark memories as active, superseded, archived, or rejected without deleting provenance.
- FR-006: Retrieval must return a bounded context pack with source files and selection reasons, capped at 1,500 global and 3,000 project tokens.
- FR-007: On `SessionEnd`, the system must queue every eligible trusted-project session for automatic classification and promotion; it must not require a manual approval step.
- FR-008: The system must prevent secret or out-of-scope material from leaving the machine for classification or entering the canonical vault; it must record a non-sensitive audit event instead.
- FR-009: The vault must be directly navigable and editable in Obsidian without requiring an API, database, or embeddings service.
- FR-010: Codex instructions and context manifests must cite source note paths for consequential recommendations or changes.
- FR-011: The system must process queued jobs through a user-level supervised worker with persistent retry and exponential backoff.
- FR-012: The classifier must use DeepSeek V4 Flash through a provider-neutral HTTP runner and require JSON output validated locally.
- FR-013: The system must only promote direct user statements and verified project outcomes/runbooks; model inferences are ineligible.
- FR-014: A confirmed newer fact that contradicts an active fact must supersede the previous note and preserve the link between them.
- FR-015: The system must mark overdue memories `stale` and exclude them from automatic context packs without deleting them.
- FR-016: The system must create a minimum project dossier when it first sees an eligible project.
- FR-017: A project-level `.codex/agent-memory.toml` with `enabled = false` must disable capture and context injection for that project.
- FR-018: The worker must commit a successful memory batch to local Git and then run an encrypted backup attempt.
- FR-019: The DeepSeek classifier must stop accepting new jobs after its configured US$5 monthly budget is reached and leave existing jobs queued.
- FR-020: The seed process must curate only global Codex guidance, approved global memories, and active project documentation; it must not mine old transcripts.
- FR-021: The system must support allowlisted non-project directories in addition to trusted Git projects, while applying explicit deny rules and local opt-outs first.
- FR-022: Installation must disable Codex native memory generation and injection and preserve backups of modified user configuration.
- FR-023: The SessionStart adapter must handle startup, resume, clear, and post-compaction lifecycle events.

## Non-Functional Requirements

- NFR-001: The canonical data format must be vendor-neutral and readable for decades without a proprietary service.
- NFR-002: Normal context retrieval must target no more than 12 Markdown files and respect the fixed v1 budgets of 1,500 global and 3,000 project tokens.
- NFR-003: The default configuration must work offline on this Linux machine.
- NFR-004: No unrestricted cloud upload of vault contents may occur. Only locally redacted, selected session excerpts may reach DeepSeek.
- NFR-005: The system must keep an auditable history of content changes while excluding secrets from Git.
- NFR-006: Retrieval must prefer explicit links, project scope, status, recency, and approved priority before semantic similarity.
- NFR-007: The `SessionEnd` hook must return within its Codex lifecycle timeout by enqueueing work only.
- NFR-008: Queue processing, note writing, Git commits, and backup attempts must be idempotent per session ID and transcript hash.
- NFR-009: API keys, backup credentials, raw transcripts, and unredacted excerpts must remain outside the repository and canonical vault.
- NFR-010: The worker must expose structured local logs and non-sensitive audit events for success, block, retry, budget pause, and backup failure.

## Edge Cases

- A preference changes: write the replacement note, mark the old note `superseded`, and link both.
- A note is valid only temporarily: use `review_after` or `expires` so it does not become silent permanent context.
- An agent's inference is uncertain: reject it as ineligible and record only a non-sensitive audit reason.
- A source conversation contains a secret: capture only the non-sensitive conclusion, never the raw transcript.
- Two projects have conflicting choices: isolate their dossiers; do not elevate either choice to global context.
- The provider returns malformed/empty JSON: preserve the job, retry with backoff, and never partially write memory.
- The monthly budget is exhausted: leave jobs queued until the next accounting period or a configuration increase.
- A source transcript disappears before retry: mark the job failed with a source-unavailable audit event; do not invent a replacement.

## Acceptance Criteria

- AC-001: A clean clone/local copy can be opened as an Obsidian vault and its global context can be read without installing a plugin.
- AC-002: A sample `SessionStart` produces only active, non-stale notes within the 1,500/3,000 token budgets and includes a source manifest.
- AC-003: A reviewer can find every active note that is overdue for review using metadata/search.
- AC-004: A direct user statement or verified project outcome from a completed session becomes active automatically after validation and is committed once.
- AC-005: A test secret pattern blocks cloud submission and note creation while recording a non-sensitive audit event.
- AC-006: Rebuilding any optional retrieval index from Markdown reproduces the same source corpus without data loss.
- AC-007: An unavailable provider produces persistent queued work and a retry record, not lost memories or a blocked Codex client.
- AC-008: A project with `enabled = false` receives no automatic context and produces no capture jobs.
- AC-009: Once the US$5 monthly budget is reached, the worker pauses new API calls and preserves pending jobs.
- AC-010: A successful session batch creates one local Git commit and triggers the encrypted-backup command only when a repository is configured.
- AC-011: An allowlisted non-project session can contribute global memory, while an unapproved directory produces no capture job or injected context.
- AC-012: Installation preserves unrelated Codex settings and hooks, disables native memories, and installs trusted-reviewable lifecycle commands.

## Out of Scope

- Automatic ingestion of ChatGPT sessions or non-Codex clients.
- Multi-user permissions, sharing, synchronization, or hosted collaboration.
- Storing binary documents as canonical memory.
- Vector search, embeddings, an MCP server, or integrations for other LLMs.
