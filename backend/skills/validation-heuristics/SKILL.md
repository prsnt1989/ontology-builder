---
name: validation-heuristics
description: Completeness and consistency checks for a generated ontology, plus repair guidance. Use when validating an ontology before generation.
license: MIT
compatibility: Works with any model that supports tool use.
metadata:
  author: ontology-builder
  version: "1.0"
  phase: validation
  phases: [validation, update_validation]
---

## Completeness checks

- Every object type has a title property and at least one indexed field.
- Every relationship references object types that exist in the model.
- Lifecycle-bearing types have a status/state property matching their state machine.

## Consistency checks

- Property `backing_column`s are unique within a table.
- Enum values referenced by validation rules and lifecycle states actually exist.
- Foreign keys used by relationships map to real columns.

## Repair guidance

- Fix deterministic (lifecycle) critical issues first — they are unambiguous.
- Treat LLM-flagged issues as advisory; do not over-correct on hallucinated problems.
- Stop repairing when the critical count stops decreasing between iterations.
