# Project Brief

## Summary

Create a private, local-first knowledge vault whose primary reader is Codex. The vault will be Obsidian-compatible Markdown, but its information architecture, automatic capture pipeline, and retrieval interface will be designed for reliable machine use rather than for personal note-taking.

## Problem

Codex now offers a generated local-memory layer, but its files are implementation state rather than a user-owned canonical knowledge base. Important preferences, decisions, ongoing projects, and operational lessons need a structured, auditable Obsidian source of truth. A conventional personal Obsidian vault still mixes diary material, rough notes, and sensitive content that should not automatically enter AI context.

## Target Users

- Primary: Bruno, as owner, curator, and operator.
- Consumer in v1: Codex running in trusted local projects.
- Future consumers: other LLMs only through a separately approved integration.

## Goals

- Keep durable, useful context in plain Markdown under Bruno's control.
- Make the highest-value context quick for an agent to locate and read.
- Separate agent memory from the existing personal vault and from secrets.
- Preserve provenance, confidence, review dates, and the ability to correct or delete memories.
- Automatically extract eligible memories when a Codex session ends, without requiring a manual capture command.
- Load a compact global and project-specific context pack at the start of a Codex session.
- Keep the canonical vault usable offline even though automatic classification uses a cheap hosted model.
- Allow a later, opt-in retrieval layer without changing the canonical data format.

## Non-Goals

- Replace the personal Obsidian vault, a password manager, backups, or source control.
- Automatically save every conversation, terminal output, or private thought.
- Ingest every conversation, terminal output, or personal note indiscriminately.
- Build a second brain, task manager, CRM, or generic RAG platform.
- Store API keys, passwords, recovery codes, financial documents, or other secrets.
- Add a vector database, embeddings service, MCP server, or support for other LLMs in v1.

## Constraints

- The canonical vault root is `/mnt/Dump/Coding/Projects/agent-memory-vault`.
- Local-first, private, and inexpensive; DeepSeek V4 Flash is the only hosted dependency in v1.
- Canonical content must remain portable Markdown with YAML frontmatter.
- The vault must be human-readable in Obsidian and Git-reviewable.
- Capture applies to trusted Git projects beneath configured allowed roots and to explicitly allowed non-project directories. Deny rules and local opt-outs always win.
- Codex native memory generation and injection are disabled while this vault is active so two memory systems cannot produce contradictory context.
- Allowed memory content is work preferences, project state/decisions, software, machines, and home-server operations. Health, finances, contacts, diary content, and secrets are excluded.
- Full transcripts remain in Codex storage; the vault keeps only a source reference, hash, and redacted evidence excerpt.

## Success Criteria

- In a new session, Codex receives a relevant context pack automatically: at most 1,500 global tokens and 3,000 project tokens.
- An eligible completed session produces an auditable, idempotent local Git commit without waiting for user review.
- Each durable memory has a clear type, scope, provenance, source hash, redacted evidence, and review/expiry rule.
- A correction or deletion can be made as a normal Markdown/Git change and is honored by later retrieval.
- The vault remains useful when opened directly in Obsidian with no service running.
- A secret-bearing or out-of-scope session never sends the sensitive excerpt to DeepSeek and never writes it into the vault.

## Assumptions

- Python 3.14 and a user-level `systemd` service are available on the target Linux machine.
- The user will select and configure the private object-storage destination for encrypted backups later; remote backup is disabled until then.
- Current DeepSeek V4 Flash pricing is configured locally and used to enforce a US$5 monthly classifier budget.

## Open Questions

- Which private object-storage provider and bucket should receive the encrypted `restic` backup?
- When should a future local semantic-retrieval layer replace or supplement deterministic context selection? It requires measured retrieval failures first.
