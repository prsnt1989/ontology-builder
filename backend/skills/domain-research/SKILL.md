---
name: domain-research
description: Research the industry/domain to recommend object types, relationships, and best practices before design. Use during the research phase.
license: MIT
compatibility: Works with any model that supports tool use.
metadata:
  author: ontology-builder
  version: "1.0"
  phase: research
  phases: [research, update_research]
---

## Purpose

Research turns the intake requirements into domain knowledge that grounds the ontology: recommended object types,
typical relationships, industry patterns, and vocabulary. The research trace (planned queries → sources → findings)
is surfaced to the user for transparency.

## Approach

- Plan a small set of focused search queries from the intake (industry, department, key entities/processes).
- Run web searches; cross-reference multiple sources; keep source references for the trace.
- Synthesize into: `industry`, `domain`, `recommended_object_types`, `recommended_relationships`,
  `industry_patterns`, `best_practices`, `domain_vocabulary`.
- Recommendations are **advisory** — they inform the designer, they are not the final ontology. Favor
  domain-standard entities and connections that yield a well-connected model.
- For an update, research only the genuinely-new concepts introduced by the change, not the whole domain again.
