
"""
Validation layer: raw Gemini text -> trusted ExtractionResult, or a clear error.

Gemini can return malformed JSON, missing fields, or nonsensical values.
This module normalizes keys, sanitizes recoverable values, and drops
individual invalid elements or colors rather than failing the entire
analysis over one bad item.

Bounding boxes are checked against the screenshot dimensions. Invalid
geometry is dropped, while partially visible elements are clipped to
the visible image area.

Nothing past this module should ever have to defend against malformed
Gemini data again - if a result comes out of validate_extraction, it is
guaranteed to match the schema.
"""

import json
import math
import re

from pydantic import ValidationError

from app.schemas.extraction import ExtractionResult
from app.schemas.normalization import remap_keys


_HEX_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

_TOP_LEVEL_KEYS = {"image", "elements", "colors"}
_TOP_LEVEL_ALIASES = {
    "colours": "colors",
    "uielements": "elements",
}

_ELEMENT_KEYS = {"id", "type", "label", "boundingBox", "estimatedFontSize"}
_ELEMENT_ALIASES = {
    "elementid": "id",
    "elementtype": "type",
    "fontsize": "estimatedFontSize",
    "bbox": "boundingBox",
    "box": "boundingBox",
}

_BOUNDING_BOX_KEYS = {"x", "y", "width", "height"}
_BOUNDING_BOX_ALIASES = {
    "w": "width",
    "h": "height",
}

_COLOR_KEYS = {"hex", "role"}
_COLOR_ALIASES = {
    "color": "hex",
    "colour": "hex",
}

_IMAGE_KEYS = {"width", "height"}


class ExtractionValidationError(Exception):
    """Raised when Gemini's response cannot be turned into a valid ExtractionResult."""


def validate_extraction(raw_text: str) -> ExtractionResult:
    cleaned = _strip_markdown_fences(raw_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ExtractionValidationError(
            f"Gemini's response was not valid JSON: {exc}"
        ) from exc

    sanitized = _sanitize_payload(parsed)

    try:
        return ExtractionResult.model_validate(sanitized)
    except ValidationError as exc:
        raise ExtractionValidationError(
            f"Gemini's response did not match the expected structure: {exc}"
        ) from exc


def _strip_markdown_fences(text: str) -> str:
    """
    Models sometimes wrap JSON in ```json ... ``` even when told not to.
    Strip that defensively rather than failing on otherwise-valid JSON.
    """
    stripped = text.strip()

    if stripped.startswith("```"):
        stripped = stripped.strip("`")

        if stripped.lower().startswith("json"):
            stripped = stripped[4:]

    return stripped.strip()


def _sanitize_payload(parsed):
    """
    Clean parsed JSON before strict schema validation.

    Normalize keys first, then sanitize individual elements and colors.
    Image dimensions are processed before elements so bounding boxes
    can be checked against the actual screenshot boundaries.
    """
    if not isinstance(parsed, dict):
        return parsed

    sanitized = remap_keys(parsed, _TOP_LEVEL_KEYS, _TOP_LEVEL_ALIASES)

    raw_image = sanitized.get("image")
    image_width = None
    image_height = None

    if isinstance(raw_image, dict):
        image = remap_keys(raw_image, _IMAGE_KEYS)

        image_width = _positive_integer(image.get("width"))
        image_height = _positive_integer(image.get("height"))

        if image_width is not None:
            image["width"] = image_width

        if image_height is not None:
            image["height"] = image_height

        sanitized["image"] = image

    raw_elements = sanitized.get("elements")

    sanitized["elements"] = (
        [
            cleaned
            for index, element in enumerate(raw_elements)
            if (
                cleaned := _sanitize_element(
                    element,
                    index,
                    image_width,
                    image_height,
                )
            ) is not None
        ]
        if isinstance(raw_elements, list)
        else []
    )

    raw_colors = sanitized.get("colors")

    sanitized["colors"] = (
        [
            cleaned
            for color in raw_colors
            if (cleaned := _sanitize_color(color)) is not None
        ]
        if isinstance(raw_colors, list)
        else []
    )

    return sanitized


def _finite_number(value):
    """Convert a value to a finite float, or return None."""
    if isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    return number if math.isfinite(number) else None


def _positive_integer(value):
    """Convert a finite positive dimension to an integer."""
    number = _finite_number(value)

    if number is None or number <= 0:
        return None

    rounded = round(number)

    return rounded if rounded > 0 else None


def _sanitize_element(
    el,
    index,
    image_width=None,
    image_height=None,
):
    """
    Sanitize one UI element.

    Invalid geometry is dropped. Valid geometry extending beyond the
    screenshot is clipped to the visible image area.
    """
    if not isinstance(el, dict):
        return None

    el = remap_keys(el, _ELEMENT_KEYS, _ELEMENT_ALIASES)

    bbox = el.get("boundingBox")

    if not isinstance(bbox, dict):
        return None

    bbox = remap_keys(
        bbox,
        _BOUNDING_BOX_KEYS,
        _BOUNDING_BOX_ALIASES,
    )

    x_value = _finite_number(bbox.get("x", 0))
    y_value = _finite_number(bbox.get("y", 0))
    width_value = _finite_number(bbox.get("width", 1))
    height_value = _finite_number(bbox.get("height", 1))

    if any(
        value is None
        for value in (
            x_value,
            y_value,
            width_value,
            height_value,
        )
    ):
        return None

    # Zero or negative dimensions do not describe a usable UI element.
    if width_value <= 0 or height_value <= 0:
        return None

    x = round(x_value)
    y = round(y_value)
    width = round(width_value)
    height = round(height_value)

    if width <= 0 or height <= 0:
        return None

    # Calculate the original right and bottom edges.
    left = max(0, x)
    top = max(0, y)
    right = x + width
    bottom = y + height

    # Clip the bounding box to the screenshot boundaries.
    if image_width is not None:
        right = min(right, image_width)

    if image_height is not None:
        bottom = min(bottom, image_height)

    # Drop elements with no visible area inside the screenshot.
    if right <= left or bottom <= top:
        return None

    width = right - left
    height = bottom - top

    # Sanitize estimated font size independently.
    font_size = el.get("estimatedFontSize")

    if font_size in (None, ""):
        font_size = None
    else:
        font_number = _finite_number(font_size)

        if font_number is None or font_number <= 0:
            font_size = None
        else:
            font_size = round(font_number)

            if font_size <= 0:
                font_size = None

    return {
        "id": (
            str(el.get("id"))
            if el.get("id") not in (None, "")
            else f"element-{index}"
        ),
        # UIElement normalizes known synonyms and unknown types.
        "type": (
            el.get("type")
            if isinstance(el.get("type"), str)
            else "other"
        ),
        "label": (
            el.get("label")
            if isinstance(el.get("label"), str)
            else None
        ),
        "boundingBox": {
            "x": left,
            "y": top,
            "width": width,
            "height": height,
        },
        "estimatedFontSize": font_size,
    }


def _sanitize_color(c):
    """Coerce a single color entry, or return None to drop it entirely."""
    if not isinstance(c, dict):
        return None

    c = remap_keys(c, _COLOR_KEYS, _COLOR_ALIASES)

    hex_value = c.get("hex")

    if not isinstance(hex_value, str):
        return None

    value = hex_value.strip()

    if not value.startswith("#"):
        value = f"#{value}"

    if len(value) == 9:
        # #RRGGBBAA - discard the alpha channel we do not use.
        value = value[:7]

    if not _HEX_PATTERN.match(value):
        return None

    return {
        "hex": value,
        "role": c.get("role") if isinstance(c.get("role"), str) else None,
    }
