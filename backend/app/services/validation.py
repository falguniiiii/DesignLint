"""
Validation layer: raw Gemini text -> trusted ExtractionResult, or a clear error.

Gemini can return malformed JSON, missing fields, or nonsensical values
(a "button" that's 3000px wide, negative coordinates, an unrecognized
type string, a font size given as a float, etc) - and it can also send
a genuinely correct FIELD under a differently-formatted KEY name (e.g.
"font_size" instead of "estimatedFontSize"). The strategy here is:
normalize key formatting and sanitize what's reasonably fixable, DROP
the individual element or color that isn't (rather than failing the
whole analysis over one bad item), and only raise
ExtractionValidationError for genuinely unrecoverable input (unparseable
JSON, or no usable structure at all).

Nothing past this module should ever have to defend against malformed
Gemini data again - if a result comes out of `validate_extraction`, it
is guaranteed to match the schema.
"""
import json
import re
from pydantic import ValidationError

from app.schemas.extraction import ExtractionResult
from app.schemas.normalization import remap_keys

_HEX_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Canonical key names for each structured object in the schema, plus
# EXPLICIT aliases for keys that are a genuinely different word/phrasing
# for the same concept (not just a formatting difference - formatting is
# handled generically by remap_keys/flatten_key regardless of case,
# spaces, hyphens, or underscores). Add an entry here only when two
# names really do mean the same field.
_TOP_LEVEL_KEYS = {"image", "elements", "colors"}
_TOP_LEVEL_ALIASES = {
    "colours": "colors",
    "uielements": "elements",
}

_ELEMENT_KEYS = {"id", "type", "label", "boundingBox", "estimatedFontSize"}
_ELEMENT_ALIASES = {
    "elementid": "id",
    "elementtype": "type",
    "fontsize": "estimatedFontSize",  # covers "font size" / "font-size" / "Font_Size"
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
    """Raised when Gemini's response cannot be turned into a valid ExtractionResult at all."""


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
        # Sanitization handles the common cases (bad type strings, float
        # coordinates, out-of-range font sizes, malformed colors, and
        # differently-formatted key names). If this still fails, the
        # response is malformed in a way we can't safely guess our way
        # around - e.g. the whole payload isn't a JSON object, or "image"
        # is missing entirely under any recognizable name.
        raise ExtractionValidationError(
            f"Gemini's response did not match the expected structure: {exc}"
        ) from exc


def _strip_markdown_fences(text: str) -> str:
    """
    Models sometimes wrap JSON in ```json ... ``` even when told not to.
    Strip that defensively rather than failing on an otherwise-valid response.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    return stripped.strip()


def _sanitize_payload(parsed):
    """
    Clean the parsed JSON before strict schema validation. Key names are
    normalized first (formatting only, via remap_keys), then individual
    malformed elements/colors are dropped rather than failing the entire
    analysis - a screenshot with 51 good elements and 1 weird one should
    still produce results for the 51.
    """
    if not isinstance(parsed, dict):
        return parsed  # not fixable - let pydantic raise a clear top-level error

    sanitized = remap_keys(parsed, _TOP_LEVEL_KEYS, _TOP_LEVEL_ALIASES)

    raw_elements = sanitized.get("elements")
    sanitized["elements"] = (
        [
            cleaned for i, el in enumerate(raw_elements)
            if (cleaned := _sanitize_element(el, i)) is not None
        ]
        if isinstance(raw_elements, list) else []
    )

    raw_colors = sanitized.get("colors")
    sanitized["colors"] = (
        [cleaned for c in raw_colors if (cleaned := _sanitize_color(c)) is not None]
        if isinstance(raw_colors, list) else []
    )

    raw_image = sanitized.get("image")
    if isinstance(raw_image, dict):
        sanitized["image"] = remap_keys(raw_image, _IMAGE_KEYS)

    return sanitized


def _sanitize_element(el, index):
    """Coerce a single element's fields, or return None to drop it entirely."""
    if not isinstance(el, dict):
        return None

    el = remap_keys(el, _ELEMENT_KEYS, _ELEMENT_ALIASES)

    bbox = el.get("boundingBox")
    if not isinstance(bbox, dict):
        return None  # no position data - can't meaningfully keep this element

    bbox = remap_keys(bbox, _BOUNDING_BOX_KEYS, _BOUNDING_BOX_ALIASES)

    try:
        x = max(0, round(float(bbox.get("x", 0))))
        y = max(0, round(float(bbox.get("y", 0))))
        width = max(1, round(float(bbox.get("width", 1))))
        height = max(1, round(float(bbox.get("height", 1))))
    except (TypeError, ValueError):
        return None  # coordinates weren't numeric at all - unrecoverable for this element

    font_size = el.get("estimatedFontSize")
    try:
        font_size = round(float(font_size)) if font_size not in (None, "") else None
        if font_size is not None and font_size <= 0:
            font_size = None
    except (TypeError, ValueError):
        font_size = None

    return {
        "id": str(el.get("id")) if el.get("id") not in (None, "") else f"element-{index}",
        # `type` is left as-is (even if missing/weird) - the UIElement
        # field_validator in extraction.py normalizes synonyms and falls
        # back to "other" for anything unrecognized.
        "type": el.get("type") if isinstance(el.get("type"), str) else "other",
        "label": el.get("label") if isinstance(el.get("label"), str) else None,
        "boundingBox": {"x": x, "y": y, "width": width, "height": height},
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
    if len(value) == 9:  # #RRGGBBAA - drop the alpha channel we don't use
        value = value[:7]
    if not _HEX_PATTERN.match(value):
        return None  # genuinely not a hex color - drop rather than guess

    return {
        "hex": value,
        "role": c.get("role") if isinstance(c.get("role"), str) else None,
    }
