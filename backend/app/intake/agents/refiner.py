from __future__ import annotations

import re
from typing import Any

from ...shared.llm_client import llm_json_call
from ..blocks import get_block
from ..prompt import REFINER_SYSTEM_PROMPT


def parse_compact_answers(raw: str, block: dict) -> dict[str, str]:
    """Parse '1:A, 2:C, 3:B' format into {question_id: selected_value}."""
    answers = {}
    questions = block["questions"]

    # Try compact format first: "1:A, 2:B, 3:C"
    pairs = re.findall(r"(\d+)\s*[:=]\s*([A-Ea-e](?:\b|$)|[^,]+)", raw)
    if pairs:
        for q_num_str, value in pairs:
            q_idx = int(q_num_str) - 1
            if q_idx < 0 or q_idx >= len(questions):
                continue
            q = questions[q_idx]
            value = value.strip()
            # If it's a single letter, map to option
            if len(value) == 1 and value.upper() in "ABCDE":
                opt_idx = ord(value.upper()) - 65
                if opt_idx < len(q["options"]):
                    answers[q["id"]] = q["options"][opt_idx]
                else:
                    answers[q["id"]] = value
            else:
                answers[q["id"]] = value
        return answers

    return {}


async def refine_answers(
    user_response: str,
    block_number: int,
    current_intent: dict[str, Any],
    presented_questions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Process user answers for a block. Returns parsed answers + completion status."""
    block = get_block(block_number)
    if not block:
        return {"answers": {}, "block_complete": False, "clarification_needed": "Invalid block"}

    # Only consider questions not already answered
    unanswered = [q for q in block["questions"] if q["id"] not in current_intent]
    if not unanswered:
        return {"answers": {}, "block_complete": True, "clarification_needed": None}

    # Override options with presented options (LLM-tailored) if available
    if presented_questions:
        pq_map = {pq["id"]: pq["options"] for pq in presented_questions}
        unanswered = [
            {**q, "options": pq_map[q["id"]]} if q["id"] in pq_map and pq_map[q["id"]] else q
            for q in unanswered
        ]

    # Try direct parsing against unanswered questions
    temp_block = {**block, "questions": unanswered}
    parsed = parse_compact_answers(user_response, temp_block)

    if parsed and len(parsed) == len(unanswered):
        return {
            "answers": parsed,
            "block_complete": True,
            "clarification_needed": None,
            "notes": "All remaining questions answered via compact format",
        }

    # Fall back to LLM parsing for natural language answers
    user_msg = (
        f"Block: {block['title']}\n"
        f"Questions (only unanswered): {[q['text'] for q in unanswered]}\n"
        f"Options per question: {[q['options'] for q in unanswered]}\n"
        f"Question IDs: {[q['id'] for q in unanswered]}\n\n"
        f"User response: {user_response}\n\n"
        f"Current intent state: {current_intent}"
    )

    result = await llm_json_call(REFINER_SYSTEM_PROMPT, user_msg)
    return result
