import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

OPENAPI_PATH = ROOT / "docs" / "openapi.json"
TS_PATH = ROOT / "frontend" / "src" / "api" / "generated.ts"


IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def ts_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_$]", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def ts_property(name: str) -> str:
    if IDENTIFIER_RE.match(name):
        return name
    return json.dumps(name)


def ref_name(ref: str) -> str:
    return ts_name(ref.rsplit("/", 1)[-1])


def ts_type(schema: dict[str, Any] | None) -> str:
    if not schema:
        return "unknown"

    if "$ref" in schema:
        return ref_name(str(schema["$ref"]))

    if "allOf" in schema:
        parts = [ts_type(item) for item in schema["allOf"]]
        return " & ".join(parts) if parts else "unknown"

    union_items = schema.get("anyOf") or schema.get("oneOf")
    if union_items:
        parts = []
        for item in union_items:
            if item.get("type") == "null":
                parts.append("null")
            else:
                parts.append(ts_type(item))
        return " | ".join(dict.fromkeys(parts)) if parts else "unknown"

    if schema.get("nullable"):
        copy = dict(schema)
        copy.pop("nullable", None)
        return f"{ts_type(copy)} | null"

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        return " | ".join(
            "null" if item == "null" else ts_type({**schema, "type": item})
            for item in schema_type
        )

    if schema_type == "array":
        return f"Array<{ts_type(schema.get('items'))}>"

    if schema_type == "integer" or schema_type == "number":
        return "number"

    if schema_type == "boolean":
        return "boolean"

    if schema_type == "string":
        enum = schema.get("enum")
        if enum:
            return " | ".join(json.dumps(value) for value in enum)
        return "string"

    if schema_type == "object" or "properties" in schema:
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        additional = schema.get("additionalProperties", False)

        if not properties:
            if isinstance(additional, dict):
                return f"Record<string, {ts_type(additional)}>"
            return "Record<string, unknown>"

        lines = ["{"]
        for name, prop_schema in sorted(properties.items()):
            optional = "" if name in required else "?"
            property_type = ts_type(prop_schema)
            if name not in required and "null" not in property_type:
                property_type = f"{property_type} | null"
            lines.append(f"  {ts_property(name)}{optional}: {property_type};")
        lines.append("}")
        object_type = "\n".join(lines)

        if isinstance(additional, dict):
            object_type = f"{object_type} & Record<string, {ts_type(additional)}>"
        elif additional is True:
            object_type = f"{object_type} & Record<string, unknown>"

        return object_type

    return "unknown"


def generate_types(openapi: dict[str, Any]) -> str:
    schemas = openapi.get("components", {}).get("schemas", {})
    lines = [
        "// Generated from docs/openapi.json by scripts/generate_api_contracts.py.",
        "// Do not edit manually.",
        "",
    ]

    for name, schema in sorted(schemas.items()):
        lines.append(f"export type {ts_name(name)} = {ts_type(schema)};")
        lines.append("")

    if schemas:
        lines.append("export type ApiSchemas = {")
        for name in sorted(schemas):
            lines.append(f"  {ts_property(name)}: {ts_name(name)};")
        lines.append("};")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    openapi = app.openapi()
    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(
        json.dumps(openapi, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    TS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TS_PATH.write_text(generate_types(openapi), encoding="utf-8")


if __name__ == "__main__":
    main()
