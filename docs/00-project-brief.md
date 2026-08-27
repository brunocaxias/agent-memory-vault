# Project Brief

## Summary

Create a private, local-first knowledge vault whose primary reader is Codex. The vault will be Obsidian-compatible Markdown, but its information architecture, automatic capture pipeline, and retrieval interfaces will be designed for reliable machine use rather than for personal note-taking. Codex hooks provide deterministic automatic memory, while a pinned read-only MCP adapter provides portable ad-hoc access.

## Problem

Codex now offers a generated local-memory layer, but its files are implementation state rather than a user-owned canonical knowledge base. Important preferences, decisions, ongoing projects, and operational lessons need a structured, auditable Obsidian source of truth. A conventional personal Obsidian vault still mixes diary material, rough notes, and sensitive content that should not automatically enter AI context.

## Target Users

- Primary: Bruno, as owner, curator, and operator.
- Automatic consumer and producer: Codex running in trusted local projects.
- Read-only consumers: Codex and other separately configured MCP-compatible local clients.

## Goals

- Keep durable, useful context in plain Markdown under Bruno's control.
- Make the highest-value context quick for an agent to locate and read.
- Separate agent memory from the existing personal vault and from secrets.
- Preserve provenance, confidence, review dates, and the ability to correct or delete memories.
- Automatically extract eligible memories when a Codex session ends, without requiring a manual capture command.
- Load a compact global and project-specific core pack at the start of a Codex session,
  plus an expiring handoff for unfinished project work.
- Retrieve a small prompt-relevant pack locally when Codex receives a user prompt.
- Keep the canonical vault usable offline even though automatic classification uses a cheap hosted model.
- Allow MCP-compatible clients to read and search the vault without changing the canonical data format or bypassing the memory pipeline.
- Provide fluid, machine-oriented projections that agents can rebuild as the
  useful organization of memory changes.

## Non-Goals

- Replace the personal Obsidian vault, a password manager, backups, or source control.
- Automatically save every conversation, terminal output, or private thought.
- Ingest every conversation, terminal output, or personal note indiscriminately.
- Build a second brain, task manager, CRM, or generic RAG platform.
- Store API keys, passwords, recovery codes, financial documents, or other secrets.
- Add a vector database or embeddings service before measured retrieval failures justify one.
- Let generic MCP tools write, patch, move, tag, or delete canonical memories.
- Automatically ingest sessions from non-Codex clients before a narrow candidate-submission contract exists.

## Constraints

- The canonical vault root is `/mnt/Dump/Obsidian/Vaults/Agent-Memory`;
  implementation code remains in
  `/mnt/Dump/Coding/Projects/agent-memory-vault`.
- Local-first, private, and inexpensive; DeepSeek V4 Flash is the only hosted dependency in v1.
- Canonical content must remain portable Markdown with YAML frontmatter.
- The vault must be machine-oriented first, Obsidian-compatible, and
  Git-reviewable; human readability is useful but does not constrain the
  projection model.
- Capture applies to trusted Git projects beneath configured allowed roots and to explicitly allowed non-project directories. Deny rules and local opt-outs always win.
- Codex native memory generation and injection are disabled while this vault is active so two memory systems cannot produce contradictory context.
- MCPVault is pinned to a tested version and exposed through a strict Codex read-only tool allowlist. It is an optional access adapter, never the write authority.
- Allowed memory content is work preferences, project state/decisions, software, machines, and home-server operations. Health, finances, contacts, diary content, and secrets are excluded.
- Full transcripts remain in Codex storage; the vault keeps only a source reference, hash, and redacted evidence excerpt.

## Success Criteria

- In a new session, Codex receives a relevant core context pack automatically: at most 1,500 global tokens and 3,000 project tokens; a separate handoff is capped at 800 tokens.
- A `PreCompact` checkpoint and `UserPromptSubmit` recall hook preserve continuity and add prompt-relevant context without a second canonical store.
- An eligible completed session produces an auditable, idempotent local Git commit without waiting for user review.
- Each durable memory has a clear type, scope, provenance, source hash, redacted evidence, and review/expiry rule.
- A correction or deletion can be made as a normal Markdown/Git change and is honored by later retrieval.
- The vault remains useful when opened directly in Obsidian with no service running.
- Codex can search and read the canonical vault through MCP while no MCP mutation tool is available.
- Agents can enter through a generated manifest, active-memory index, project
  dossier, entity index, or concept index and follow links back to canonical
  provenance.
- Deleting and rebuilding `70-projections` reproduces the same views without
  changing canonical records.
- A secret-bearing or out-of-scope session never sends the sensitive excerpt to DeepSeek and never writes it into the vault.

## Assumptions

- Python 3.14 and a user-level `systemd` service are available on the target Linux machine.
- Node.js 20 or newer and `npx` are available for the pinned local MCPVault process.
- The user will select and configure the private object-storage destination for encrypted backups later; remote backup is disabled until then.
- Current DeepSeek V4 Flash pricing is configured locally and used to enforce a US$5 monthly classifier budget.

## Open Questions

- Which private object-storage provider and bucket should receive the encrypted `restic` backup?
- When should a future local semantic-retrieval layer replace or supplement deterministic context selection? It requires measured retrieval failures first.
