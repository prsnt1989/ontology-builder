---
name: graph-connectivity
description: How ontology object types and relationships form a connected graph — no isolated types, complete relationships, correct cardinality/direction. Use when designing relationships or reviewing the graph.
license: MIT
compatibility: Works with any model that supports tool use.
metadata:
  author: ontology-builder
  version: "1.0"
  phase: design
  phases: [design, update_design]
---

## Connectivity is a quality signal

The ontology is visualized as a network graph: each object type is a **node**, each relationship a **directed,
labeled edge**. A well-formed ontology is a connected graph.

- **No islands.** Every object type must participate in at least one relationship (as `from_object_type` or
  `to_object_type`). An object type with zero relationships renders as an isolated node — a design smell. Connect
  it to the most semantically related type, or drop it if it is genuinely superfluous.
- When you add a **new** object type, always add a relationship connecting it to an existing type in the same change.

## Complete relationships

Every relationship must be fully specified — an incomplete relationship renders with a blank cardinality marker or
is dropped from the graph entirely:

- `from_object_type` and `to_object_type` must both reference **existing** object types (by `api_name`).
- `cardinality` is required: `one_to_one` | `one_to_many` | `many_to_one` | `many_to_many`.
- `backing_foreign_key` must be complete: `from_table`, `from_column`, `to_table`, `to_column` (usually the
  target's primary key column, `id`), and `on_delete` (default `RESTRICT`). The FK column lives on the **many**
  side's table.
- Give a role-based `display_name` (e.g. "Support Cases", "Managed By") — this is the edge label.

## Direction & cardinality

- Direction (`from` → `to`) follows the foreign key: the table holding the FK is the `from` side.
- Prefer `many_to_one` from a child to its parent (e.g. `SupportCase → Customer`, many cases to one customer).
- Use `many_to_many` only when a join relationship is genuinely needed; otherwise model through an intermediate
  object type.
