"""Deterministic lifecycle validation — no LLM needed."""
from __future__ import annotations

from typing import Any


def validate_lifecycles(context: dict[str, Any]) -> dict[str, Any]:
    """Check lifecycle state/transition consistency with pure Python logic."""
    lifecycles = context.get("lifecycles", [])
    object_type_names = {ot.get("api_name") for ot in context.get("object_types", [])}
    issues: list[dict[str, Any]] = []

    for lc in lifecycles:
        obj_type = lc.get("object_type", "unknown")
        states = lc.get("states", [])
        transitions = lc.get("transitions", [])

        # Check object_type exists
        if obj_type not in object_type_names:
            issues.append({
                "severity": "critical",
                "category": "lifecycle",
                "component": f"Lifecycle:{obj_type}",
                "message": f"Lifecycle references non-existent object type '{obj_type}'",
                "suggestion": f"Remove the lifecycle or add object type '{obj_type}'",
            })
            continue

        defined_state_names = {s.get("name") for s in states if s.get("name")}

        # Check allowed_transitions reference defined states
        for state in states:
            state_name = state.get("name", "")
            for target in state.get("allowed_transitions", []):
                if target not in defined_state_names:
                    issues.append({
                        "severity": "critical",
                        "category": "lifecycle",
                        "component": f"Lifecycle:{obj_type}.{state_name}",
                        "message": f"allowed_transition '{target}' not in defined states {sorted(defined_state_names)}",
                        "suggestion": f"Add state '{target}' or remove it from allowed_transitions",
                    })

        # Check transitions reference defined states
        for t in transitions:
            from_s = t.get("from_state", "")
            to_s = t.get("to_state", "")
            if from_s and from_s not in defined_state_names:
                issues.append({
                    "severity": "critical",
                    "category": "lifecycle",
                    "component": f"Lifecycle:{obj_type}",
                    "message": f"Transition from_state '{from_s}' not in defined states {sorted(defined_state_names)}",
                    "suggestion": f"Add state '{from_s}' or fix the transition",
                })
            if to_s and to_s not in defined_state_names:
                issues.append({
                    "severity": "critical",
                    "category": "lifecycle",
                    "component": f"Lifecycle:{obj_type}",
                    "message": f"Transition to_state '{to_s}' not in defined states {sorted(defined_state_names)}",
                    "suggestion": f"Add state '{to_s}' or fix the transition",
                })

        # Structural checks
        initial_states = [s for s in states if s.get("is_initial")]
        terminal_states = [s for s in states if s.get("is_terminal")]

        if len(initial_states) == 0:
            issues.append({
                "severity": "warning",
                "category": "lifecycle",
                "component": f"Lifecycle:{obj_type}",
                "message": "No initial state defined",
                "suggestion": "Mark one state as is_initial: true",
            })
        elif len(initial_states) > 1:
            issues.append({
                "severity": "warning",
                "category": "lifecycle",
                "component": f"Lifecycle:{obj_type}",
                "message": f"Multiple initial states: {[s['name'] for s in initial_states]}",
                "suggestion": "Only one state should be is_initial: true",
            })

        if len(terminal_states) == 0:
            issues.append({
                "severity": "warning",
                "category": "lifecycle",
                "component": f"Lifecycle:{obj_type}",
                "message": "No terminal state defined",
                "suggestion": "Mark at least one state as is_terminal: true",
            })

    return {"issues": issues}
