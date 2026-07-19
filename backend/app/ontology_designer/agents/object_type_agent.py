from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call

SYSTEM_PROMPT = """You are an Object Type Designer for a Palantir-style ontology.

Given intake information and domain research, design the core object types (entities).

Return JSON:
{
  "object_types": [
    {
      "api_name": "PascalCaseName",
      "display_name": "Human Readable",
      "plural_display_name": "Human Readable Plural",
      "description": "Clear 1-2 sentence description",
      "primary_key": "business_id_field_name",
      "icon": "icon-name",
      "title_property": "the_field_used_as_display_title",
      "backing_table": {
        "table_name": "snake_case_plural",
        "schema_name": "public",
        "primary_key_column": "id"
      }
    }
  ]
}

RULES:
- Generate 8-15 object types based on the domain
- api_name is PascalCase, table_name is snake_case plural
- Include audit-related types (AuditLog) if compliance requires it
- Include link/junction types for many-to-many relationships
- Every type must have a backing_table mapping
- title_property is the field shown as the entity's name in UIs"""


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Design object types from intake + research context."""
    user_msg = (
        f"Industry: {context.get('industry', 'Unknown')}\n"
        f"Domain: {context.get('domain', 'Unknown')}\n"
        f"Key entities from intake: {json.dumps(context.get('key_entities', []))}\n"
        f"Key processes: {json.dumps(context.get('key_processes', []))}\n"
        f"Recommended types from research: {json.dumps(context.get('recommended_object_types', []))}\n"
        f"Industry patterns: {json.dumps(context.get('industry_patterns', []), indent=2)}"
    )
    return await llm_json_call(SYSTEM_PROMPT, user_msg)
