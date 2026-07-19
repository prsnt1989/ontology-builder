---
name: ontology-update-management
description: Safely modify an existing ontology in place — analyze change requests, apply surgical patches, and migrate the database additively without losing data. Use during the update/change flow.
license: MIT
compatibility: Works with any model that supports tool use.
metadata:
  author: ontology-builder
  version: "1.0"
  phase: update_design
  phases: [update_intake, update_design, update_actions_rules, update_generating]
---

## Analyzing change requests

- Restate each requested change against the **existing** ontology (real object type / property / relationship
  names). Never invent structure the user didn't ask for.
- Clarify only genuinely-ambiguous aspects: target object type, field type/constraints, whether it's an ADD,
  MODIFY, or REMOVE, cardinality of new relationships, and whether existing data needs backfilling.
- Prefer additive changes. Only remove when the user explicitly asks.

## Surgical patches, not regeneration

Apply changes as a minimal set of patch operations against the existing design — do NOT regenerate the whole
ontology (that would rename/reword unchanged types):

- `add_object_type` / `add_property` / `add_relationship` for additions.
- `update_*_field` / `rename_relationship` / `replace_lifecycle` for modifications.
- `remove_object_type` / `remove_relationship` / `remove_*` for deletions.
- A new object type MUST come with an `add_relationship` connecting it (no islands).
- Removing an object type cascade-removes its relationships/actions/permissions/lifecycles automatically — don't
  emit separate removals for those.

## Additive, data-safe database migration

The database already holds data. Migration is **additive only**:

- **New tables** → create and seed them.
- **New columns** on existing tables → `ALTER TABLE ... ADD COLUMN` as **nullable** (existing rows lack a value).
  Do NOT re-seed existing tables (that would duplicate rows).
- **Removed** columns/tables in the ontology are **not dropped** from the DB — existing data is preserved; they
  simply disappear from the ontology/graph/YAML.
- Bump the ontology version (e.g. `1.0` → `1.1`) with `extends` pointing at the prior version.
