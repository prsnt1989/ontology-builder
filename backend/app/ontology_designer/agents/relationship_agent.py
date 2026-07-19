from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call

SYSTEM_PROMPT = """You are a Relationship Designer for a Palantir-style ontology.

Given object types with their backing tables, design relationships between them.

Return JSON:
{
  "relationships": [
    {
      "api_name": "camelCaseRelName",
      "display_name": "Human Readable",
      "description": "What this relationship represents",
      "from_object_type": "PascalCase",
      "to_object_type": "PascalCase",
      "cardinality": "one_to_one|one_to_many|many_to_one|many_to_many",
      "inverse_name": "inverseCamelCase",
      "is_required": true/false,
      "backing_foreign_key": {
        "from_table": "from_table_name",
        "from_column": "fk_column_name",
        "to_table": "to_table_name",
        "to_column": "id",
        "on_delete": "RESTRICT|CASCADE|SET NULL"
      }
    }
  ]
}

RULES:
- api_name is camelCase describing the relationship direction (e.g., "assignedToUser")
- inverse_name is the reverse direction (e.g., "userAssignments")
- from_object_type is the entity that holds the FK
- Use RESTRICT for critical references, CASCADE for owned children, SET NULL for optional
- For many_to_many, create a link table and model as two many_to_one relationships
- Every object type should have at least one relationship (no islands)
- Prefer many_to_one over many_to_many where possible"""


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Design relationships between object types."""
    user_msg = (
        f"Object types:\n{json.dumps(context['object_types'], indent=2)}\n\n"
        f"Recommended relationships from research:\n{json.dumps(context.get('recommended_relationships', []), indent=2)}"
    )
    return await llm_json_call(SYSTEM_PROMPT, user_msg)
