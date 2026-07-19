from __future__ import annotations

import json
import re
from typing import Any

from ...shared.llm_client import llm_call
from ..blocks import get_block, TOTAL_BLOCKS
from ..prompt import CONTEXTUAL_QUESTIONS_PROMPT


def _extract_presented_questions(markdown: str, question_ids: list[str]) -> list[dict]:
    """Parse LLM-generated markdown to extract presented options per question."""
    questions = []
    q_sections = re.split(r'\*\*Question \d+:', markdown)
    for i, section in enumerate(q_sections[1:]):
        if i >= len(question_ids):
            break
        options = re.findall(r'^\s*[A-E]\)\s*(.+)$', section, re.MULTILINE)
        questions.append({"id": question_ids[i], "options": options})
    return questions


def _format_static(block: dict) -> dict[str, Any]:
    """Format a block's questions as static markdown (no LLM)."""
    block_number = block["block_number"]
    lines = []
    lines.append(f"**BLOCK {block_number}/{TOTAL_BLOCKS}: {block['title']}**")
    lines.append(f"_{block['description']}_")
    lines.append("")

    presented_questions = []
    for i, q in enumerate(block["questions"], 1):
        lines.append(f"**Question {i}: {q['text']}**")
        lines.append(f"_Impact: {q['impact']}_")
        lines.append("")
        if q["options"]:
            for j, opt in enumerate(q["options"]):
                letter = chr(65 + j)
                lines.append(f"  {letter}) {opt}")
            lines.append("")
            presented_questions.append({"id": q["id"], "options": list(q["options"])})
        else:
            lines.append("  _(Free text — type your answer)_")
            lines.append("")
            presented_questions.append({"id": q["id"], "options": []})

    lines.append("---")
    lines.append("Reply with option letters (e.g., `1:A, 2:C, 3:B`) or provide custom answers.")
    return {
        "markdown": "\n".join(lines),
        "presented_questions": presented_questions,
    }


async def format_block_questions(
    block_number: int,
    previous_answers: dict[str, Any] | None = None,
    company_research: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Format a questionnaire block, tailoring to context when prior answers exist."""
    block = get_block(block_number)
    if not block:
        return {"markdown": "", "presented_questions": []}

    if not previous_answers:
        return _format_static(block)

    company_name = previous_answers.get("company_name", "the company")
    industry = previous_answers.get("industry", "unknown")

    # Only include questions that haven't been answered yet
    unanswered = [q for q in block["questions"] if q["id"] not in previous_answers]
    if not unanswered:
        return {"markdown": "", "presented_questions": []}

    user_msg = (
        f"COMPANY NAME: {company_name}\n"
        f"INDUSTRY: {industry}\n\n"
    )

    # Include web research if available
    if company_research:
        research_text = "\n".join(
            f"- {r.get('title', '')}: {r.get('snippet', '')}"
            for r in company_research[:5]
        )
        user_msg += f"COMPANY RESEARCH (from web search):\n{research_text}\n\n"

    user_msg += (
        f"ALL PREVIOUS ANSWERS:\n{json.dumps(previous_answers, indent=2)}\n\n"
        f"BLOCK TEMPLATE TO ADAPT (only unanswered questions):\n"
        f"Block {block_number}/{TOTAL_BLOCKS}: {block['title']}\n"
        f"Description: {block['description']}\n"
        f"Questions to present ({len(unanswered)} remaining):\n"
    )
    for q in unanswered:
        user_msg += f"- ID: {q['id']}, Text: {q['text']}, Options: {q['options']}, Impact: {q['impact']}\n"

    user_msg += f"\nREMINDER: Use \"{company_name}\" (the FULL company name) in every question. Industry is \"{industry}\". Number questions starting at 1. Use the company research to make options specific to what this company actually does."

    tailored = await llm_call(CONTEXTUAL_QUESTIONS_PROMPT, user_msg, skill_phase="intake")

    question_ids = [q["id"] for q in unanswered]
    presented_questions = _extract_presented_questions(tailored, question_ids)

    return {
        "markdown": tailored,
        "presented_questions": presented_questions,
    }
