# Implementation Plan

## Milestones

### M1 — Confirmed information architecture and seed

Create the canonical Markdown layout, schema, global index, project-dossier template, audit structure, and seed only the approved existing sources.

### M2 — Codex hook and context workflow

Install global `SessionStart`/`SessionEnd` hooks. Load global/project context automatically and enqueue completed trusted-project sessions without blocking Codex.

### M3 — Durable automatic capture

Implement the Python queue worker, local redaction, DeepSeek JSON classification, automatic promotion, conflict handling, stale status, local commits, and audit events.

### M4 — Operations and recovery

Install the user-level systemd service, retries, US$5 budget guardrail, Gitleaks, and optional encrypted `restic` backup configuration. Validate recovery and observe real sessions.

### M5 — Measure future retrieval needs

Keep deterministic selection as the default. Consider a local semantic selector, MCP, or other LLM support only after documented misses prove the 1,500/3,000-token packs insufficient.

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
- [ ] Install the optional Gitleaks binary on the host.
- [ ] Run acceptance scenarios against at least five real Codex sessions before considering semantic retrieval.

## Dependencies

- M2 depends on the schema/templates and trusted-project predicate from M1.
- M3 depends on the queue contract, redaction policy, DeepSeek credential, and local Git repository.
- M4 depends on durable writes from M3; remote backup remains inactive until an object-storage destination is provided.
- M5 depends on measured retrieval failures from real usage.

## Risks

- Automatic promotion can pollute memory; mitigate with explicit/verified eligibility, local validation, audit, review dates, and Git history.
- The SessionEnd timeout can lose slow work; mitigate by enqueueing only and running the worker under systemd.
- Hosted classification can leak data or create cost surprises; mitigate with redaction, secret blocking, a provider-neutral runner, and US$5 monthly pause.
- Mixing personal and agent vaults can leak sensitive notes; keep distinct roots, scope checks, and project opt-out.
- A vector index may create confident but untraceable retrieval; keep it non-canonical and deferred.

## Validation Plan

- Verify Obsidian can navigate global and project context without special tooling.
- Simulate `SessionStart` and verify the compact global/project context is correct, source-cited, and under 1,500/3,000 tokens.
- Simulate `SessionEnd`; verify it enqueues within timeout, then worker processing creates exactly one commit.
- Test direct statement, verified outcome, inference, conflict, duplicate, stale, disabled project, missing transcript, malformed JSON, provider outage, and budget exhaustion.
- Test known secrets and out-of-scope content to verify no cloud request/note/commit occurs.
- Temporarily remove any optional index and confirm the Markdown vault plus Git history remains recoverable and usable.
- Restore a `restic` backup in an isolated directory after a backup destination is configured.
