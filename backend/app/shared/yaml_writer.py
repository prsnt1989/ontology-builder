from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ..config import settings
from .schemas import OntologyMeta


def _represent_none(dumper: yaml.Dumper, _data: Any) -> Any:
    return dumper.represent_scalar("tag:yaml.org,2002:null", "null")


yaml.add_representer(type(None), _represent_none)


def write_yaml_file(session_id: str, filename: str, data: dict) -> str:
    output_dir = Path(settings.output_dir) / session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    with open(filepath, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return str(filepath)


def write_ontology_files(
    session_id: str,
    meta: OntologyMeta,
    object_types: list[dict],
    relationships: list[dict],
    actions: list[dict],
    permissions: list[dict],
    validation_rules: list[dict],
    lifecycles: list[dict],
) -> dict[str, str]:
    meta_dict = meta.model_dump()
    files = {}

    properties_by_type = {}
    for ot in object_types:
        props = ot.pop("properties", [])
        properties_by_type[ot["api_name"]] = props

    files["object_types.yaml"] = write_yaml_file(session_id, "object_types.yaml", {
        "ontology_meta": meta_dict,
        "object_types": object_types,
    })

    files["properties.yaml"] = write_yaml_file(session_id, "properties.yaml", {
        "ontology_meta": meta_dict,
        "properties": properties_by_type,
    })

    files["relationships.yaml"] = write_yaml_file(session_id, "relationships.yaml", {
        "ontology_meta": meta_dict,
        "relationships": relationships,
    })

    files["actions.yaml"] = write_yaml_file(session_id, "actions.yaml", {
        "ontology_meta": meta_dict,
        "actions": actions,
    })

    files["permissions.yaml"] = write_yaml_file(session_id, "permissions.yaml", {
        "ontology_meta": meta_dict,
        "permissions": permissions,
    })

    files["validation_rules.yaml"] = write_yaml_file(session_id, "validation_rules.yaml", {
        "ontology_meta": meta_dict,
        "validation_rules": validation_rules,
    })

    files["lifecycle_states.yaml"] = write_yaml_file(session_id, "lifecycle_states.yaml", {
        "ontology_meta": meta_dict,
        "lifecycles": lifecycles,
    })

    # Generate data_mapping.yaml (summary of all table/column mappings)
    table_mappings = []
    for ot in object_types:
        if ot.get("backing_table"):
            mapping = {
                "object_type": ot["api_name"],
                "table": ot["backing_table"],
                "columns": [
                    p.get("backing_column")
                    for p in properties_by_type.get(ot["api_name"], [])
                    if p.get("backing_column")
                ],
            }
            table_mappings.append(mapping)

    files["data_mapping.yaml"] = write_yaml_file(session_id, "data_mapping.yaml", {
        "ontology_meta": meta_dict,
        "table_mappings": table_mappings,
    })

    return files
