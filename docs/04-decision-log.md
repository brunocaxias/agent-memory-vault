# Decision Log

## 2026-07-24 - Initial Project Direction

### Decision

Create a separate agent-oriented memory vault rather than extending the existing personal Obsidian vault. Treat Obsidian-compatible Markdown as the canonical record and design the vault primarily for Codex and other LLM consumers.

### Context

Bruno uses Codex heavily and wants durable personal/work context beyond the limited, provider-specific chat memory. The desired system differs from a personal vault: it must be structured, scoped, auditable, and safe to expose selectively to LLMs.

### Alternatives Considered

- Rely only on native ChatGPT/Codex memory: low effort but limited, opaque, and provider-bound.
- Extend the existing personal vault: convenient but mixes AI-safe context with notes that should not enter model prompts.
- Start with a vector database/RAG service: offers fuzzy recall but creates operational overhead and weakens auditability before the content model is proven.

### Consequences

- A second vault has an initial curation cost but creates a clear privacy and purpose boundary.
- Markdown indexes and explicit project dossiers become the first retrieval mechanism.
- Automated ingestion and semantic retrieval are deferred until real usage demonstrates their need.

## 2026-07-24 - Proposed v1 Governance Boundary

### Decision

Propose owner-approved memory promotion: agents may write proposals to an inbox but cannot directly activate durable memories. The decision is pending Bruno's confirmation.

### Context

LLMs can infer incorrectly, preserve stale information, or copy material that is too sensitive. A review inbox maintains usefulness while preserving control.

### Alternatives Considered

- Direct autonomous writes: fastest capture, highest risk of pollution and leakage.
- Fully manual capture only: safest, but may be too much friction for sustained use.

### Consequences

- The initial workflow includes a review step.
- Later automation must preserve the proposal/approval distinction.

## 2026-07-24 - Proposed Retrieval Strategy

### Decision

Propose deterministic, bounded context selection before embeddings or a vector database. This remains pending confirmation.

### Context

The first problem is trustworthy and scoped context, not maximum recall. Markdown links, explicit project scope, active status, and review dates are inspectable and cheap.

### Alternatives Considered

- Obsidian-plugin-first automation.
- Semantic RAG/vector database as the primary interface.

### Consequences

- v1 can operate with Obsidian, Markdown, Git, and standard local search.
- A local CLI/MCP selector becomes a measured phase-2 enhancement, not an architectural dependency.

## 2026-07-24 - Confirmed Automatic Codex Memory Pipeline

### Decision

Use a global Codex hook pipeline for trusted Git projects: `SessionStart` injects deterministic global and project context; `SessionEnd` queues the completed session; a Python worker supervised by user-level systemd classifies the session with DeepSeek V4 Flash and promotes valid memories automatically.

### Context

Bruno wants the system to act as real durable memory for heavy Codex use, not merely a manual vault. Codex hooks provide session lifecycle events but the session-end event has a short timeout, so network classification cannot execute inline.

### Alternatives Considered

- Manual capture or mandatory review inbox: rejected because it would lose the desired automatic memory behavior.
- Codex as classifier: rejected due to cost and potential recursive hook behavior.
- Obsidian plugin-only approach: rejected because it would not naturally integrate with the Codex session lifecycle.

### Consequences

- The hook only enqueues durable jobs; a background worker does all slow work.
- The initial consumer is Codex. Other LLMs, MCP, and semantic retrieval remain out of scope.
- The automatic pipeline must have stronger redaction, validation, audit, idempotency, and cost controls.

## 2026-07-24 - Confirmed Memory Eligibility and Lifecycle

### Decision

Automatically promote only explicit user statements and verified project outcomes/runbooks. Store a source reference, transcript SHA-256, and redacted evidence excerpt. New explicit contradictory information supersedes the active record. Review schedules are 30 days for project state, 180 days for decisions/runbooks, and 365 days for global preferences/stable facts; overdue notes become `stale` and leave automatic context packs.

### Context

Automatic direct writes are useful only when memories remain trustworthy. Bruno selected work/operation content only and chose automatic active promotion rather than an approval inbox.

### Alternatives Considered

- Save model inferences: rejected because false conclusions would silently enter active memory.
- Keep conflicting notes active: rejected because it increases context ambiguity.
- Retain stale notes in context: rejected because outdated context is worse than a discoverable archived record.

### Consequences

- The classifier contract must encode eligibility and evidence, not merely a free-text summary.
- Blocked secrets/out-of-scope content create non-sensitive audit events only.
- Notes remain editable and recoverable through Markdown/Git even when excluded from context.

## 2026-07-24 - Confirmed Operations, Cost, and Backup Boundaries

### Decision

Use DeepSeek V4 Flash with locally redacted excerpts, a persistent retry queue, and a US$5 monthly budget that pauses calls while preserving jobs. Commit each successful session batch locally. Attempt an encrypted `restic` backup after each commit, but leave remote backup disabled until Bruno selects a private object-storage destination. Projects can opt out with `.codex/agent-memory.toml`.

### Context

The system must be inexpensive, survive provider failures, and never depend on a public Git remote. Bruno selected a future configurable backup destination rather than committing to a provider now.

### Alternatives Considered

- Send full transcripts to cloud: rejected because local summary/selected redacted excerpts reduce exposure.
- Drop failed sessions: rejected because failures would create invisible memory gaps.
- Only collect cost telemetry: rejected in favor of a hard initial monthly ceiling.

### Consequences

- Credentials and cost rates are configuration, not repository content.
- Backup restoration is an acceptance test once a destination is configured.
- Provider and pricing changes may require updating configuration, not canonical memories.

## 2026-07-28 - Canonical Obsidian Memory and Capture Scope

### Decision

Keep Agent Memory Vault as the canonical product and absorb the useful
note-authoring rules from `obsidian-note-skill` as internal validation and
rendering behavior. Disable Codex native memory generation and injection.
Automatically capture trusted Git projects under allowed roots and explicitly
allowlisted non-project directories; explicit deny rules and project opt-outs
take precedence.

### Context

Codex now includes a local generated-memory feature, but those files are not
intended as a hand-maintained canonical store. Bruno wants persistent memory to
remain structured, correctable, and navigable in Obsidian without a competing
injection layer.

### Alternatives Considered

- Run Codex native memory and the Obsidian vault together: rejected because
  duplicate extraction and independent correction paths can create conflicts.
- Mirror generated Codex memory into Obsidian: rejected because Obsidian would
  not be authoritative at retrieval time.
- Capture every local Codex session: rejected for v1 because unrestricted
  capture increases privacy and noise risk.

### Consequences

- The installer must preserve existing Codex configuration and hooks while
  disabling native memory flags.
- General chats are eligible only from configured non-project roots.
- The smaller note-authoring plan is marked superseded rather than implemented
  as a separate product.
