from __future__ import annotations

import json
import logging
from typing import Any

from ..shared.llm_client import llm_json_call
from ..shared.web_search import web_search
from ..session_store import session_store
from .agents.clarifier import format_block_questions
from .agents.refiner import refine_answers
from .blocks import TOTAL_BLOCKS
from .output_schema import IntakeOutput
from .prompt import EMITTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class IntakeSpecialist:
    async def analyze(self, session_id: str, user_message: str) -> dict[str, Any]:
        """Main entry point. Manages the questionnaire loop."""
        state = session_store.get_value(session_id, "intake_state")
        if not state:
            state = {
                "current_block": 1,
                "blocks_completed": [],
                "intent": {},
                "awaiting_input": False,
            }
            session_store.update(session_id, "intake_state", state)

        current_block = state["current_block"]

        # If we haven't started or just completed a block, present next questions
        if not state["awaiting_input"]:
            # If the user's first message has substance (not just "start"/"begin"/"hello"),
            # treat it as Block 1 answers and process immediately
            stripped = user_message.strip().lower()
            is_greeting = stripped in ("start", "begin", "hello", "hi", "hey", "continue", "")
            if current_block == 1 and not is_greeting:
                state["awaiting_input"] = True
                session_store.update(session_id, "intake_state", state)
                # Fall through to process the message as answers below
            else:
                result = await format_block_questions(current_block, state["intent"], state.get("company_research"))
                state["awaiting_input"] = True
                state["presented_questions"] = result["presented_questions"]
                session_store.update(session_id, "intake_state", state)
                return {
                    "type": "intake_questions",
                    "response": result["markdown"],
                    "progress": {
                        "block": current_block,
                        "total_blocks": TOTAL_BLOCKS,
                        "phase": "intake",
                    },
                    "complete": False,
                }

        # Process user's answers
        result = await refine_answers(user_message, current_block, state["intent"], state.get("presented_questions"))

        if result.get("clarification_needed"):
            return {
                "type": "intake_clarification",
                "response": result["clarification_needed"],
                "progress": {
                    "block": current_block,
                    "total_blocks": TOTAL_BLOCKS,
                    "phase": "intake",
                },
                "complete": False,
            }

        # Merge answers into intent
        answers = result.get("answers", {})
        state["intent"].update(answers)

        # Web search for company info (once, after company_name is captured)
        if "company_name" in state["intent"] and "company_research" not in state:
            company = state["intent"]["company_name"]
            industry = state["intent"].get("industry", "")
            query = f"{company} company overview products services industry"
            if industry:
                query += f" {industry}"
            logger.info("Searching web for company info: %s", company)
            results = await web_search(query, context=f"Learning about {company} to build a tailored data ontology")
            state["company_research"] = results
            session_store.update(session_id, "intake_state", state)

        if result.get("block_complete"):
            state["blocks_completed"].append(current_block)
            state["current_block"] = current_block + 1
            state["awaiting_input"] = False
            session_store.update(session_id, "intake_state", state)

            # Check if all blocks done
            if current_block >= TOTAL_BLOCKS:
                return await self._emit_output(session_id, state["intent"])

            # Present next block
            next_result = await format_block_questions(state["current_block"], state["intent"], state.get("company_research"))
            state["awaiting_input"] = True
            state["presented_questions"] = next_result["presented_questions"]
            session_store.update(session_id, "intake_state", state)
            return {
                "type": "intake_questions",
                "response": f"Block {current_block} complete!\n\n{next_result['markdown']}",
                "progress": {
                    "block": state["current_block"],
                    "total_blocks": TOTAL_BLOCKS,
                    "phase": "intake",
                },
                "complete": False,
            }

        # Block not yet complete — show remaining questions tailored to what we know so far
        remaining_result = await format_block_questions(current_block, state["intent"], state.get("company_research"))
        state["awaiting_input"] = True
        state["presented_questions"] = remaining_result["presented_questions"]
        session_store.update(session_id, "intake_state", state)
        return {
            "type": "intake_questions",
            "response": remaining_result["markdown"],
            "progress": {
                "block": current_block,
                "total_blocks": TOTAL_BLOCKS,
                "phase": "intake",
            },
            "complete": False,
        }

    async def _emit_output(self, session_id: str, intent: dict) -> dict[str, Any]:
        """Convert all collected answers into structured IntakeOutput."""
        user_msg = f"Collected answers from all 7 blocks:\n{json.dumps(intent, indent=2)}"
        raw = await llm_json_call(EMITTER_SYSTEM_PROMPT, user_msg, skill_phase="intake")

        try:
            intake_output = IntakeOutput(**raw)
        except Exception:
            intake_output = IntakeOutput()

        session_store.update(session_id, "intake_output", intake_output.model_dump())
        session_store.update(session_id, "phase", "research")

        return {
            "type": "intake_complete",
            "response": "Intake complete! I've captured your requirements. Now I'll research your domain to build an informed ontology.",
            "output": intake_output.model_dump(),
            "progress": {
                "block": TOTAL_BLOCKS,
                "total_blocks": TOTAL_BLOCKS,
                "phase": "research",
            },
            "complete": True,
        }
