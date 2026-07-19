from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ActionParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    required: bool = True
    description: str


class ActionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_name: str
    display_name: str
    description: str
    object_type: str
    parameters: List[ActionParameter] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)
    result_type: Optional[str] = None


class PermissionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    object_type: str
    allowed_actions: List[str] = Field(default_factory=list)
    property_restrictions: List[str] = Field(default_factory=list)
    row_filter: Optional[str] = None


class ValidationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    object_type: str
    description: str
    rule_type: str
    expression: str
    error_message: str
    severity: str = "error"


class LifecycleState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    display_name: str
    description: str
    is_initial: bool = False
    is_terminal: bool = False
    allowed_transitions: List[str] = Field(default_factory=list)


class LifecycleTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_state: str
    to_state: str
    trigger: str
    guard_conditions: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)


class LifecycleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_type: str
    states: List[LifecycleState] = Field(default_factory=list)
    transitions: List[LifecycleTransition] = Field(default_factory=list)


class ActionsRulesOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actions: List[ActionDefinition] = Field(default_factory=list)
    permissions: List[PermissionRule] = Field(default_factory=list)
    validation_rules: List[ValidationRule] = Field(default_factory=list)
    lifecycles: List[LifecycleDefinition] = Field(default_factory=list)
