---
name: nl-to-sql
description: Translate natural-language questions into safe SQLite queries against the generated ontology schema. Use in the Q&A phase.
license: MIT
compatibility: Works with any model that supports tool use.
metadata:
  author: ontology-builder
  version: "1.0"
  phase: qa
  phases: [qa]
---

## Rules

- ONLY use table and column names that appear in the provided schema. Never invent columns.
- Use JOINs based on the foreign-key relationships shown in the schema.
- For status/state queries, use the actual column name from the schema.
- Limit results to 50 rows unless the question asks for counts/aggregates.
- Use readable column aliases in SELECT.
- Only SELECT queries are permitted — never mutate data.
- If a question references a concept not in the schema, explain what is available instead.
- If ambiguous, make a reasonable assumption and state it.
