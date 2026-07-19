from __future__ import annotations

import json
from typing import Any

from ..session_store import session_store
from .output_schema import DomainResearchOutput
from .agents import search_planner, web_researcher, domain_synthesizer


class ResearchSpecialist:
    async def analyze(self, session_id: str) -> dict[str, Any]:
        """Run deep research based on intake output."""
        intake = session_store.get_value(session_id, "intake_output")
        if not intake:
            return {"type": "error", "response": "No intake data found. Complete the questionnaire first."}

        # Step 1: Plan search queries
        search_plan = await search_planner.run({"intake": intake})
        queries = search_plan.get("queries", [])

        # Step 2: Execute web searches via Azure OpenAI Responses API
        search_results = await web_researcher.run(queries)

        # Step 3: Synthesize domain knowledge
        raw = await domain_synthesizer.run({
            "intake": intake,
            "search_results": search_results,
        })

        try:
            research_output = DomainResearchOutput(**raw)
        except Exception:
            research_output = DomainResearchOutput(
                industry=intake.get("company_profile", {}).get("industry", "Unknown"),
                domain=intake.get("business_domain", {}).get("department", "Unknown"),
                recommended_object_types=raw.get("recommended_object_types", []),
                recommended_relationships=raw.get("recommended_relationships", []),
                best_practices=raw.get("best_practices", []),
            )

        session_store.update(session_id, "research_output", research_output.model_dump())
        session_store.update(session_id, "phase", "design")

        return {
            "type": "research_complete",
            "response": (
                f"Research complete! I found {len(research_output.recommended_object_types)} recommended object types "
                f"and {len(research_output.industry_patterns)} industry patterns. "
                f"Now I'll design your ontology."
            ),
            "output": research_output.model_dump(),
            "complete": True,
        }
