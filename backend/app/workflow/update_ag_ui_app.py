"""AG-UI wrapper for the update pipeline workflow (mounted at /api/pipeline/update)."""
from __future__ import annotations

import logging
from typing import Any, Callable

from agent_framework.ag_ui import AgentFrameworkWorkflow

from .update_pipeline import build_update_pipeline_workflow

logger = logging.getLogger(__name__)


class UpdatePipelineAGUIWorkflow(AgentFrameworkWorkflow):
    """Per-thread update pipeline. ``thread_id`` is treated as the session id."""

    def __init__(self, datastore_getter: Callable[[], Any]) -> None:
        self._datastore_getter = datastore_getter
        super().__init__(
            workflow_factory=self._make_workflow,
            name="ontology_update_pipeline",
            description="Apply confirmed ontology changes (design patch → generation) with HITL approval.",
        )

    def _make_workflow(self, thread_id: str):
        return build_update_pipeline_workflow(
            session_id=thread_id, datastore=self._datastore_getter()
        )
