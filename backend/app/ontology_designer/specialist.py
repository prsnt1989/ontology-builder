from __future__ import annotations

import json
from typing import Any

from ..session_store import session_store
from .agents import object_type_agent, property_agent, relationship_agent


class OntologyDesignerSpecialist:
    async def analyze(self, session_id: str) -> dict[str, Any]:
        """Design object types, properties, and relationships."""
        intake = session_store.get_value(session_id, "intake_output")
        research = session_store.get_value(session_id, "research_output")

        if not intake or not research:
            return {"type": "error", "response": "Missing intake or research data."}

        # Flatten intake + research into a context the sub-agents expect
        context = {
            "industry": research.get("industry", intake.get("company_profile", {}).get("industry", "Unknown")),
            "domain": research.get("domain", intake.get("business_domain", {}).get("department", "Unknown")),
            "key_entities": intake.get("business_domain", {}).get("key_entities", []),
            "key_processes": intake.get("business_domain", {}).get("key_processes", []),
            "recommended_object_types": research.get("recommended_object_types", []),
            "recommended_relationships": research.get("recommended_relationships", []),
            "industry_patterns": research.get("industry_patterns", []),
            "domain_vocabulary": research.get("domain_vocabulary", {}),
            "user_roles": intake.get("user_roles", []),
            "data_sources": intake.get("data_sources", []),
            "problem_statement": intake.get("problem_statement", {}),
            "constraints": intake.get("constraints", {}),
        }

        # Step 1: Design object types
        object_types_result = await object_type_agent.run(context)
        object_types = object_types_result.get("object_types", [])

        # Step 2: Design properties for each type
        properties_result = await property_agent.run({
            **context,
            "object_types": object_types,
        })
        # Merge properties back into object types
        properties_by_type = properties_result.get("properties_by_type", {})
        for ot in object_types:
            type_name = ot["api_name"]
            if type_name in properties_by_type:
                ot["properties"] = properties_by_type[type_name]

        # Step 3: Design relationships
        relationships_result = await relationship_agent.run({
            **context,
            "object_types": object_types,
        })
        relationships = relationships_result.get("relationships", [])

        ontology_design = {
            "object_types": object_types,
            "relationships": relationships,
        }

        session_store.update(session_id, "ontology_design", ontology_design)
        session_store.update(session_id, "phase", "actions_rules")

        return {
            "type": "design_complete",
            "response": (
                f"Ontology design complete! Created {len(object_types)} object types "
                f"and {len(relationships)} relationships. Now generating actions, permissions, and rules."
            ),
            "output": ontology_design,
            "complete": True,
        }
