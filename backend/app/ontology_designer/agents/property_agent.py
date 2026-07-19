from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call

SYSTEM_PROMPT = """You are a Property Designer for a Palantir-style ontology.

Given a list of object types (with their backing tables), design properties for each.

Return JSON:
{
  "properties_by_type": {
    "PascalCaseTypeName": [
      {
        "name": "snake_case_field",
        "display_name": "Human Readable",
        "description": "What this field represents",
        "type": "string|integer|float|boolean|date|datetime|enum|array",
        "required": true/false,
        "unique": true/false,
        "indexed": true/false,
        "default_value": null,
        "enum_values": [],
        "constraints": [],
        "backing_column": {
          "column_name": "snake_case_field",
          "sql_type": "VARCHAR(100)|INTEGER|REAL|TEXT|DATE",
          "nullable": true/false,
          "indexed": true/false,
          "check_constraint": null
        }
      }
    ]
  }
}

RULES:
- Each type should have 5-12 properties
- Always include: a business ID field (unique, indexed), title/name field, created_at, updated_at
- For entities with lifecycles, include a "state" or "status" enum field
- Match SQL types to property types (string→VARCHAR/TEXT, integer→INTEGER, etc.)
- Mark commonly-searched fields as indexed
- Include realistic enum_values for enum properties (3-6 values)
- Constraints use format: "min_length:N", "max_length:N", "min:N", "max:N", "pattern:regex"
"""


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Design properties for each object type."""
    user_msg = (
        f"Object types to design properties for:\n{json.dumps(context['object_types'], indent=2)}\n\n"
        f"Industry: {context.get('industry', 'Unknown')}\n"
        f"Domain vocabulary: {json.dumps(context.get('domain_vocabulary', {}), indent=2)}"
    )
    return await llm_json_call(SYSTEM_PROMPT, user_msg, skill_phase="design")
