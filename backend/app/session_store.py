from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self, persist_dir: str = "deployment/data/sessions") -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._load_all()

    def _load_all(self) -> None:
        """Load all persisted sessions from disk on startup."""
        for path in self._persist_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                session_id = path.stem
                self._sessions[session_id] = data
                logger.info("Loaded session %s (phase=%s)", session_id, data.get("phase"))
            except Exception as e:
                logger.warning("Failed to load session %s: %s", path.name, e)

    def _persist(self, session_id: str) -> None:
        """Write session to disk."""
        session = self._sessions.get(session_id)
        if not session:
            return
        path = self._persist_dir / f"{session_id}.json"
        try:
            path.write_text(json.dumps(session, default=str))
        except Exception as e:
            logger.error("Failed to persist session %s: %s", session_id, e)

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "phase": "intake",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "intake_state": {
                "current_block": 1,
                "blocks_completed": [],
                "intent": {},
                "awaiting_input": False,
            },
            "intake_output": None,
            "research_output": None,
            "ontology_design": None,
            "actions_rules": None,
            "validation_report": None,
            "generated_files": {},
            "messages": [],
            "ontology_meta": None,
        }
        self._persist(session_id)
        return session_id

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: Optional[str] = None) -> tuple[str, dict[str, Any]]:
        if session_id and session_id in self._sessions:
            return session_id, self._sessions[session_id]
        new_id = self.create_session()
        return new_id, self._sessions[new_id]

    def update(self, session_id: str, key: str, value: Any) -> None:
        if session_id in self._sessions:
            self._sessions[session_id][key] = value
            self._persist(session_id)

    def get_value(self, session_id: str, key: str) -> Any:
        session = self._sessions.get(session_id)
        if session:
            return session.get(key)
        return None

    def add_message(self, session_id: str, role: str, content: str) -> None:
        if session_id in self._sessions:
            messages = self._sessions[session_id]["messages"]
            messages.append({"role": role, "content": content})
            if len(messages) > 50:
                self._sessions[session_id]["messages"] = messages[-50:]
            self._persist(session_id)

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            path = self._persist_dir / f"{session_id}.json"
            if path.exists():
                path.unlink()
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        results = []
        for sid, s in self._sessions.items():
            company = None
            if s.get("intake_output"):
                company = s["intake_output"].get("company_profile", {}).get("company_name")
            if not company:
                intake_state = s.get("intake_state") or {}
                company = intake_state.get("intent", {}).get("company_name")
            results.append({
                "session_id": sid,
                "phase": s["phase"],
                "created_at": s.get("created_at"),
                "company": company,
                "ontology_ready": bool(s.get("generated_files")),
            })
        return sorted(results, key=lambda x: x.get("created_at") or "", reverse=True)


session_store = SessionStore()
