# PRD

## Overview

The Agent Memory Vault is a curated, local-first memory layer for Codex-assisted work. It favors small, reliable context packs over unlimited recall. Obsidian is the editor and browser; Markdown is canonical; the pipeline automatically extracts strictly eligible memories from trusted-project Codex sessions. A pinned read-only MCPVault adapter adds portable local search and note access without becoming a write path.

## User Personas

- **Owner/curator:** defines scope, storage credentials, project exclusions, and corrections; reviews audit records when automation blocks or fails.
- **Codex session:** automatically receives relevant global and project context before work and creates memory candidates when it ends.
- **Background worker:** classifies redacted session excerpts, validates results, writes canonical notes, commits changes, and triggers backup.
- **MCP-compatible client:** searches and reads approved vault content on demand but cannot mutate canonical memory through MCP.

## Core User Journeys

1. Codex starts in a trusted project; `SessionStart` injects a compact global/project core pack and an unexpired handoff when available.
2. `UserPromptSubmit` locally selects a small prompt-relevant pack from active canonical records.
3. `PreCompact` and `SessionEnd` enqueue a transcript checkpoint without blocking the Codex client.
3. A user-level worker extracts only eligible, locally redacted evidence, calls DeepSeek V4 Flash, validates its JSON, and promotes valid memories automatically.
4. The worker writes canonical records, deterministically rebuilds fluid agent
   projections, commits the managed layers as one session batch, and attempts
   an encrypted backup if configured.
5. Bruno inspects memories and audit records in Obsidian, corrects a note normally, or disables a project with `.codex/agent-memory.toml`.
6. Codex or another configured local MCP client performs an ad-hoc BM25 search and reads selected notes; automatic injection still comes from `SessionStart`.

## Functional Requirements

- FR-001: The system must store canonical memories as UTF-8 Markdown files with YAML frontmatter.
- FR-002: The vault must provide a concise global context entry point for agent-readable preferences, working rules, and stable environment facts.
- FR-003: The vault must separate canonical global/project records, decisions,
  runbooks, archive, and non-sensitive audit from fluid generated projections.
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
- FR-016: The system must generate a project dossier projection when it first
  sees active canonical memory for that project.
- FR-017: A project-level `.codex/agent-memory.toml` with `enabled = false` must disable capture and context injection for that project.
- FR-018: The worker must commit a successful memory batch to local Git and then run an encrypted backup attempt.
- FR-019: The DeepSeek classifier must stop accepting new jobs after its configured US$5 monthly budget is reached and leave existing jobs queued.
- FR-020: The seed process must curate only global Codex guidance, approved global memories, and active project documentation; it must not mine old transcripts.
- FR-021: The system must support allowlisted non-project directories in addition to trusted Git projects, while applying explicit deny rules and local opt-outs first.
- FR-022: Installation must disable Codex native memory generation and injection and preserve backups of modified user configuration.
- FR-023: The SessionStart adapter must handle startup, resume, clear, and post-compaction lifecycle events.
- FR-024: Installation must configure `@bitbonsai/mcpvault@0.12.4` as the local `agent_memory_vault` Codex MCP server rooted at the canonical vault.
- FR-025: The MCP server must expose only read, batch-read, lexical search, frontmatter inspection, note metadata, vault statistics, directory listing, tag listing, and wiki-link resolution.
- FR-026: MCP must not expose write, patch, move, delete, tag mutation, or frontmatter mutation tools against the canonical vault.
- FR-027: MCP availability or failure must not affect SessionStart injection, SessionEnd enqueueing, worker processing, or canonical writes.
- FR-028: The separate canonical vault root must default to
  `/mnt/Dump/Obsidian/Vaults/Agent-Memory`, never the application repository.
- FR-029: Canonical records may carry bounded, grounded `entities` and
  `concepts` labels for machine retrieval.
- FR-030: The system must deterministically generate a projection manifest,
  active-memory index, per-project dossiers, entity/concept indexes, and a
  supersession graph.
- FR-031: Projection files must be replaceable and must never be parsed as
  canonical memory or injected independently of their canonical source records.
- FR-032: Installation must initialize a private local Git repository for a new
  vault and commit its managed schema and projection baseline.
- FR-033: The system must keep an expiring, non-canonical per-project handoff derived only from a redacted project session.
- FR-034: `UserPromptSubmit` must retrieve only active, scope-eligible canonical records using a rebuildable local lexical/entity/concept index.
- FR-035: Canonical records may carry temporal-validity dates and typed grounded relations; supersession closes the prior effective window.
- FR-036: `PreCompact` must enqueue only an idempotent checkpoint and must not call a provider inline.
- FR-037: A proposal-only curator must report deterministic stale, duplicate, expired-window, and dangling-relation findings without editing canonical records.

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
- NFR-011: The MCP package version and enabled-tool allowlist must be deterministic, reviewable, and idempotently installed while preserving unrelated Codex configuration.
- NFR-012: MCP search remains lexical BM25 without embeddings. Automatic prompt recall uses a disposable local SQLite FTS5 index plus deterministic scope, lifecycle, authority, entity, concept, and relation signals.
- NFR-013: Rebuilding projections from unchanged canonical records must produce
  byte-identical Markdown and remove obsolete generated projection files.

## Edge Cases

- A preference changes: write the replacement note, mark the old note `superseded`, and link both.
- A note is valid only temporarily: use `review_after` or `expires` so it does not become silent permanent context.
- An agent's inference is uncertain: reject it as ineligible and record only a non-sensitive audit reason.
- A source conversation contains a secret: capture only the non-sensitive conclusion, never the raw transcript.
- Two projects have conflicting choices: isolate their dossiers; do not elevate either choice to global context.
- The provider returns malformed/empty JSON: preserve the job, retry with backoff, and never partially write memory.
- The monthly budget is exhausted: leave jobs queued until the next accounting period or a configuration increase.
- A source transcript disappears before retry: mark the job failed with a source-unavailable audit event; do not invent a replacement.
- MCPVault is unavailable or cannot start: Codex loses only ad-hoc MCP access; hooks and the worker continue normally.

## Acceptance Criteria

- AC-001: A clean install initializes the separate Markdown directory as an
  Obsidian-compatible vault whose agent manifest can be read without installing
  a plugin or running Obsidian.
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
- AC-013: `codex mcp get agent_memory_vault` shows the pinned package, canonical vault root, and exactly the approved read-only tool allowlist.
- AC-014: An MCP client can list, search, and read test notes, while write, patch, move, delete, tag mutation, and frontmatter mutation tools are unavailable.
- AC-015: A clean install creates the separate Agent-Memory vault, initializes
  Git, and points both the worker and MCPVault at the same root.
- AC-016: A project memory with entity/concept labels appears in the generated
  project, entity, concept, and active-memory projections while SessionStart
  cites only the canonical note.
- AC-017: Tampering with a generated projection is detected by validation and a
  rebuild restores the deterministic version.

## Out of Scope

- Automatic ingestion of ChatGPT sessions or non-Codex clients; they receive read-only access until a separate candidate-submission contract is approved.
- Multi-user permissions, sharing, synchronization, or hosted collaboration.
- Storing binary documents as canonical memory.
- Vector search and embeddings.
- Generic MCP writes to canonical memory.
