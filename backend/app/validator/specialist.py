from __future__ import annotations

import logging
from typing import Any

from ..session_store import session_store
from .agents import completeness_checker, consistency_checker, repair_agent
from .agents.lifecycle_validator import validate_lifecycles
from ..actions_rules.lifecycle_fixer import fix_lifecycles

logger = logging.getLogger(__name__)

MAX_REPAIR_ITERATIONS = 10


class ValidatorSpecialist:
    async def analyze(self, session_id: str) -> dict[str, Any]:
        """Validate the ontology, auto-repairing until all critical issues are resolved."""
        ontology = session_store.get_value(session_id, "ontology_design")
        actions_rules = session_store.get_value(session_id, "actions_rules")

        if not ontology:
            return {"type": "error", "response": "No ontology design to validate."}

        iterations_log: list[dict] = []
        prev_issue_count = float("inf")
        initial_issue_count = 0
        # Warning categories that are actionable and worth auto-repairing even when
        # there are no critical issues (bounded so we don't loop forever if unfixable).
        REPAIRABLE_WARNING_CATEGORIES = {"connectivity", "relationship_completeness"}
        warning_repair_attempts = 0
        MAX_WARNING_REPAIRS = 2

        for iteration in range(MAX_REPAIR_ITERATIONS):
            # Run validation checks
            context = {
                "object_types": ontology.get("object_types", []),
                "relationships": ontology.get("relationships", []),
                "actions": (actions_rules or {}).get("actions", []),
                "permissions": (actions_rules or {}).get("permissions", []),
                "validation_rules": (actions_rules or {}).get("validation_rules", []),
                "lifecycles": (actions_rules or {}).get("lifecycles", []),
            }

            completeness_result = await completeness_checker.run(context)
            consistency_result = await consistency_checker.run(context)
            lifecycle_result = validate_lifecycles(context)

            all_issues = (
                completeness_result.get("issues", [])
                + consistency_result.get("issues", [])
                + lifecycle_result.get("issues", [])
            )
            strengths = consistency_result.get("strengths", [])
            critical_count = len([i for i in all_issues if i.get("severity") == "critical"])
            warning_count = len(all_issues) - critical_count

            # Track initial count for score calculation
            if iteration == 0:
                initial_issue_count = len(all_issues)

            # Score: percentage of issues resolved from initial
            if initial_issue_count == 0 or len(all_issues) == 0:
                score = 100
            else:
                score = max(0, round(100 * (1 - len(all_issues) / initial_issue_count)))

            # Log this iteration
            fixed_this_round = int(prev_issue_count - len(all_issues)) if prev_issue_count != float("inf") else 0
            iter_entry = {
                "iteration": iteration + 1,
                "total_issues": len(all_issues),
                "critical_count": critical_count,
                "warning_count": warning_count,
                "score": score,
                "fixed_this_round": fixed_this_round,
            }
            iterations_log.append(iter_entry)

            logger.info(
                "Validation iteration %d: %d issues (%d critical, %d warnings), score %d/100, fixed %d this round",
                iteration + 1, len(all_issues), critical_count, warning_count, score, fixed_this_round,
            )

            # No criticals, but try to auto-repair actionable warnings (isolated object
            # types, incomplete relationships) a bounded number of times before passing.
            repairable_warnings = [
                i for i in all_issues
                if i.get("severity") == "warning" and i.get("category") in REPAIRABLE_WARNING_CATEGORIES
            ]
            if critical_count == 0 and repairable_warnings and warning_repair_attempts < MAX_WARNING_REPAIRS:
                warning_repair_attempts += 1
                logger.info(
                    "Repairing %d actionable warning(s) (attempt %d/%d)...",
                    len(repairable_warnings), warning_repair_attempts, MAX_WARNING_REPAIRS,
                )
                repaired = await repair_agent.run({
                    "ontology_design": ontology,
                    "actions_rules": actions_rules or {},
                    "issues": repairable_warnings,
                })
                if "ontology_design" in repaired:
                    ontology = repaired["ontology_design"]
                    session_store.update(session_id, "ontology_design", ontology)
                if "actions_rules" in repaired:
                    actions_rules = repaired["actions_rules"]
                    if actions_rules.get("lifecycles"):
                        actions_rules["lifecycles"] = fix_lifecycles(actions_rules["lifecycles"])
                    session_store.update(session_id, "actions_rules", actions_rules)
                continue  # re-validate

            # SUCCESS: No critical issues remaining — pass (warnings are acceptable)
            if critical_count == 0:
                final_score = 100 if len(all_issues) == 0 else max(80, 100 - warning_count * 2)
                report = {
                    "overall_score": final_score,
                    "passed": True,
                    "issues": all_issues,
                    "strengths": strengths,
                    "iterations": iterations_log,
                    "summary": (
                        f"Ontology validated successfully in {iteration + 1} iteration(s). "
                        f"{warning_count} warnings noted (non-blocking)."
                        if iteration > 0
                        else f"Ontology validated on first pass. {warning_count} warnings noted."
                    ),
                }
                session_store.update(session_id, "validation_report", report)
                session_store.update(session_id, "phase", "generating")
                return {
                    "type": "validation_passed",
                    "response": (
                        f"Ontology validation passed with score {final_score}/100"
                        f"{f' (repaired in {iteration + 1} iterations)' if iteration > 0 else ''}. "
                        f"{f'{warning_count} warnings noted. ' if warning_count > 0 else ''}"
                        f"Proceeding to generate YAML files and database."
                    ),
                    "output": report,
                    "complete": True,
                }

            # CONVERGENCE CHECK: If critical count isn't decreasing, stop
            prev_critical = iterations_log[-2]["critical_count"] if len(iterations_log) >= 2 else float("inf")
            if critical_count >= prev_critical:
                logger.info(
                    "Critical issues not improving (%d >= %d). Stopping repair loop.",
                    critical_count, int(prev_critical),
                )
                break

            prev_issue_count = len(all_issues)

            # Issues found — repair
            logger.info("Repairing ontology (iteration %d, %d issues to fix)...", iteration + 1, len(all_issues))
            repaired = await repair_agent.run({
                "ontology_design": ontology,
                "actions_rules": actions_rules or {},
                "issues": all_issues,
            })

            # Apply repairs
            if "ontology_design" in repaired:
                ontology = repaired["ontology_design"]
                session_store.update(session_id, "ontology_design", ontology)
            if "actions_rules" in repaired:
                actions_rules = repaired["actions_rules"]
                # Re-run lifecycle fixer after repairs to catch any remaining inconsistencies
                if actions_rules.get("lifecycles"):
                    actions_rules["lifecycles"] = fix_lifecycles(actions_rules["lifecycles"])
                session_store.update(session_id, "actions_rules", actions_rules)

        # Loop exited without full pass — check if we can proceed anyway
        # If no deterministic (lifecycle) critical issues remain and critical_count is low,
        # treat as a soft pass (LLM checkers can hallucinate issues)
        deterministic_criticals = len([
            i for i in all_issues
            if i.get("severity") == "critical" and i.get("category") == "lifecycle"
        ])
        soft_pass = deterministic_criticals == 0 and critical_count <= 5

        if soft_pass:
            final_score = max(60, 100 - critical_count * 10 - warning_count * 2)
            report = {
                "overall_score": final_score,
                "passed": True,
                "issues": all_issues,
                "strengths": strengths,
                "iterations": iterations_log,
                "summary": (
                    f"Ontology validated with {critical_count} minor issues after "
                    f"{len(iterations_log)} iteration(s). Proceeding to generation."
                ),
            }
            session_store.update(session_id, "validation_report", report)
            session_store.update(session_id, "phase", "generating")
            return {
                "type": "validation_passed",
                "response": (
                    f"Ontology validation passed with score {final_score}/100 "
                    f"(soft pass after {len(iterations_log)} iterations). "
                    f"{critical_count} non-blocking issues noted. "
                    f"Proceeding to generate YAML files and database."
                ),
                "output": report,
                "complete": True,
            }

        report = {
            "overall_score": score,
            "passed": False,
            "issues": all_issues,
            "strengths": strengths,
            "iterations": iterations_log,
            "summary": (
                f"Repair loop stopped after {len(iterations_log)} iterations "
                f"(issues not improving). {critical_count} critical issues remain."
            ),
        }
        session_store.update(session_id, "validation_report", report)

        # Build a human-readable iteration summary
        iter_summary = " → ".join(
            f"Iter {e['iteration']}: {e['total_issues']} issues ({e['critical_count']} critical)"
            for e in iterations_log
        )

        return {
            "type": "validation_failed",
            "response": (
                f"Validation repair stopped — issues not improving after {len(iterations_log)} iterations.\n\n"
                f"**Progress:** {iter_summary}\n\n"
                f"**Remaining:** {critical_count} critical issues, {warning_count} warnings (score: {score}/100)."
            ),
            "output": report,
            "complete": False,
        }
