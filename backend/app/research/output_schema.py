from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = ""
    title: str = ""
    relevance: str = ""
    key_findings: List[str] = Field(default_factory=list)


class IndustryPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pattern_name: str
    description: str
    common_object_types: List[str] = Field(default_factory=list)
    common_relationships: List[str] = Field(default_factory=list)
    source: str = ""


class DomainResearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    industry: str = ""
    domain: str = ""
    sources_consulted: List[ResearchSource] = Field(default_factory=list)
    industry_patterns: List[IndustryPattern] = Field(default_factory=list)
    recommended_object_types: List[str] = Field(default_factory=list)
    recommended_relationships: List[str] = Field(default_factory=list)
    best_practices: List[str] = Field(default_factory=list)
    domain_vocabulary: dict = Field(default_factory=dict)
