"""Agent Skills for the ontology pipeline (progressive-disclosure, agentskills.io).

Skills live as ``SKILL.md`` packages under ``backend/skills/``. This module:

- builds a :class:`SkillsProvider` that can be attached to MAF agents so the model
  can ``load_skill`` / ``read_skill_resource`` on demand (progressive disclosure);
- exposes :func:`list_advertised_skills` — the L1 metadata (name, description,
  phase) for the UI skills panel, read directly from the frontmatter.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from agent_framework import SkillsProvider

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def build_skills_provider() -> SkillsProvider | None:
    """Build a SkillsProvider from the on-disk skill packages, or None if absent."""
    if not _SKILLS_DIR.exists():
        return None
    try:
        return SkillsProvider.from_paths(str(_SKILLS_DIR))
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to build skills provider: %s", e)
        return None


def _parse_frontmatter(md_path: Path) -> dict[str, Any] | None:
    text = md_path.read_text()
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None


def list_advertised_skills() -> list[dict[str, Any]]:
    """Return L1 skill metadata for the UI: name, description, phase."""
    skills: list[dict[str, Any]] = []
    if not _SKILLS_DIR.exists():
        return skills
    for skill_md in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        fm = _parse_frontmatter(skill_md)
        if not fm or "name" not in fm:
            continue
        metadata = fm.get("metadata") or {}
        skills.append(
            {
                "name": fm["name"],
                "description": fm.get("description", ""),
                "phase": metadata.get("phase"),
            }
        )
    return skills
