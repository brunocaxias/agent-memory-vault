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
- The initial consumer is Codex. At that stage, other LLMs, MCP, and semantic retrieval were out of scope; the 2026-07-28 decision below supersedes only the MCP read-access boundary.
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

## 2026-07-28 - Confirmed Read-Only MCPVault Access Layer

### Decision

Add `@bitbonsai/mcpvault@0.12.4` as a pinned local STDIO MCP server named
`agent_memory_vault`. Allow only note reads, batch reads, BM25 search,
frontmatter and note metadata inspection, vault statistics, directory listing,
tag listing, and wiki-link resolution. Keep every mutation tool unavailable.

### Context

The automatic Codex hook pipeline solves deterministic capture and context
injection, but MCP-compatible clients benefit from a standard ad-hoc vault
interface. MCPVault operates directly on local Markdown and does not require
Obsidian to run. It does not provide a reliable session lifecycle or the
project's eligibility, redaction, provenance, and idempotency controls.

### Alternatives Considered

- Keep MCP deferred: safest but unnecessarily limits portable read/search
  access now that the canonical vault and governance pipeline are working.
- Give MCPVault full read/write access: rejected because generic mutations
  bypass the worker's validation, audit, source evidence, and Git batch rules.
- Replace deterministic SessionStart selection with BM25: rejected because
  lexical relevance does not enforce scope, lifecycle status, or token budgets.

### Consequences

- Codex and separately configured MCP clients can inspect the same canonical
  Markdown without a provider-specific skill invocation.
- Hooks and the worker remain the only automatic capture and canonical write
  path; MCP failure cannot block them.
- The Node package is version-pinned and upgrades require reviewing the exact
  tool list plus a live STDIO smoke test.
- Automatic non-Codex capture remains out of scope until a narrow
  candidate-submission interface is designed.

## 2026-07-28 - Confirmed Layered Agent-Native Vault

### Decision

Keep the software repository at
`/mnt/Dump/Coding/Projects/agent-memory-vault` and create the independent
canonical vault at `/mnt/Dump/Obsidian/Vaults/Agent-Memory`. Use two data
layers:

1. stable source-cited canonical memory records; and
2. deterministic, fluid Markdown projections for agent navigation.

Generate a manifest, active-memory index, per-project dossiers, entity and
concept indexes, and a supersession graph under `70-projections`. Projection
files are explicitly non-canonical, may be deleted/rebuilt, and never enter
automatic context independently of their canonical source records.

### Context

Bruno confirmed that the vault's primary readers are agents and that its
structure may be fluid. A conventional human-first notes hierarchy is too
shallow, but unrestricted agent rewriting would weaken provenance and allow
derived summaries to become indistinguishable from sourced memory.

### Alternatives Considered

- Keep only atomic notes: rejected because navigation becomes shallow as the
  corpus grows.
- Let agents freely rewrite every note: rejected because facts, summaries, and
  inferred relationships would drift without a stable evidence layer.
- Add a graph/vector database now: rejected because deterministic Markdown
  projections provide the required fluidity without a second datastore or
  retrieval dependency.

### Consequences

- Canonical records gain optional bounded, grounded `entities` and
  `concepts` labels.
- Projection output is byte-deterministic, validated against canonical input,
  committed alongside each session batch, and rebuildable offline.
- Obsolete generated files are deleted only within the dedicated
  `70-projections` boundary.
- The separate vault has its own private local Git repository; application code
  and planning documents are not exposed as memory through MCP.
- Human readability remains useful, but machine navigation, provenance, and
  reconstructability take priority.

## 2026-07-28 - Confirmed Three-Lane Recall and Continuity Upgrade

### Decision

Keep canonical Markdown and the existing redaction/worker/Git write boundary.
Add an expiring project handoff, queue-only `PreCompact` checkpointing, and
bounded `UserPromptSubmit` recall using a rebuildable local SQLite FTS5 index.
Extend records with temporal-validity dates and typed grounded relations. Add a
proposal-only curator; defer embeddings and graph databases.

### Context

Repository research showed that Markdown-first agent-memory systems converge on
short core memory, session handoffs, relevance-aware recall, temporal
supersession, and maintenance/evaluation loops. The existing selector ranked
only by priority/date at session start, which could inject irrelevant context
after the user's actual prompt became known.

### Alternatives Considered

- Replace the vault with an external memory product: rejected because it would
  weaken or duplicate the existing local redaction, eligibility, provenance,
  audit, and canonical-write controls.
- Add embeddings or a graph database immediately: deferred because local FTS,
  scope, lifecycle, entities, concepts, and relations provide an inspectable
  baseline first.
- Let consolidation rewrite canonical notes automatically: rejected because
  deterministic diagnostics may propose maintenance but cannot establish new
  truth without evidence.

### Consequences

- `60-handoffs` is an intentionally non-canonical, expiring continuity layer.
- The FTS5 database lives in runtime state and is rebuildable from canonical
  Markdown.
- Handoff and prompt recall remain bounded and source-cited.
- The daily curator produces a report only when it finds deterministic issues;
  it never mutates canonical records.
