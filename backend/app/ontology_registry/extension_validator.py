from __future__ import annotations

from typing import Any


class ExtensionValidationError(Exception):
    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__(f"Extension validation failed: {'; '.join(violations)}")


def validate_extension(base: dict[str, Any], extension: dict[str, Any]) -> list[str]:
    """Validate that an extension does not modify or remove base ontology objects.

    Rules:
    - Cannot remove object types that exist in base
    - Cannot remove properties from existing object types
    - Cannot change property types on existing properties
    - Cannot remove relationships from base
    - Cannot change cardinality on existing relationships
    - Can ADD new object types, properties, relationships, actions, etc.
    """
    violations = []

    base_types = {ot["api_name"]: ot for ot in base.get("object_types", [])}
    ext_types = {ot["api_name"]: ot for ot in extension.get("object_types", [])}

    for type_name in base_types:
        if type_name not in ext_types:
            violations.append(
                f"Object type '{type_name}' exists in base but missing in extension. "
                f"Extensions cannot remove base types."
            )
            continue

        base_props = {p["api_name"]: p for p in base_types[type_name].get("properties", [])}
        ext_props = {p["api_name"]: p for p in ext_types[type_name].get("properties", [])}

        for prop_name, base_prop in base_props.items():
            if prop_name not in ext_props:
                violations.append(
                    f"Property '{type_name}.{prop_name}' removed in extension. "
                    f"Extensions cannot remove base properties."
                )
            elif ext_props[prop_name].get("type") != base_prop.get("type"):
                violations.append(
                    f"Property '{type_name}.{prop_name}' type changed from "
                    f"'{base_prop.get('type')}' to '{ext_props[prop_name].get('type')}'. "
                    f"Extensions cannot change base property types."
                )

    base_rels = {r["api_name"]: r for r in base.get("relationships", [])}
    ext_rels = {r["api_name"]: r for r in extension.get("relationships", [])}

    for rel_name in base_rels:
        if rel_name not in ext_rels:
            violations.append(
                f"Relationship '{rel_name}' removed in extension. "
                f"Extensions cannot remove base relationships."
            )
        elif ext_rels[rel_name].get("cardinality") != base_rels[rel_name].get("cardinality"):
            violations.append(
                f"Relationship '{rel_name}' cardinality changed. "
                f"Extensions cannot change base relationship cardinality."
            )

    return violations


def validate_or_raise(base: dict[str, Any], extension: dict[str, Any]) -> None:
    """Validate extension and raise if violations found."""
    violations = validate_extension(base, extension)
    if violations:
        raise ExtensionValidationError(violations)
