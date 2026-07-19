"""MAF pipeline workflow.

Wraps the existing specialist pipeline (research → design → actions_rules →
validation → generation) as a Microsoft Agent Framework ``Workflow``. Each phase
is an :class:`Executor` bound to a session id, so:

- the engine emits ``executor_invoked`` / ``executor_completed`` events per phase,
  which AG-UI turns into ``STEP_STARTED`` / ``STEP_FINISHED`` (the phase timeline);
- each executor emits custom ``phase_status`` / ``agent_activity`` events for the
  live activity feed and research trace;
- the final generation step is gated behind ``ctx.request_info`` (human-in-the-loop
  approval) before it provisions and seeds the database.

Intake stays conversational on ``/api/chat``; the frontend starts this workflow
once intake completes (phase == "research").

Note: this module deliberately does NOT use ``from __future__ import annotations``.
MAF's ``@response_handler`` validates the ``ctx`` annotation from the raw signature
(not ``get_type_hints``), so stringized annotations would fail validation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from agent_framework import (
    Executor,
    Message,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowEvent,
    handler,
    response_handler,
)

from ..session_store import session_store
from ..research.specialist import ResearchSpecialist
from ..ontology_designer.specialist import OntologyDesignerSpecialist
from ..actions_rules.specialist import ActionsRulesSpecialist
from ..validator.specialist import ValidatorSpecialist
from .. import generation

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Flows between pipeline executors. Domain data lives in ``session_store``."""

    session_id: str
    notes: list[str] = field(default_factory=list)
    failed: bool = False


@dataclass
class ApprovalRequest:
    """Payload surfaced to the UI when approval is required before provisioning."""

    session_id: str
    kind: str
    title: str
    detail: str
    tables: list[str] = field(default_factory=list)


def _activity_event(session_id: str, phase: str, agent: str, status: str, detail: str = "") -> WorkflowEvent:
    return WorkflowEvent(
        "agent_activity",
        data={
            "session_id": session_id,
            "phase": phase,
            "agent": agent,
            "status": status,
            "detail": detail,
        },
    )


def _phase_event(session_id: str, phase: str, status: str, summary: str = "") -> WorkflowEvent:
    return WorkflowEvent(
        "phase_status",
        data={"session_id": session_id, "phase": phase, "status": status, "summary": summary},
    )


class _PhaseExecutor(Executor):
    """Base for a pipeline phase that delegates to an existing specialist."""

    phase: str = ""

    async def _run_specialist(self, session_id: str) -> dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError

    async def _emit_trace(self, ctx: WorkflowContext, session_id: str) -> None:
        """Optional hook to emit extra activity/trace events for this phase."""

    async def _handle(self, state: PipelineState, ctx: WorkflowContext[PipelineState, dict]) -> None:
        sid = state.session_id
        await ctx.add_event(_phase_event(sid, self.phase, "running"))
        await ctx.add_event(_activity_event(sid, self.phase, self.id, "running"))
        try:
            result = await self._run_specialist(sid)
        except Exception as e:  # noqa: BLE001
            logger.error("Phase %s failed: %s", self.phase, e, exc_info=True)
            state.failed = True
            await ctx.add_event(_phase_event(sid, self.phase, "failed", str(e)))
            await ctx.yield_output({"phase": self.phase, "status": "failed", "message": str(e)})
            return

        is_failure = result.get("type") == "error" or (
            result.get("complete") is False and result.get("type", "").endswith("failed")
        )
        if is_failure:
            state.failed = True
            msg = result.get("response", "Phase failed.")
            await ctx.add_event(_phase_event(sid, self.phase, "failed", msg))
            await ctx.yield_output({"phase": self.phase, "status": "failed", "message": msg})
            return

        summary = result.get("response", "")
        state.notes.append(summary)
        await self._emit_trace(ctx, sid)
        await ctx.add_event(_phase_event(sid, self.phase, "done", summary))
        await ctx.yield_output({"phase": self.phase, "status": "done", "message": summary})
        await ctx.send_message(state)


class ResearchExecutor(_PhaseExecutor):
    phase = "research"

    def __init__(self) -> None:
        super().__init__(id="research")

    async def _run_specialist(self, session_id: str) -> dict[str, Any]:
        return await ResearchSpecialist().analyze(session_id)

    async def _emit_trace(self, ctx: WorkflowContext, session_id: str) -> None:
        research = session_store.get_value(session_id, "research_output") or {}
        await ctx.add_event(
            WorkflowEvent(
                "research_trace",
                data={
                    "session_id": session_id,
                    "industry": research.get("industry"),
                    "domain": research.get("domain"),
                    "recommended_object_types": research.get("recommended_object_types", []),
                    "industry_patterns": research.get("industry_patterns", []),
                    "best_practices": research.get("best_practices", []),
                    "sources": research.get("sources", []),
                },
            )
        )

    @handler
    async def run_phase(self, messages: list[Message], ctx: WorkflowContext[PipelineState, dict]) -> None:
        # Start executor: the session id is resolved from the workflow binding.
        state = PipelineState(session_id=self._session_id)  # type: ignore[attr-defined]
        await self._handle(state, ctx)


class DesignExecutor(_PhaseExecutor):
    phase = "design"

    def __init__(self) -> None:
        super().__init__(id="design")

    async def _run_specialist(self, session_id: str) -> dict[str, Any]:
        return await OntologyDesignerSpecialist().analyze(session_id)

    @handler
    async def run_phase(self, state: PipelineState, ctx: WorkflowContext[PipelineState, dict]) -> None:
        if state.failed:
            return
        await self._handle(state, ctx)


class ActionsRulesExecutor(_PhaseExecutor):
    phase = "actions_rules"

    def __init__(self) -> None:
        super().__init__(id="actions_rules")

    async def _run_specialist(self, session_id: str) -> dict[str, Any]:
        return await ActionsRulesSpecialist().analyze(session_id)

    @handler
    async def run_phase(self, state: PipelineState, ctx: WorkflowContext[PipelineState, dict]) -> None:
        if state.failed:
            return
        await self._handle(state, ctx)


class ValidationExecutor(_PhaseExecutor):
    phase = "validation"

    def __init__(self) -> None:
        super().__init__(id="validation")

    async def _run_specialist(self, session_id: str) -> dict[str, Any]:
        return await ValidatorSpecialist().analyze(session_id)

    async def _emit_trace(self, ctx: WorkflowContext, session_id: str) -> None:
        report = session_store.get_value(session_id, "validation_report") or {}
        await ctx.add_event(
            WorkflowEvent(
                "validation_report",
                data={
                    "session_id": session_id,
                    "overall_score": report.get("overall_score"),
                    "passed": report.get("passed"),
                    "issues": report.get("issues", []),
                    "strengths": report.get("strengths", []),
                },
            )
        )

    @handler
    async def run_phase(self, state: PipelineState, ctx: WorkflowContext[PipelineState, dict]) -> None:
        if state.failed:
            return
        await self._handle(state, ctx)


class GenerationExecutor(Executor):
    """Writes YAML (safe), then requests approval before provisioning the DB."""

    def __init__(self, datastore: Any) -> None:
        super().__init__(id="generating")
        self._datastore = datastore

    @handler
    async def start(self, state: PipelineState, ctx: WorkflowContext[dict, dict]) -> None:
        if state.failed:
            return
        sid = state.session_id
        await ctx.add_event(_phase_event(sid, "generating", "running"))

        # Safe step: write YAML files.
        await ctx.add_event(_activity_event(sid, "generating", "yaml_writer", "running", "Writing ontology YAML files"))
        try:
            files = generation.write_ontology_yaml(sid)
        except Exception as e:  # noqa: BLE001
            logger.error("YAML generation failed: %s", e, exc_info=True)
            await ctx.add_event(_phase_event(sid, "generating", "failed", str(e)))
            await ctx.yield_output({"phase": "generating", "status": "failed", "message": str(e)})
            return
        await ctx.add_event(
            _activity_event(sid, "generating", "yaml_writer", "done", f"{len(files)} files written")
        )

        # Irreversible step: request human approval before provisioning + seeding.
        ontology = session_store.get_value(sid, "ontology_design") or {}
        table_count = len(ontology.get("object_types", []))
        await ctx.request_info(
            ApprovalRequest(
                session_id=sid,
                kind="provision_database",
                title="Provision database & seed synthetic data",
                detail=(
                    f"This will create ~{table_count} tables from the ontology and seed them "
                    "with generated synthetic data. This step writes to the database and cannot "
                    "be undone automatically."
                ),
                tables=[ot.get("api_name", "") for ot in ontology.get("object_types", [])],
            ),
            response_type=bool,
        )

    @response_handler
    async def on_approval(
        self, request: ApprovalRequest, approved: bool, ctx: WorkflowContext[dict, dict]
    ) -> None:
        sid = request.session_id
        if not approved:
            session_store.update(sid, "phase", "qa")
            await ctx.add_event(_phase_event(sid, "generating", "skipped", "Database provisioning declined."))
            await ctx.yield_output(
                {
                    "phase": "generating",
                    "status": "skipped",
                    "message": (
                        "Ontology YAML files were generated, but database provisioning was declined. "
                        "You can review the ontology files; the Data Explorer and Q&A will be empty "
                        "until the database is provisioned."
                    ),
                    "ontology_ready": True,
                }
            )
            return

        await ctx.add_event(_activity_event(sid, "generating", "datastore", "running", "Creating tables & seeding data"))
        try:
            result = await generation.provision_and_seed_database(sid, self._datastore)
        except Exception as e:  # noqa: BLE001
            logger.error("Provisioning failed: %s", e, exc_info=True)
            await ctx.add_event(_phase_event(sid, "generating", "failed", str(e)))
            await ctx.yield_output({"phase": "generating", "status": "failed", "message": str(e)})
            return

        session_store.update(sid, "phase", "qa")
        ontology = session_store.get_value(sid, "ontology_design") or {}
        intake = session_store.get_value(sid, "intake_output")
        files = session_store.get_value(sid, "generated_files") or {}
        suggestions = generation.generate_business_questions(ontology, intake)
        total_rows = sum(result["seed_counts"].values())

        await ctx.add_event(
            _activity_event(
                sid,
                "generating",
                "datastore",
                "done",
                f"{len(result['tables_created'])} tables, {total_rows} rows",
            )
        )
        await ctx.add_event(_phase_event(sid, "generating", "done", "Ontology generated and database provisioned."))
        await ctx.yield_output(
            {
                "phase": "generating",
                "status": "done",
                "ontology_ready": True,
                "message": (
                    f"Ontology generation complete! {len(files)} files written, "
                    f"{len(result['tables_created'])} tables created with {total_rows} rows of "
                    "synthetic data. You can now test the ontology with natural-language questions."
                ),
                "files": list(files.keys()),
                "tables_created": result["tables_created"],
                "seed_counts": result["seed_counts"],
                "follow_up_questions": suggestions,
            }
        )


def build_pipeline_workflow(session_id: str, datastore: Any) -> Workflow:
    """Build the pipeline workflow bound to a session id and datastore."""
    research = ResearchExecutor()
    # Bind the session id onto the start executor (input is list[Message] from AG-UI).
    research._session_id = session_id  # type: ignore[attr-defined]

    design = DesignExecutor()
    actions_rules = ActionsRulesExecutor()
    validation = ValidationExecutor()
    generating = GenerationExecutor(datastore)

    return (
        WorkflowBuilder(
            name="ontology_pipeline",
            description="Research → design → actions/rules → validation → generation pipeline.",
            start_executor=research,
            output_from="all",
        )
        .add_chain([research, design, actions_rules, validation, generating])
        .build()
    )
