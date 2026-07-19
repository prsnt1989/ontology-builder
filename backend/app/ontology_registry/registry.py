from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any, Optional

from ..config import settings


class OntologyRegistry:
    """Manages versioned ontology storage and retrieval."""

    def __init__(self) -> None:
        self._base_dir = Path(settings.output_dir)

    def list_ontologies(self) -> list[dict[str, Any]]:
        """List all stored ontology versions."""
        results = []
        if not self._base_dir.exists():
            return results

        for session_dir in self._base_dir.iterdir():
            if not session_dir.is_dir():
                continue
            meta_file = session_dir / "object_types.yaml"
            if meta_file.exists():
                with open(meta_file) as f:
                    data = yaml.safe_load(f)
                meta = data.get("ontology_meta", {})
                results.append({
                    "session_id": session_dir.name,
                    "id": meta.get("id", ""),
                    "version": meta.get("version", ""),
                    "extends": meta.get("extends"),
                    "use_case": meta.get("use_case"),
                    "company": meta.get("company", ""),
                    "created_at": meta.get("created_at", ""),
                })
        return results

    def get_ontology(self, session_id: str) -> Optional[dict[str, Any]]:
        """Load a full ontology from YAML files."""
        session_dir = self._base_dir / session_id
        if not session_dir.exists():
            return None

        result = {}
        for yaml_file in session_dir.glob("*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            result[yaml_file.stem] = data
        return result

    def get_base_ontology(self, company_id: str) -> Optional[dict[str, Any]]:
        """Find the base (non-extension) ontology for a company."""
        for entry in self.list_ontologies():
            if entry.get("id", "").startswith(f"ont_{company_id}") and not entry.get("extends"):
                return self.get_ontology(entry["session_id"])
        return None

    def get_versions(self, company_id: str) -> list[dict[str, Any]]:
        """Get all versions (base + extensions) for a company."""
        return [
            entry for entry in self.list_ontologies()
            if entry.get("id", "").startswith(f"ont_{company_id}")
        ]


registry = OntologyRegistry()
