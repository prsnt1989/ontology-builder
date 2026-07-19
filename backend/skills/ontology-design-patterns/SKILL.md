---
name: ontology-design-patterns
description: Conventions for designing Palantir Foundry-style object types, properties, and relationships. Use when designing or reviewing an ontology's structure.
license: MIT
compatibility: Works with any model that supports tool use.
metadata:
  author: ontology-builder
  version: "1.0"
  phase: design
---

## Object type design

- `api_name` must be PascalCase (e.g. `WorkOrder`, `Equipment`, `Technician`).
- Every object type has a `backing_table` with a snake_case `table_name`.
- Generate 8–15 focused object types — not a bloated model.
- Each object type should have 5–12 properties, mixing required and optional.
- Include a `title_property` that serves as the human-readable identifier.
- Primary keys are auto-increment integers, with a separate business ID field.

## Property design

- Every property maps to a `backing_column` (snake_case).
- Use appropriate SQL types per property type.
- Mark `indexed: true` for commonly filtered/searched fields.
- For enum properties, provide realistic `enum_values`.
- Prefer explicit status/state columns named `status` or `state` for lifecycle-bearing types.

## Relationships

- Model relationships from foreign keys; name them by role, not by table.
- Capture cardinality (one-to-many, many-to-many) explicitly.
- Every relationship should connect two object types that already exist in the model.
