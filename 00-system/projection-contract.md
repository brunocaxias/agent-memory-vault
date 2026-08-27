# Agent Projection Contract

Everything below `70-projections` is deterministic, fluid, and replaceable.
Agents may use projections to navigate the vault, then follow links to canonical
records for provenance and lifecycle status.

Projection files may be deleted and rebuilt with:

`memory-vault rebuild-projections`

Do not manually store unique facts, decisions, or evidence in a projection.
The projection builder replaces stale files and regenerates active-memory,
project, entity, concept, relation, and supersession views from canonical records.
