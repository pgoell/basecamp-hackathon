"""The agent's tools: PowerPoint-like edits to one presentation.

Same contract as blattwerk's MCP handlers (frontend/mcp/handlers.ts), in Python: read the doc,
change a copy, check it against the schema, write it back with the version it was read at.
"""

import copy
import json

from fastapi import HTTPException
from jsonschema import Draft202012Validator

from app.slides import db, ops
from app.slides.presentations import find, write
from app.slides.schema import SCHEMA, problems


class ToolError(Exception):
    pass


def _defs() -> dict:
    """schema.json's definitions as $defs, for self-contained tool schemas."""
    text = json.dumps(SCHEMA["definitions"]).replace("#/definitions/", "#/$defs/")
    return json.loads(text)


DEFS = _defs()
DOC = {k: v for k, v in SCHEMA.items() if k not in ("$schema", "definitions", "title")}


def _new_element() -> dict:
    """An element as add_element takes it: any element type, without the id."""
    variants = []
    for name in ("Text", "Shape", "Image", "Table"):
        variant = copy.deepcopy(DEFS[name])
        del variant["properties"]["id"]
        variant["required"].remove("id")
        variants.append(variant)
    return {"anyOf": variants, "description": "The element, without an id."}


SLIDE_ID = {"type": "string", "description": "The slide's id, from get_presentation."}
ELEMENT_ID = {"type": "string", "description": "The element's id, from get_presentation."}
WORDS = {
    "title": {"type": "string", "description": "Text for the title box. Left out, it stays empty."},
    "body": {
        "type": "string",
        "description": "Text for the (first) body box, one paragraph or bullet per line.",
    },
}
LAYOUT = {
    "enum": ops.LAYOUTS,
    "description": "title: big centred title + subtitle. title_content: title + bulleted body. "
    "two_columns: title + two bulleted bodies. section: section header. blank: nothing.",
}
DOC_NOTE = (
    "Slides are 960 x 540 pt (16:9); every x, y, w, h and font size is in pt, x and y from the "
    "slide's top left. Elements draw in order: the last lies on top."
)


def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    schema = {"type": "object", "properties": properties, "required": required, "additionalProperties": False}
    if "#/$defs/" in json.dumps(properties):
        schema["$defs"] = DEFS
    return {"name": name, "description": description, "eager_input_streaming": True, "input_schema": schema}


TOOLS = [
    tool(
        "get_presentation",
        "Read the whole presentation: title, version, and the doc with every slide and element. "
        "Call it before you change anything, and again when a change fails. " + DOC_NOTE,
        {},
        [],
    ),
    tool(
        "rename_presentation",
        "Change the presentation's title.",
        {"title": {"type": "string", "minLength": 1, "maxLength": 120}},
        ["title"],
    ),
    tool(
        "add_slide",
        "Add a slide with a layout's title and body boxes, filled with `title` and `body` if given. "
        "Restyle or refill them later with update_element.",
        {
            "layout": LAYOUT,
            "position": {
                "type": "integer",
                "minimum": 0,
                "description": "Index the new slide gets, 0 for first. Left out, it goes last.",
            },
            **WORDS,
        },
        ["layout"],
    ),
    tool("delete_slide", "Delete a slide.", {"slide_id": SLIDE_ID}, ["slide_id"]),
    tool(
        "duplicate_slide",
        "Copy a slide; the copy goes right after it.",
        {"slide_id": SLIDE_ID},
        ["slide_id"],
    ),
    tool(
        "move_slide",
        "Move a slide to another place in the deck.",
        {
            "slide_id": SLIDE_ID,
            "to": {"type": "integer", "minimum": 0, "description": "The new index, 0 for first."},
        },
        ["slide_id", "to"],
    ),
    tool(
        "set_slide",
        "Set a slide's background colour or speaker notes. Pass null to remove one.",
        {
            "slide_id": SLIDE_ID,
            "background": {"anyOf": [DEFS["Slide"]["properties"]["background"], {"type": "null"}]},
            "notes": {"type": ["string", "null"]},
        },
        ["slide_id"],
    ),
    tool(
        "apply_layout",
        "Give a slide another layout: its title and body boxes are swapped for the layout's, "
        "keeping their text in order unless you pass title or body. Other elements stay.",
        {"slide_id": SLIDE_ID, "layout": LAYOUT, **WORDS},
        ["slide_id", "layout"],
    ),
    tool(
        "add_element",
        "Add an element on top of a slide: a text box, a shape (optionally with text), an image "
        "(src from an upload or an https URL), or a table. Text is paragraphs of runs; a run can "
        "be bold, italic, underlined or coloured, a paragraph can be a bullet or numbered item. " + DOC_NOTE,
        {"slide_id": SLIDE_ID, "element": _new_element()},
        ["slide_id", "element"],
    ),
    tool(
        "update_element",
        "Change some fields of an element: move or resize it (x, y, w, h), turn it (rotation), "
        "restyle it (size, color, font, fill, align, ...), or replace its text (paras, whole). "
        "Fields you leave out stay; a field set to null is removed. " + DOC_NOTE,
        {
            "slide_id": SLIDE_ID,
            "element_id": ELEMENT_ID,
            "changes": {"type": "object", "description": "The fields to set, by name."},
        },
        ["slide_id", "element_id", "changes"],
    ),
    tool(
        "delete_element",
        "Delete an element from a slide.",
        {"slide_id": SLIDE_ID, "element_id": ELEMENT_ID},
        ["slide_id", "element_id"],
    ),
    tool(
        "arrange_element",
        "Move an element in the drawing order: to the front, to the back, or one step.",
        {"slide_id": SLIDE_ID, "element_id": ELEMENT_ID, "to": {"enum": ops.ARRANGE}},
        ["slide_id", "element_id", "to"],
    ),
    tool(
        "replace_doc",
        "Replace the whole doc, for big rewrites. Keep the ids of slides and elements you keep; "
        "give new ones short unique ids. " + DOC_NOTE,
        {"doc": json.loads(json.dumps(DOC).replace("#/definitions/", "#/$defs/"))},
        ["doc"],
    ),
]


def _loose(schema: dict) -> dict:
    """The input schema the tool's input is checked against before it runs. An element or a doc
    is only checked to be an object here: the doc check after the change names its faults in
    plain words, where the schema's anyOf would only say it matches none."""
    props = {k: {"type": "object"} if k in ("element", "doc") else v for k, v in schema["properties"].items()}
    return {**schema, "properties": props}


VALIDATORS = {t["name"]: Draft202012Validator(_loose(t["input_schema"])) for t in TOOLS}


def change(name: str, doc: dict, args: dict):
    """Runs a write tool on `doc` in place. Returns what the agent is told it made."""
    if name == "add_slide":
        slide = ops.add_slide(
            doc, args["layout"], args.get("position"), args.get("title", ""), args.get("body", "")
        )
        return {"slide": slide}
    if name == "delete_slide":
        return ops.delete_slide(doc, args["slide_id"])
    if name == "duplicate_slide":
        return {"slide": ops.duplicate_slide(doc, args["slide_id"])}
    if name == "move_slide":
        return ops.move_slide(doc, args["slide_id"], args["to"])
    if name == "set_slide":
        _, slide = ops.find_slide(doc, args["slide_id"])
        for key in ("background", "notes"):
            if key in args:
                if args[key] is None:
                    slide.pop(key, None)
                else:
                    slide[key] = args[key]
        return None
    if name == "apply_layout":
        return {
            "slide": ops.apply_layout(
                doc, args["slide_id"], args["layout"], args.get("title"), args.get("body")
            )
        }
    if name == "add_element":
        return {"element": ops.add_element(doc, args["slide_id"], args["element"])}
    if name == "update_element":
        return {"element": ops.update_element(doc, args["slide_id"], args["element_id"], args["changes"])}
    if name == "delete_element":
        return ops.delete_element(doc, args["slide_id"], args["element_id"])
    if name == "arrange_element":
        return ops.arrange_element(doc, args["slide_id"], args["element_id"], args["to"])
    raise ToolError(f"No tool named {name}.")


def execute(name: str, args, pid: int) -> tuple[str, int | None]:
    """Runs a tool. Returns the text for the agent and the new version after a write."""
    if not isinstance(args, dict) or name not in VALIDATORS:
        raise ToolError(json.dumps({"INVALID_JSON": json.dumps(args)}))
    errors = [
        f"{'.'.join(map(str, e.absolute_path)) or 'input'}: {e.message}"
        for e in VALIDATORS[name].iter_errors(args)
    ]
    if errors:
        raise ToolError("Invalid input, nothing was changed:\n" + "\n".join(errors[:10]))
    con = db.connect()
    try:
        return _run(con, name, args, pid)
    finally:
        con.close()


def _run(con, name: str, args: dict, pid: int) -> tuple[str, int | None]:
    try:
        row = find(con, pid)
    except HTTPException:
        raise ToolError("This presentation was deleted.") from None
    if name == "get_presentation":
        out = {k: row[k] for k in ("title", "version", "doc")}
        out["slide_count"] = len(row["doc"]["slides"])
        return json.dumps(out, separators=(",", ":")), None
    if name == "rename_presentation":
        saved = write(con, pid, row["version"], args["title"], None)
        return "Renamed.", saved["version"]
    # Someone may save in the editor between the read and the write: then the change is made
    # again on their doc, as each change names its slide and element by id.
    for _ in range(3):
        if name == "replace_doc":
            doc, made = args["doc"], None
        else:
            doc = copy.deepcopy(row["doc"])
            try:
                made = change(name, doc, args)
            except ValueError as e:
                raise ToolError(f"{e} Nothing was changed.") from None
        found = problems(doc)
        if found:
            raise ToolError(
                "The change would break the doc, so nothing was saved:\n"
                + "\n".join(found)
                + f"\nFix these and call {name} again."
            )
        try:
            saved = write(con, pid, row["version"], None, doc)
        except HTTPException as e:
            if e.status_code != 409:
                raise
            row = find(con, pid)
            continue
        text = json.dumps({"ok": True, "version": saved["version"], **(made or {})}, separators=(",", ":"))
        return text, saved["version"]
    raise ToolError("The presentation keeps changing in the editor. Call get_presentation and try again.")
