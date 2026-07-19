---
name: actions-and-permissions
description: Patterns for designing ontology actions, role-based permissions, validation rules, and lifecycle state machines. Use in the actions & rules phase.
license: MIT
compatibility: Works with any model that supports tool use.
metadata:
  author: ontology-builder
  version: "1.0"
  phase: actions_rules
---

## Actions

- Derive actions from the object types and the workflows captured during intake.
- Each action names the object type it operates on and its precondition(s).
- Model approval steps as guarded transitions, not free-form fields.

## Permissions

- Build role-based permissions from the user roles captured in intake.
- Scope permissions per object type and per action (view / edit / admin).
- For sensitive data (PII/PHI, financial), add property-level restrictions and audit actions.

## Validation rules

- Derive validation rules from known data-quality issues (nulls, formats, duplicates).
- Prefer declarative constraints tied to specific properties.

## Lifecycle state machines

- Give lifecycle-bearing object types an explicit set of states and transitions.
- Every transition has a `from`/`to` state; every non-initial state must be reachable.
- Side effects (notifications, assignments) hang off transitions, not states.
