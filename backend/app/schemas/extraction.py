
"""
This schema is the contract between Gemini and the rest of DesignLint.

It describes observable visual properties and cautiously inferred
structural information. Design judgments remain the responsibility
of the deterministic rule engine.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.schemas.normalization import resolve_alias

ElementType = Literal[
    "button", "heading", "body_text", "card", "navigation",
    "image", "input", "icon", "container", "other",
]

SectionType = Literal[
    "header", "hero", "navigation", "sidebar", "main_content",
    "product_grid", "content_grid", "form", "footer", "other",
]

ElementRole = Literal[
    "page_title", "section_heading", "body_copy",
    "primary_action", "secondary_action", "navigation_item",
    "price", "metric", "product_image", "decorative_image",
    "form_control", "other",
]

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

SECTION_ALIASES: dict[str, str] = {
    "top_bar": "header",
    "navbar": "navigation",
    "nav": "navigation",
    "main": "main_content",
    "content": "main_content",
    "products": "product_grid",
    "product_listing": "product_grid",
    "grid": "content_grid",
    "bottom": "footer",
}

_VALID_SECTIONS = {
    "header", "hero", "navigation", "sidebar", "main_content",
    "product_grid", "content_grid", "form", "footer", "other",
}

ROLE_ALIASES: dict[str, str] = {
    "title": "page_title",
    "main_heading": "page_title",
    "h1": "page_title",
    "heading": "section_heading",
    "subtitle": "body_copy",
    "description": "body_copy",
    "primary_cta": "primary_action",
    "cta": "primary_action",
    "secondary_cta": "secondary_action",
    "nav_item": "navigation_item",
    "menu_item": "navigation_item",
    "product_price": "price",
    "amount": "price",
    "stat": "metric",
    "kpi": "metric",
    "input_field": "form_control",
}

_VALID_ROLES = {
    "page_title", "section_heading", "body_copy",
    "primary_action", "secondary_action", "navigation_item",
    "price", "metric", "product_image", "decorative_image",
    "form_control", "other",
}


class BoundingBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Section(BaseModel):
    id: str
    type: SectionType
    boundingBox: BoundingBox
    label: Optional[str] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        if not isinstance(v, str):
            return "other"
        return resolve_alias(
            v, SECTION_ALIASES, _VALID_SECTIONS, fallback="other"
        )


class UIElement(BaseModel):
    id: str
    type: ElementType
    label: Optional[str] = None
    boundingBox: BoundingBox
    estimatedFontSize: Optional[int] = Field(default=None, gt=0)
    role: Optional[ElementRole] = None
    sectionId: Optional[str] = None
    groupId: Optional[str] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        if not isinstance(v, str):
            return "other"
        return resolve_alias(v, TYPE_ALIASES, _VALID_TYPES, fallback="other")

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v):
        if not isinstance(v, str):
            return "other" if v is not None else None
        return resolve_alias(v, ROLE_ALIASES, _VALID_ROLES, fallback="other")

    @field_validator("estimatedFontSize", mode="before")
    @classmethod
    def treat_zero_as_not_applicable(cls, v):
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
    Structured output expected from Gemini for one screenshot.
    """
    image: ImageMeta
    elements: list[UIElement] = Field(default_factory=list)
    colors: list[DominantColor] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
