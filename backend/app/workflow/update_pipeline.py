"""MAF update-pipeline workflow.

Mirrors ``pipeline.py`` but MODIFIES an existing ontology in place using the
confirmed ``update_plan``. Reuses the same ``_PhaseExecutor`` scaffolding, event
helpers, ``PipelineState``, ``ApprovalRequest``, and HITL approval pattern.

Chain: update_design → update_actions_rules → update_validation → update_generating.
(Research is folded into design context; a dedicated research step is skipped since
updates operate on an already-researched ontology.)

Like ``pipeline.py``, this module avoids ``from __future__ import annotations`` so
MAF's ``@response_handler`` can read the ``ctx`` annotation from the raw signature.
"""

import logging
from typing import Any

from agent_framework import (
    Executor,
    Message,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)

from ..session_store import session_store
from ..actions_rules.specialist import ActionsRulesSpecialist
from ..validator.specialist import ValidatorSpecialist
from ..update_intake.agents import update_designer
from .. import generation
from .pipeline import PipelineState, ApprovalRequest, _phase_event, _activity_event

logger = logging.getLogger(__name__)


class UpdateDesignExecutor(Executor):
    """Applies the confirmed change plan to ontology_design via surgical patches."""

    def __init__(self) -> None:
        super().__init__(id="update_design")

    @handler
    async def run_phase(self, messages: list[Message], ctx: WorkflowContext[PipelineState, dict]) -> None:
        # Start executor: session id is bound on the instance.
        sid = self._session_id  # type: ignore[attr-defined]
        state = PipelineState(session_id=sid)
        await ctx.add_event(_phase_event(sid, "update_design", "running"))
        await ctx.add_event(_activity_event(sid, "update_design", "update_designer", "running", "Applying requested changes"))

        ontology = session_store.get_value(sid, "ontology_design") or {"object_types": [], "relationships": []}
        actions_rules = session_store.get_value(sid, "actions_rules") or {}
        update_plan = session_store.get_value(sid, "update_plan") or {"changes": []}

        try:
            result = await update_designer.run(ontology, actions_rules, update_plan)
        except Exception as e:  # noqa: BLE001
            logger.error("Update design failed: %s", e, exc_info=True)
            state.failed = True
            await ctx.add_event(_phase_event(sid, "update_design", "failed", str(e)))
            await ctx.yield_output({"phase": "update_design", "status": "failed", "message": str(e)})
            return

        # Persist the mutated ontology + actions_rules.
        session_store.update(sid, "ontology_design", ontology)
        session_store.update(sid, "actions_rules", actions_rules)

        summary = f"Applied {result.get('applied', 0)} change(s) to the ontology design."
        state.notes.append(summary)
        await ctx.add_event(_activity_event(sid, "update_design", "update_designer", "done", summary))
        await ctx.add_event(_phase_event(sid, "update_design", "done", summary))
        await ctx.yield_output({"phase": "update_design", "status": "done", "message": summary})
        await ctx.send_message(state)


class UpdateActionsRulesExecutor(Executor):
    """Regenerates actions/permissions/rules/lifecycles for the merged ontology.

    Reuses the existing ActionsRulesSpecialist over the full (merged) ontology so
    new object types get actions/permissions/lifecycles; then restores phase.
    """

    def __init__(self) -> None:
        super().__init__(id="update_actions_rules")

    @handler
    async def run_phase(self, state: PipelineState, ctx: WorkflowContext[PipelineState, dict]) -> None:
        if state.failed:
            return
        sid = state.session_id
        await ctx.add_event(_phase_event(sid, "update_actions_rules", "running"))
        await ctx.add_event(_activity_event(sid, "update_actions_rules", "actions_rules", "running"))
        try:
            result = await ActionsRulesSpecialist().analyze(sid)
        except Exception as e:  # noqa: BLE001
            logger.error("Update actions/rules failed: %s", e, exc_info=True)
            state.failed = True
            await ctx.add_event(_phase_event(sid, "update_actions_rules", "failed", str(e)))
            await ctx.yield_output({"phase": "update_actions_rules", "status": "failed", "message": str(e)})
            return
        # The reused specialist sets the build-flow phase ("validation"); re-assert the
        # update phase so a mid-flow reload shows the correct update timeline.
        session_store.update(sid, "phase", "update_validation")
        summary = result.get("response", "Actions, permissions, and rules updated.")
        state.notes.append(summary)
        await ctx.add_event(_activity_event(sid, "update_actions_rules", "actions_rules", "done", summary))
        await ctx.add_event(_phase_event(sid, "update_actions_rules", "done", summary))
        await ctx.yield_output({"phase": "update_actions_rules", "status": "done", "message": summary})
        await ctx.send_message(state)


class UpdateValidationExecutor(Executor):
    """Validates the merged ontology (reuses the existing validator + repair loop)."""

    def __init__(self) -> None:
        super().__init__(id="update_validation")

    @handler
    async def run_phase(self, state: PipelineState, ctx: WorkflowContext[PipelineState, dict]) -> None:
        if state.failed:
            return
        sid = state.session_id
        await ctx.add_event(_phase_event(sid, "update_validation", "running"))
        await ctx.add_event(_activity_event(sid, "update_validation", "validator", "running"))
        try:
            result = await ValidatorSpecialist().analyze(sid)
        except Exception as e:  # noqa: BLE001
            logger.error("Update validation failed: %s", e, exc_info=True)
            state.failed = True
            await ctx.add_event(_phase_event(sid, "update_validation", "failed", str(e)))
            await ctx.yield_output({"phase": "update_validation", "status": "failed", "message": str(e)})
            return

        # The reused validator sets phase to "generating"; re-assert the update phase.
        session_store.update(sid, "phase", "update_generating")
        report = session_store.get_value(sid, "validation_report") or {}
        summary = result.get("response", "Validation complete.")
        await ctx.add_event(_activity_event(sid, "update_validation", "validator", "done", summary))
        await ctx.add_event(_phase_event(sid, "update_validation", "done", summary))
        await ctx.yield_output(
            {
                "phase": "update_validation",
                "status": "done",
                "message": summary,
                "overall_score": report.get("overall_score"),
            }
        )
        await ctx.send_message(state)


class UpdateGenerationExecutor(Executor):
    """Writes versioned YAML, then HITL-approves before ADDITIVE DB provisioning."""

    def __init__(self, datastore: Any) -> None:
        super().__init__(id="update_generating")
        self._datastore = datastore

    @handler
    async def start(self, state: PipelineState, ctx: WorkflowContext[dict, dict]) -> None:
        if state.failed:
            return
        sid = state.session_id
        await ctx.add_event(_phase_event(sid, "update_generating", "running"))
        await ctx.add_event(_activity_event(sid, "update_generating", "yaml_writer", "running", "Writing updated YAML"))
        try:
            files = generation.write_ontology_yaml(sid, bump_version=True)
        except Exception as e:  # noqa: BLE001
            logger.error("Update YAML generation failed: %s", e, exc_info=True)
            await ctx.add_event(_phase_event(sid, "update_generating", "failed", str(e)))
            await ctx.yield_output({"phase": "update_generating", "status": "failed", "message": str(e)})
            return
        await ctx.add_event(_activity_event(sid, "update_generating", "yaml_writer", "done", f"{len(files)} files written"))

        ontology = session_store.get_value(sid, "ontology_design") or {}
        await ctx.request_info(
            ApprovalRequest(
                session_id=sid,
                kind="apply_ontology_updates",
                title="Apply updates to the database",
                detail=(
                    "This will add any new tables (created & seeded) and add new columns to existing "
                    "tables via ALTER TABLE. Existing data is preserved — nothing is dropped."
                ),
                tables=[ot.get("api_name", "") for ot in ontology.get("object_types", [])],
            ),
            response_type=bool,
        )

    @response_handler
    async def on_approval(self, request: ApprovalRequest, approved: bool, ctx: WorkflowContext[dict, dict]) -> None:
        sid = request.session_id
        if not approved:
            session_store.update(sid, "phase", "qa")
            await ctx.add_event(_phase_event(sid, "update_generating", "skipped", "Database update declined."))
            await ctx.yield_output(
                {
                    "phase": "update_generating",
                    "status": "skipped",
                    "message": (
                        "Updated ontology YAML files were written, but the database was not changed. "
                        "The Ontology and Graph views reflect the update; the Data Explorer still shows "
                        "the previous schema."
                    ),
                    "ontology_ready": True,
                }
            )
            return

        await ctx.add_event(_activity_event(sid, "update_generating", "datastore", "running", "Applying additive DB changes"))
        try:
            result = await generation.apply_ontology_updates_to_db(sid, self._datastore)
        except Exception as e:  # noqa: BLE001
            logger.error("Update provisioning failed: %s", e, exc_info=True)
            await ctx.add_event(_phase_event(sid, "update_generating", "failed", str(e)))
            await ctx.yield_output({"phase": "update_generating", "status": "failed", "message": str(e)})
            return

        session_store.update(sid, "phase", "qa")
        ontology = session_store.get_value(sid, "ontology_design") or {}
        intake = session_store.get_value(sid, "intake_output")
        suggestions = generation.generate_business_questions(ontology, intake)
        new_tables = result.get("tables_created", [])
        cols_added = result.get("columns_added", {})
        n_cols = sum(len(v) for v in cols_added.values())
        detail = f"{len(new_tables)} new table(s), {n_cols} new column(s)"
        await ctx.add_event(_activity_event(sid, "update_generating", "datastore", "done", detail))
        await ctx.add_event(_phase_event(sid, "update_generating", "done", "Ontology update applied."))
        await ctx.yield_output(
            {
                "phase": "update_generating",
                "status": "done",
                "ontology_ready": True,
                "message": (
                    f"Update complete! Applied your changes — {detail}. Existing data was preserved. "
                    "You can explore the updated ontology in the Graph and Ontology views, or ask questions."
                ),
                "tables_created": new_tables,
                "columns_added": cols_added,
                "seed_counts": result.get("seed_counts", {}),
                "follow_up_questions": suggestions,
            }
        )


def build_update_pipeline_workflow(session_id: str, datastore: Any) -> Workflow:
    """Build the update pipeline bound to a session id and datastore."""
    design = UpdateDesignExecutor()
    design._session_id = session_id  # type: ignore[attr-defined]
    actions_rules = UpdateActionsRulesExecutor()
    validation = UpdateValidationExecutor()
    generating = UpdateGenerationExecutor(datastore)

    return (
        WorkflowBuilder(
            name="ontology_update_pipeline",
            description="Apply confirmed changes: design patch → actions/rules → validation → additive generation.",
            start_executor=design,
            output_from="all",
        )
        .add_chain([design, actions_rules, validation, generating])
        .build()
    )
