"""
This schema is the contract between Gemini and the rest of DesignLint.

It intentionally only describes OBSERVABLE properties (what's on screen,
where, roughly how big) - never judgments like "well-spaced" or "too many
colors". That judgment is the rule engine's job (Phase 3), not Gemini's.

Anything Gemini returns is validated against this schema before it is
trusted by any other part of the application.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.schemas.normalization import resolve_alias

ElementType = Literal[
    "button", "heading", "body_text", "card", "navigation",
    "image", "input", "icon", "container", "other",
]

# Gemini will keep inventing reasonable-but-different phrasings for the
# same concept ("text", "body text", "paragraph", "label"...) since it's
# not actually a fixed enum on Gemini's side, just a suggestion in the
# prompt. Rather than patching one exact string at a time forever, map
# known synonyms here, and treat anything still unrecognized as "other"
# rather than failing the whole analysis over one element's label.
# Formatting differences (case/space/hyphen) are handled generically by
# resolve_alias() - only genuine synonyms need an entry here.
TYPE_ALIASES: dict[str, str] = {
    "text": "body_text",
    "paragraph": "body_text",
    "label": "body_text",
    "caption": "body_text",
    "textbox": "input",
    "text_field": "input",
    "text_input": "input",
    "img": "image",
    "photo": "image",
    "picture": "image",
    "cta": "button",
    "link": "button",
    "nav": "navigation",
    "menu": "navigation",
    "navbar": "navigation",
}
_VALID_TYPES = {
    "button", "heading", "body_text", "card", "navigation",
    "image", "input", "icon", "container", "other",
}


class BoundingBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class UIElement(BaseModel):
    id: str
    type: ElementType
    label: Optional[str] = None
    boundingBox: BoundingBox
    estimatedFontSize: Optional[int] = Field(default=None, gt=0)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        # Never raise here: an unrecognized type from Gemini shouldn't
        # fail the entire analysis. resolve_alias() normalizes formatting
        # first, then only accepts a known alias or already-valid type -
        # anything genuinely unrecognized falls back to "other" instead
        # of being accepted as-is.
        if not isinstance(v, str):
            return "other"
        return resolve_alias(v, TYPE_ALIASES, _VALID_TYPES, fallback="other")

    @field_validator("estimatedFontSize", mode="before")
    @classmethod
    def treat_zero_as_not_applicable(cls, v):
        # Gemini sends 0 for elements with no meaningful font size (icons,
        # containers) rather than omitting the field. 0 isn't a valid font
        # size, so treat it the same as "not provided" rather than rejecting
        # the whole response over it.
        if v == 0:
            return None
        return v


class DominantColor(BaseModel):
    hex: str

    @field_validator("hex")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("#") or len(v) not in (4, 7):
            raise ValueError(f"'{v}' is not a valid hex color")
        return v.lower()

    role: Optional[str] = None


class ImageMeta(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ExtractionResult(BaseModel):
    """
    The full structured output expected from Gemini for one screenshot.
    This is what gets handed to the rule engine in Phase 3.
    """
    image: ImageMeta
    elements: list[UIElement] = Field(default_factory=list)
    colors: list[DominantColor] = Field(default_factory=list)
