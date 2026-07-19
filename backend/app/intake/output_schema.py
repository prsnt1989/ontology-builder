from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CompanyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str = ""
    industry: str = ""
    sub_industry: Optional[str] = None
    company_size: str = ""
    tech_stack: List[str] = Field(default_factory=list)
    palantir_experience: str = ""


class BusinessDomain(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department: str = ""
    key_processes: List[str] = Field(default_factory=list)
    key_entities: List[str] = Field(default_factory=list)
    domain_specific_terms: List[str] = Field(default_factory=list)


class ProblemStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary_goal: str = ""
    pain_points: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    current_solution: Optional[str] = None


class DataSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = ""
    type: str = ""
    volume: str = ""
    freshness: str = ""
    quality_issues: List[str] = Field(default_factory=list)


class UserRole(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_name: str
    description: str = ""
    permissions_needed: List[str] = Field(default_factory=list)
    hierarchy_level: int = 0


class WorkflowInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    complexity: str = ""
    approval_processes: str = ""
    notification_triggers: List[str] = Field(default_factory=list)
    automation_level: str = ""


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    compliance_requirements: List[str] = Field(default_factory=list)
    integration_needs: List[str] = Field(default_factory=list)
    scalability: str = ""
    sensitive_data: str = ""


class IntakeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_profile: CompanyProfile = Field(default_factory=CompanyProfile)
    business_domain: BusinessDomain = Field(default_factory=BusinessDomain)
    problem_statement: ProblemStatement = Field(default_factory=ProblemStatement)
    data_sources: List[DataSource] = Field(default_factory=list)
    user_roles: List[UserRole] = Field(default_factory=list)
    workflows: WorkflowInfo = Field(default_factory=WorkflowInfo)
    constraints: Constraints = Field(default_factory=Constraints)
