# Implementation Plan

## Milestones

### M1 — Confirmed information architecture and seed

Create the canonical Markdown layout, schema, global index, project-dossier template, audit structure, and seed only the approved existing sources.

### M2 — Codex hook and context workflow

Install global `SessionStart`/`UserPromptSubmit`/`PreCompact`/`SessionEnd` hooks. Load core and prompt-relevant context automatically and enqueue checkpoints without blocking Codex.

### M3 — Durable automatic capture

Implement the Python queue worker, local redaction, DeepSeek JSON classification, automatic promotion, conflict handling, stale status, local commits, and audit events.

### M4 — Operations and recovery

Install the user-level systemd service, retries, US$5 budget guardrail, Gitleaks, and optional encrypted `restic` backup configuration. Validate recovery and observe real sessions.

### M5 — Read-only MCP access

Configure pinned MCPVault as a local STDIO server for Codex. Expose only the approved read/search/metadata tools and keep all canonical writes inside the existing worker pipeline.

### M6 — Measure future semantic retrieval needs

Keep deterministic selection as the default. Consider a local semantic selector or narrow non-Codex candidate-submission tool only after documented misses or capture needs justify them.

## Task Breakdown

- [x] Initialize the project repository, canonical directories, YAML schema, and templates.
- [x] Implement `memory-seed` for approved initialization without historical transcript mining.
- [x] Implement the global `SessionEnd` enqueue hook and global `SessionStart` context hook.
- [x] Implement trusted-project discovery, non-project allowlists, deny roots, and `.codex/agent-memory.toml` opt-out.
- [x] Implement the persistent queue and user-level systemd worker/service units.
- [x] Implement deterministic transcript extraction, scope filtering, redaction, and source hashing.
- [x] Implement the DeepSeek V4 Flash runner, JSON schema validation, retry/backoff, and configured cost accounting.
- [x] Implement note writer, duplicate/supersession logic, review schedules, stale exclusion, and audit writer.
- [x] Implement bounded global/project selector and source manifest.
- [x] Add local Git commit-per-session behavior and `restic` backup adapter, disabled without credentials.
- [x] Add schema, link, metadata, and secret validation plus Gitleaks configuration.
- [x] Add pinned, idempotent, read-only MCPVault configuration to the Codex installer.
- [x] Add tests proving unrelated Codex settings survive and mutation tools are unavailable.
- [x] Validate the pinned MCPVault package version and exact tool surface against its source.
- [x] Separate the application repository from the canonical Agent-Memory vault.
- [x] Add grounded entity/concept metadata to the classifier and canonical schema.
- [x] Implement deterministic manifest, active-memory, project, entity,
  concept, and supersession projections under `70-projections`.
- [x] Ensure automatic context selects canonical records only and never treats
  projections as independent memory.
- [x] Add projection drift validation, obsolete-projection cleanup, a manual
  rebuild command, and Git initialization for a new vault.
- [x] Repoint the live worker and MCPVault configuration to the separate vault.
- [x] Add queue-only `PreCompact`, expiring project handoffs, and bounded `UserPromptSubmit` recall.
- [x] Add rebuildable local FTS5 retrieval, temporal validity, typed relations, and a relation projection.
- [x] Add a proposal-only curator command and daily user-systemd timer definition.
- [ ] Install the optional Gitleaks binary on the host.
- [ ] Run acceptance scenarios against at least five real Codex sessions before considering semantic retrieval.

## Dependencies

- M2 depends on the schema/templates and trusted-project predicate from M1.
- M3 depends on the queue contract, redaction policy, DeepSeek credential, and local Git repository.
- M4 depends on durable writes from M3; remote backup remains inactive until an object-storage destination is provided.
- M5 depends only on the canonical Markdown vault and local Node.js runtime; it must remain independent of the hook/worker lifecycle.
- M6 depends on measured retrieval failures or a confirmed cross-client capture contract.
- The projection layer depends only on canonical Markdown and is intentionally
  rebuildable without DeepSeek, MCPVault, Obsidian, or network access.

## Risks

- Automatic promotion can pollute memory; mitigate with explicit/verified eligibility, local validation, audit, review dates, and Git history.
- The SessionEnd timeout can lose slow work; mitigate by enqueueing only and running the worker under systemd.
- Hosted classification can leak data or create cost surprises; mitigate with redaction, secret blocking, a provider-neutral runner, and US$5 monthly pause.
- Mixing personal and agent vaults can leak sensitive notes; keep distinct roots, scope checks, and project opt-out.
- A vector index may create confident but untraceable retrieval; keep it non-canonical and deferred.
- A generic MCP mutation may bypass memory governance; keep the entire canonical MCP surface read-only.
- A package update may add or rename tools; pin the version and re-audit the allowlist before upgrades.
- Generated views may be mistaken for evidence; mark them `canonical: false`,
  keep them outside selector scan roots, and require links back to canonical
  records.

## Validation Plan

- Verify Obsidian can navigate global and project context without special tooling.
- Simulate `SessionStart` and verify the compact global/project context is correct, source-cited, and under 1,500/3,000 tokens.
- Simulate `SessionStart`, `PreCompact`, `UserPromptSubmit`, and `SessionEnd`; verify bounded source-cited core, handoff, relevant recall, and checkpoint behavior.
- Test direct statement, verified outcome, inference, conflict, duplicate, stale, disabled project, missing transcript, malformed JSON, provider outage, and budget exhaustion.
- Test known secrets and out-of-scope content to verify no cloud request/note/commit occurs.
- Temporarily remove any optional index and confirm the Markdown vault plus Git history remains recoverable and usable.
- Verify MCPVault starts over STDIO, exposes the approved read-only list, and can search/read a test note.
- Verify Codex MCP configuration contains the exact version and allowlist and that MCP failure does not affect hooks or the worker.
- Delete or tamper with generated projections, rebuild them, and confirm
  byte-identical deterministic restoration without canonical changes.
- Restore a `restic` backup in an isolated directory after a backup destination is configured.
