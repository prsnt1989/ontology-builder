---
name: requirements-intake
description: Gather the organization/domain requirements that drive ontology design via a structured questionnaire. Use during the intake phase.
license: MIT
compatibility: Works with any model that supports tool use.
metadata:
  author: ontology-builder
  version: "1.0"
  phase: intake
  phases: [intake]
---

## Purpose

Intake collects the business context an informed ontology needs, across 7 blocks: Company Profile, Business
Domain, Problem Statement, Data Sources, Users & Permissions, Workflows, and Constraints & Requirements.

## Questioning

- Ask one block at a time; tailor options to the company's industry and prior answers (don't re-ask what's known).
- Prefer concrete multiple-choice options plus a free-text escape; capture the company name first (it seeds a web
  search for domain enrichment).
- Map each answer to its impact on the ontology (e.g. permission model → row-level filters; workflows → lifecycle
  states; data sources → backing tables).

## Output

Emit a structured `IntakeOutput`: `company_profile`, `business_domain` (key_entities/processes), `problem_statement`,
`data_sources`, `user_roles`, `workflows`, `constraints`. Expand abbreviations, infer 3–5 user roles from the
permission model, and list multiple data sources when the tech stack implies them. This output drives research and
design — completeness here improves every downstream phase.
