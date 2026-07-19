"""Post-processor to fix lifecycle internal consistency issues.

The LLM often generates lifecycles where transitions reference state names
that don't match the actual state definitions. This module repairs that
immediately after generation, before validation.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def fix_lifecycles(lifecycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure all lifecycle transitions reference only defined state names."""
    fixed_count = 0

    for lc in lifecycles:
        obj_type = lc.get("object_type", "?")
        states = lc.get("states", [])
        transitions = lc.get("transitions", [])

        if not states:
            continue

        defined_names = {s["name"] for s in states if "name" in s}

        # Collect all referenced state names from transitions and allowed_transitions
        referenced_names = set()
        for t in transitions:
            referenced_names.add(t.get("from_state", ""))
            referenced_names.add(t.get("to_state", ""))
        for s in states:
            for at in s.get("allowed_transitions", []):
                referenced_names.add(at)
        referenced_names.discard("")

        # If references don't match definitions, we need to fix
        undefined_refs = referenced_names - defined_names
        if not undefined_refs:
            continue

        # Strategy: the transitions usually have the CORRECT domain names
        # while the states have generic names. Replace states with referenced names.
        # Build a mapping from defined states to what they should be.

        # If counts match, map positionally (initial→first ref'd, terminal→last ref'd, etc.)
        # Otherwise, rebuild the state list from the referenced names.
        all_from = [t.get("from_state") for t in transitions if t.get("from_state")]
        all_to = [t.get("to_state") for t in transitions if t.get("to_state")]

        # Determine initial state: the from_state that never appears as to_state
        to_set = set(all_to)
        from_set = set(all_from)
        initial_candidates = from_set - to_set
        terminal_candidates = to_set - from_set

        # Rebuild states from transitions (transitions are the source of truth)
        all_state_names = set()
        for t in transitions:
            if t.get("from_state"):
                all_state_names.add(t["from_state"])
            if t.get("to_state"):
                all_state_names.add(t["to_state"])
        # Also include allowed_transitions targets
        for s in states:
            for at in s.get("allowed_transitions", []):
                all_state_names.add(at)

        if not all_state_names:
            continue

        # Build new state list
        new_states = []
        for name in sorted(all_state_names):
            display_name = name.replace("_", " ").title()
            is_initial = name in initial_candidates
            is_terminal = name in terminal_candidates

            # Find allowed transitions for this state
            allowed = []
            for t in transitions:
                if t.get("from_state") == name and t.get("to_state"):
                    if t["to_state"] not in allowed:
                        allowed.append(t["to_state"])

            new_states.append({
                "name": name,
                "display_name": display_name,
                "description": f"State: {display_name}",
                "is_initial": is_initial,
                "is_terminal": is_terminal,
                "allowed_transitions": allowed,
            })

        # Ensure exactly one initial state
        initials = [s for s in new_states if s["is_initial"]]
        if len(initials) == 0 and new_states:
            new_states[0]["is_initial"] = True
        elif len(initials) > 1:
            for s in initials[1:]:
                s["is_initial"] = False

        # Ensure at least one terminal state
        terminals = [s for s in new_states if s["is_terminal"]]
        if not terminals:
            # Mark states with no outgoing transitions as terminal
            for s in new_states:
                if not s["allowed_transitions"]:
                    s["is_terminal"] = True

        lc["states"] = new_states
        fixed_count += 1
        logger.info(
            "Fixed lifecycle for %s: rebuilt %d states from transitions (was %d defined, %d undefined refs)",
            obj_type, len(new_states), len(defined_names), len(undefined_refs),
        )

    if fixed_count:
        logger.info("Post-processed %d/%d lifecycles with consistency fixes", fixed_count, len(lifecycles))

    return lifecycles
