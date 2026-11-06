"""Changes to a presentation doc. Each works on the dict in place and raises ValueError with a
message the agent can act on when an id or index is wrong."""

import copy
import uuid

LAYOUTS = ["title", "title_content", "two_columns", "section", "blank"]
ARRANGE = ["front", "back", "forward", "backward"]


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def paras(text: str = "", list_: str | None = None) -> list[dict]:
    out = []
    for line in text.split("\n") if text else [""]:
        para = {"runs": [{"text": line}]}
        if list_:
            para["list"] = list_
        out.append(para)
    return out


def text_box(x, y, w, h, text="", **rest) -> dict:
    return {
        "id": new_id(),
        "type": "text",
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "paras": paras(text),
        "size": 24,
        **rest,
    }


def placeholders(layout: str, title: str = "", body: str = "") -> list[dict]:
    """The title and body boxes a layout lays on a slide. Same places as the editor's
    frontend/src/slides/layouts.ts."""

    def bullets(x, w, words=body):
        return text_box(x, 140, w, 360, role="body", paras=paras(words, "bullet"))

    def heading():
        return text_box(60, 40, 840, 80, title, size=40, role="title", valign="middle")

    if layout == "title":
        return [
            text_box(60, 170, 840, 110, title, size=54, role="title", align="center", valign="bottom"),
            text_box(60, 290, 840, 60, body, size=28, align="center", color="#555555", role="body"),
        ]
    if layout == "title_content":
        return [heading(), bullets(60, 840)]
    if layout == "two_columns":
        return [heading(), bullets(60, 405), bullets(495, 405, "")]
    if layout == "section":
        return [text_box(60, 200, 840, 100, title, size=48, role="title", valign="middle")]
    if layout == "blank":
        return []
    raise ValueError(f"No layout '{layout}'. Use one of: {', '.join(LAYOUTS)}.")


def find_slide(doc: dict, slide_id: str) -> tuple[int, dict]:
    for i, slide in enumerate(doc["slides"]):
        if slide["id"] == slide_id:
            return i, slide
    ids = ", ".join(s["id"] for s in doc["slides"]) or "none"
    raise ValueError(f"No slide with id '{slide_id}'. Slide ids in order: {ids}.")


def find_element(slide: dict, element_id: str) -> tuple[int, dict]:
    for i, element in enumerate(slide["elements"]):
        if element["id"] == element_id:
            return i, element
    ids = ", ".join(e["id"] for e in slide["elements"]) or "none"
    raise ValueError(f"No element '{element_id}' on slide '{slide['id']}'. Its elements: {ids}.")


def add_slide(
    doc: dict, layout: str = "title_content", position: int | None = None, title: str = "", body: str = ""
) -> dict:
    slide = {"id": new_id(), "elements": placeholders(layout, title, body)}
    slides = doc["slides"]
    if position is None:
        position = len(slides)
    if not 0 <= position <= len(slides):
        raise ValueError(f"position must be 0 to {len(slides)}, got {position}.")
    slides.insert(position, slide)
    return slide


def delete_slide(doc: dict, slide_id: str) -> None:
    i, _ = find_slide(doc, slide_id)
    del doc["slides"][i]


def duplicate_slide(doc: dict, slide_id: str) -> dict:
    i, slide = find_slide(doc, slide_id)
    twin = copy.deepcopy(slide)
    twin["id"] = new_id()
    for element in twin["elements"]:
        element["id"] = new_id()
    doc["slides"].insert(i + 1, twin)
    return twin


def move_slide(doc: dict, slide_id: str, to: int) -> None:
    i, slide = find_slide(doc, slide_id)
    last = len(doc["slides"]) - 1
    if not 0 <= to <= last:
        raise ValueError(f"to must be 0 to {last}, got {to}.")
    del doc["slides"][i]
    doc["slides"].insert(to, slide)


def apply_layout(
    doc: dict, slide_id: str, layout: str, title: str | None = None, body: str | None = None
) -> dict:
    """Swaps the slide's title and body boxes for the layout's, carrying their text over in order,
    or filling them with `title` and `body` when given. Other elements stay."""
    _, slide = find_slide(doc, slide_id)
    fresh = placeholders(layout, title or "", body or "")
    old = {role: [e for e in slide["elements"] if e.get("role") == role] for role in ("title", "body")}
    for box in fresh:
        given = title if box["role"] == "title" else body
        if old[box["role"]]:
            was = old[box["role"]].pop(0)["paras"]
            if given is None:
                box["paras"] = was
    slide["elements"] = [e for e in slide["elements"] if e.get("role") not in ("title", "body")]
    slide["elements"][:0] = fresh
    return slide


def add_element(doc: dict, slide_id: str, element: dict) -> dict:
    _, slide = find_slide(doc, slide_id)
    element = {**element, "id": new_id()}
    slide["elements"].append(element)
    return element


def update_element(doc: dict, slide_id: str, element_id: str, changes: dict) -> dict:
    _, slide = find_slide(doc, slide_id)
    _, element = find_element(slide, element_id)
    if "id" in changes or ("type" in changes and changes["type"] != element["type"]):
        raise ValueError("An element's id and type cannot change. Delete it and add a new one.")
    for key, value in changes.items():
        if value is None:
            element.pop(key, None)
        else:
            element[key] = value
    return element


def delete_element(doc: dict, slide_id: str, element_id: str) -> None:
    _, slide = find_slide(doc, slide_id)
    i, _ = find_element(slide, element_id)
    del slide["elements"][i]


def arrange_element(doc: dict, slide_id: str, element_id: str, to: str) -> None:
    """Moves an element in the drawing order: the last element lies on top."""
    _, slide = find_slide(doc, slide_id)
    i, element = find_element(slide, element_id)
    elements = slide["elements"]
    if to not in ARRANGE:
        raise ValueError(f"to must be one of {', '.join(ARRANGE)}, got '{to}'.")
    j = {"front": len(elements) - 1, "back": 0, "forward": i + 1, "backward": i - 1}[to]
    j = max(0, min(len(elements) - 1, j))
    del elements[i]
    elements.insert(j, element)
