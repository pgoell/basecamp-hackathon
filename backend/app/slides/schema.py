"""Checks a presentation doc against schema.json and says what to fix in plain words.

Ported from blattwerk's schema.py.
"""

import json
from pathlib import Path

from jsonschema import Draft7Validator

SCHEMA = json.loads((Path(__file__).parent / "schema.json").read_text())
VALIDATOR = Draft7Validator(SCHEMA)
WORDS = {
    "string": "a string",
    "number": "a number",
    "integer": "a whole number",
    "boolean": "a yes or no",
    "array": "a list",
    "object": "an object",
    "null": "nothing",
}


def kind(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return {str: "string", list: "array", dict: "object"}[type(value)]


def where(path: list) -> str:
    text = ""
    for key in path:
        text += f"[{key}]" if isinstance(key, int) else f".{key}" if text else key
    return text or "doc"


def verdict(error) -> str:
    schema, got = error.schema, error.instance
    if error.validator in ("minimum", "maximum", "exclusiveMinimum"):
        if error.validator == "exclusiveMinimum":
            return f"must be more than {schema['exclusiveMinimum']}, got {got}"
        if "minimum" in schema and "maximum" in schema:
            return f"must be {schema['minimum']} to {schema['maximum']}, got {got}"
        if "minimum" in schema:
            return f"must be at least {schema['minimum']}, got {got}"
        return f"must be at most {schema['maximum']}, got {got}"
    if error.validator == "enum":
        options = ", ".join(f"'{option}'" for option in schema["enum"])
        return f"must be one of {options}, got '{got}'"
    if error.validator == "const":
        return f"must be '{schema['const']}', got '{got}'"
    if error.validator == "pattern":
        if schema["pattern"].startswith("^#"):
            return f"must be a hex colour such as '#1f2937', got '{got}'"
        return f"must start with /api/slides/uploads/ or https://, got '{got}'"
    if error.validator == "type":
        wanted = [error.validator_value] if isinstance(error.validator_value, str) else error.validator_value
        return f"must be {' or '.join(WORDS[w] for w in wanted)}, got {WORDS[kind(got)]}"
    return error.message


def items(error) -> list[tuple[list, str]]:
    """The path and the fix for each problem one error stands for."""
    path = list(error.absolute_path)
    if error.validator == "required":
        return [
            ([*path, name], "missing, add it") for name in error.validator_value if name not in error.instance
        ]
    if error.validator == "additionalProperties":
        known = error.schema.get("properties", {})
        return [([*path, name], "unknown field, remove it") for name in error.instance if name not in known]
    return [(path, verdict(error))]


def problems(doc) -> list[str]:
    """Every fault in the doc, the first ten by path. Empty when the doc is right."""
    try:
        json.dumps(doc, allow_nan=False)
    except ValueError:
        return ["doc: holds NaN or Infinity, write a finite number"]
    found = {}
    for error in VALIDATOR.iter_errors(doc):
        for path, text in items(error):
            key = tuple((0, k) if isinstance(k, int) else (1, k) for k in path)
            found.setdefault(f"{where(path)}: {text}", key)
    return sorted(found, key=found.get)[:10]
