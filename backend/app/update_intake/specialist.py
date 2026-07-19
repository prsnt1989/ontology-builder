"""Update-intake specialist: conversational gathering of ontology change requests.

Mirrors the build-flow IntakeSpecialist but for MODIFYING an existing ontology:
- the user adds one or more free-text change requests while exploring;
- for each request, adaptive follow-up questions (tailored to the request + the
  existing ontology) are asked until the change is fully specified;
- when the user is done, all changes are summarized into a structured ``update_plan``
  and the user is asked to confirm;
- on confirmation the phase advances to ``update_research`` (which the frontend uses
  to auto-start the SSE update pipeline).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from ..session_store import session_store
from ..shared.llm_client import llm_json_call
from .ontology_summary import summarize_ontology
from .prompt import CHANGE_ANALYZER_PROMPT, UPDATE_PLAN_PROMPT

logger = logging.getLogger(__name__)

# Phrases that mean "I'm done adding changes — proceed to summary".
_DONE_PHRASES = (
    "done", "that's all", "thats all", "proceed", "no more", "finish", "finished",
    "go ahead", "implement", "apply changes", "apply the changes", "that is all",
    "nothing else", "all done", "continue",
)
# Phrases that mean "confirm and start implementing".
_CONFIRM_PHRASES = ("confirm", "yes", "approve", "looks good", "lgtm", "do it", "proceed", "apply", "go")
# Phrases that mean "I want to add another change" after a summary.
_ADD_MORE_PHRASES = ("add", "another", "more", "also", "one more", "wait", "change")


def _default_state() -> dict[str, Any]:
    return {
        "change_requests": [],   # [{id, text, qa: [{q, a}], understood, affected, kind, status}]
        "current_index": None,   # index into change_requests currently gathering
        "awaiting_confirmation": False,
    }


class UpdateIntakeSpecialist:
    async def analyze(self, session_id: str, user_message: str) -> dict[str, Any]:
        state = session_store.get_value(session_id, "update_state")
        if not state:
            state = _default_state()
            session_store.update(session_id, "update_state", state)

        ontology = session_store.get_value(session_id, "ontology_design") or {}
        actions_rules = session_store.get_value(session_id, "actions_rules") or {}
        summary = summarize_ontology(ontology, actions_rules)

        msg = user_message.strip()
        low = msg.lower()

        # --- Batch submission (from the "Request changes" modal) ---
        # First line is the "[BATCH]" sentinel; remaining non-empty lines are individual
        # change requests collected & approved in the modal. Seed them all, then start
        # follow-ups on the first.
        if msg.startswith("[BATCH]") and not state["change_requests"]:
            lines = [ln.strip("-• \t") for ln in msg.splitlines()[1:]]
            changes = [ln for ln in lines if ln]
            if changes:
                return await self._seed_batch(session_id, state, changes, summary)

        # --- Confirmation stage ---
        if state.get("awaiting_confirmation"):
            if any(p in low for p in _CONFIRM_PHRASES) and not any(p in low for p in ("no", "not", "wait", "add")):
                return await self._confirm(session_id, state)
            if any(low.startswith(p) or p in low for p in _ADD_MORE_PHRASES):
                # User wants to add more — treat this message as a new change request.
                state["awaiting_confirmation"] = False
                session_store.update(session_id, "update_state", state)
                return await self._new_request(session_id, state, msg, summary)
            # Unclear — re-show the summary.
            return self._summary_response(session_id, state, reshow=True)

        # --- Gathering stage ---
        current_idx = state.get("current_index")

        # If we're mid-request (awaiting answers to follow-ups)
        if current_idx is not None and current_idx < len(state["change_requests"]):
            req = state["change_requests"][current_idx]
            if req["status"] == "gathering":
                # "done" during gathering means: finalize this request as-is, then summarize
                if low in _DONE_PHRASES:
                    req["status"] = "ready"
                    state["current_index"] = None
                    session_store.update(session_id, "update_state", state)
                    return await self._maybe_summarize(session_id, state, summary)
                # Otherwise, record the answer and re-analyze
                req.setdefault("qa", []).append({"q": req.get("_last_questions", []), "a": msg})
                return await self._analyze_request(session_id, state, current_idx, summary)

        # Not mid-request: is the user done, or starting a new change?
        if low in _DONE_PHRASES and state["change_requests"]:
            return await self._maybe_summarize(session_id, state, summary)

        # New change request
        return await self._new_request(session_id, state, msg, summary)

    async def _new_request(
        self, session_id: str, state: dict, text: str, summary: str
    ) -> dict[str, Any]:
        req = {
            "id": str(uuid.uuid4())[:8],
            "text": text,
            "qa": [],
            "understood": "",
            "affected": [],
            "kind": "modify",
            "status": "gathering",
        }
        state["change_requests"].append(req)
        idx = len(state["change_requests"]) - 1
        state["current_index"] = idx
        session_store.update(session_id, "update_state", state)
        return await self._analyze_request(session_id, state, idx, summary)

    async def _seed_batch(
        self, session_id: str, state: dict, changes: list[str], summary: str
    ) -> dict[str, Any]:
        """Seed a batch of change requests (from the modal), then gather the first."""
        for text in changes:
            state["change_requests"].append(
                {
                    "id": str(uuid.uuid4())[:8],
                    "text": text,
                    "qa": [],
                    "understood": "",
                    "affected": [],
                    "kind": "modify",
                    "status": "gathering",
                }
            )
        state["current_index"] = 0
        session_store.update(session_id, "update_state", state)
        return await self._analyze_request(session_id, state, 0, summary)

    def _next_gathering_index(self, state: dict) -> int | None:
        """Index of the next request still needing follow-ups, or None if all ready."""
        for i, r in enumerate(state["change_requests"]):
            if r["status"] == "gathering":
                return i
        return None

    async def _analyze_request(
        self, session_id: str, state: dict, idx: int, summary: str
    ) -> dict[str, Any]:
        req = state["change_requests"][idx]
        qa_text = "\n".join(
            f"Q: {item['q']}\nA: {item['a']}" for item in req.get("qa", []) if item.get("a")
        )
        user_msg = (
            f"EXISTING ONTOLOGY:\n{summary}\n\n"
            f"CHANGE REQUEST:\n{req['text']}\n\n"
            f"CLARIFYING ANSWERS SO FAR:\n{qa_text or '(none yet)'}"
        )
        try:
            result = await llm_json_call(CHANGE_ANALYZER_PROMPT, user_msg)
        except Exception as e:  # noqa: BLE001
            logger.warning("Change analyzer failed: %s", e)
            result = {"needs_clarification": False, "questions": []}

        req["understood"] = result.get("understood_summary", req.get("understood", ""))
        req["affected"] = result.get("affected_object_types", [])
        req["kind"] = result.get("change_kind", "modify")

        if result.get("needs_clarification") and result.get("questions"):
            questions = result["questions"][:4]
            req["_last_questions"] = questions
            session_store.update(session_id, "update_state", state)
            total = len(state["change_requests"])
            label = f"Change {idx + 1} of {total}" if total > 1 else "Change"
            body = (
                f"**{label}:** {req['understood'] or req['text']}\n\n"
                "A few details to get this right:\n\n"
                + "\n".join(f"- {q}" for q in questions)
            )
            return {
                "type": "update_questions",
                "response": body,
                "progress": {"phase": "update_intake"},
                "output": {
                    "kind": "gathering",
                    # NOTE: questions are shown as bullets in the response body and
                    # answered in free text — they are NOT follow-up "chips" (those are
                    # a QA-only affordance for suggested next questions).
                    "change_requests": _public_requests(state),
                },
                "complete": False,
            }

        # No clarification needed — this request is ready.
        req["status"] = "ready"

        # Auto-advance to the next request that still needs follow-ups (batch flow).
        next_idx = self._next_gathering_index(state)
        if next_idx is not None:
            state["current_index"] = next_idx
            session_store.update(session_id, "update_state", state)
            return await self._analyze_request(session_id, state, next_idx, summary)

        # All requests are ready — go straight to the summary + confirmation.
        state["current_index"] = None
        session_store.update(session_id, "update_state", state)
        return await self._maybe_summarize(session_id, state, summary)

    async def _maybe_summarize(self, session_id: str, state: dict, summary: str) -> dict[str, Any]:
        ready = [r for r in state["change_requests"] if r["status"] == "ready"]
        if not ready:
            return {
                "type": "update_questions",
                "response": "Describe a change you'd like to make to the ontology.",
                "progress": {"phase": "update_intake"},
                "complete": False,
            }
        # Build the structured plan
        requests_text = "\n\n".join(
            f"Change {i+1}: {r['text']}\n"
            + "\n".join(f"  Q: {item['q']}\n  A: {item['a']}" for item in r.get("qa", []) if item.get("a"))
            for i, r in enumerate(ready)
        )
        user_msg = f"EXISTING ONTOLOGY:\n{summary}\n\nCHANGE REQUESTS:\n{requests_text}"
        try:
            plan = await llm_json_call(UPDATE_PLAN_PROMPT, user_msg)
        except Exception as e:  # noqa: BLE001
            logger.warning("Update plan generation failed: %s", e)
            plan = {
                "changes": [{"title": r["text"], "kind": r["kind"], "detail": r.get("understood", ""),
                             "affected_object_types": r.get("affected", [])} for r in ready],
                "summary_markdown": "\n".join(f"- {r['text']}" for r in ready),
            }

        session_store.update(session_id, "update_plan", plan)
        state["awaiting_confirmation"] = True
        session_store.update(session_id, "update_state", state)
        return self._summary_response(session_id, state, plan=plan)

    def _summary_response(self, session_id: str, state: dict, plan: dict | None = None, reshow: bool = False) -> dict[str, Any]:
        if plan is None:
            plan = session_store.get_value(session_id, "update_plan") or {}
        summary_md = plan.get("summary_markdown", "")
        prefix = "Here's a summary of the changes I'll make:" if not reshow else "Just to confirm, here are the changes:"
        body = (
            f"{prefix}\n\n{summary_md}\n\n"
            "**Confirm** to apply these changes, or tell me another change to add."
        )
        return {
            "type": "update_summary",
            "response": body,
            "progress": {"phase": "update_intake"},
            "output": {
                "kind": "summary",
                "changes": plan.get("changes", []),
                "summary_markdown": summary_md,
                "awaiting_confirmation": True,
            },
            "complete": False,
        }

    async def _confirm(self, session_id: str, state: dict) -> dict[str, Any]:
        state["awaiting_confirmation"] = False
        state["confirmed"] = True
        session_store.update(session_id, "update_state", state)
        session_store.update(session_id, "phase", "update_research")
        return {
            "type": "update_confirmed",
            "response": "Confirmed. I'll now research, redesign, validate, and apply your changes.",
            "progress": {"phase": "update_research"},
            "output": {"kind": "confirmed"},
            "complete": True,
        }


def _public_requests(state: dict) -> list[dict[str, Any]]:
    """Client-facing view of the running change list."""
    return [
        {"id": r["id"], "text": r["text"], "understood": r.get("understood", ""), "status": r["status"]}
        for r in state.get("change_requests", [])
    ]
