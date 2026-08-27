# Canonical Memory Schema

Canonical records are the authoritative evidence layer. Generated projections
must never be used as a source when creating or correcting a canonical record.

## Required frontmatter

- `id`: deterministic stable identity.
- `type`: preference, decision, project-state, runbook, fact, or lesson.
- `status`: active, stale, superseded, or archived.
- `scope`: global or project:<slug>.
- `source`: eligibility kind, session reference, and transcript SHA-256.
- `evidence`: a short locally redacted supporting excerpt.
- `created`, `recorded_at`, `effective_from`, `effective_to`, and `review_after`:
  lifecycle and temporal-validity dates.
- `priority`: low, medium, or high.
- `entities` and `concepts`: optional grounded machine-retrieval labels.
- `relations`: optional typed links to memory IDs, entities, or concepts.

## Layer boundary

- Canonical records: `10-global`, `20-projects`, `30-runbooks`, `40-decisions`.
- Expiring session continuity: `60-handoffs` (not canonical memory).
- Fluid generated views: `70-projections`.
- Non-sensitive audit: `80-audit`.
- Raw transcripts, queue state, credentials, and unredacted text stay outside the vault.
