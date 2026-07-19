---
name: generation-provisioning
description: Emit ontology YAML files and provision the database (schema/DDL + synthetic seed) behind a human approval gate. Use during the generation phase.
license: MIT
compatibility: Works with any model that supports tool use.
metadata:
  author: ontology-builder
  version: "1.0"
  phase: generating
  phases: [generating, update_generating]
---

## Two steps, one gate

Generation has a safe step and an irreversible step separated by human approval:

1. **Write YAML (safe).** Emit the 8 ontology files (`object_types`, `properties`, `relationships`, `actions`,
   `permissions`, `validation_rules`, `lifecycle_states`, `data_mapping`) plus `ontology_meta` (id, version,
   company, timestamps). Properties are written to `properties.yaml` keyed by object-type `api_name`.
2. **Provision the database (irreversible) — requires approval.** Only after the user approves: create tables
   from the object types + relationships, then seed synthetic rows.

## Schema / DDL

- One table per object type using its `backing_table.table_name` (snake_case). Auto-increment integer `id` PK plus
  the business ID field.
- Column SQL types come from each property's `backing_column.sql_type` (VARCHAR/INTEGER/BOOLEAN/TIMESTAMP…).
- Foreign keys come from relationships' `backing_foreign_key`.

## Seeding

- Generate realistic synthetic rows per table using the company/industry context.
- Respect foreign keys so relationships resolve.

## Updates

For an update run, provisioning is **additive**: create+seed only new tables, `ALTER TABLE ADD COLUMN` for new
columns (nullable), never drop, never re-seed existing tables. Always keep the irreversible DB step behind the
approval gate.
