from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PropertyType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    ENUM = "enum"
    ARRAY = "array"
    OBJECT = "object"
    GEOSPATIAL = "geospatial"
    ATTACHMENT = "attachment"


class Cardinality(str, Enum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class BackingColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column_name: str
    sql_type: str
    nullable: bool = True
    indexed: bool = False
    check_constraint: Optional[str] = None


class BackingTable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_name: str
    schema_name: str = "public"
    primary_key_column: str = "id"


class BackingForeignKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    on_delete: str = "RESTRICT"


class PropertyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    display_name: str
    description: str
    type: PropertyType
    required: bool = False
    unique: bool = False
    indexed: bool = False
    default_value: Optional[str] = None
    enum_values: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    backing_column: Optional[BackingColumn] = None


class ObjectTypeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_name: str
    display_name: str
    plural_display_name: str
    description: str
    primary_key: str
    icon: Optional[str] = None
    title_property: str
    backing_table: Optional[BackingTable] = None
    properties: List[PropertyDefinition] = Field(default_factory=list)


class RelationshipDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_name: str
    display_name: str
    description: str
    from_object_type: str
    to_object_type: str
    cardinality: Cardinality
    inverse_name: Optional[str] = None
    is_required: bool = False
    backing_foreign_key: Optional[BackingForeignKey] = None


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
    rule_type: str  # "field_level", "cross_field", "business_rule"
    expression: str
    error_message: str
    severity: str = "error"  # "error" | "warning"


class LifecycleTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_state: str
    to_state: str
    trigger: str
    guard_conditions: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)


class LifecycleState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    display_name: str
    description: str
    is_initial: bool = False
    is_terminal: bool = False
    allowed_transitions: List[str] = Field(default_factory=list)


class LifecycleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_type: str
    states: List[LifecycleState] = Field(default_factory=list)
    transitions: List[LifecycleTransition] = Field(default_factory=list)


class OntologyMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    version: str
    extends: Optional[str] = None
    use_case: Optional[str] = None
    company: str
    created_at: str
    base_version: str
