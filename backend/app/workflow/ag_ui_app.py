"""AG-UI wrapper for the pipeline workflow.

Bridges the AG-UI ``thread_id`` to the app's ``session_id`` and builds a
session-bound pipeline workflow per thread. Registered on the FastAPI app via
``add_agent_framework_fastapi_endpoint`` at ``/api/pipeline``.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from agent_framework.ag_ui import AgentFrameworkWorkflow

from .pipeline import build_pipeline_workflow

logger = logging.getLogger(__name__)


class PipelineAGUIWorkflow(AgentFrameworkWorkflow):
    """Per-thread pipeline workflow. ``thread_id`` is treated as the session id.

    The datastore is resolved lazily via ``datastore_getter`` so the endpoint can
    be registered at import time while the datastore is created later in lifespan.
    """

    def __init__(self, datastore_getter: Callable[[], Any]) -> None:
        self._datastore_getter = datastore_getter
        super().__init__(
            workflow_factory=self._make_workflow,
            name="ontology_pipeline",
            description="Ontology build pipeline (research → generation) with HITL approval.",
        )

    def _make_workflow(self, thread_id: str):
        # AG-UI thread_id == our session_id. The frontend passes the session id
        # as thread_id when starting the pipeline.
        return build_pipeline_workflow(
            session_id=thread_id, datastore=self._datastore_getter()
        )
