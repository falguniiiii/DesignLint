"""
Structures produced by the rule engine (app/rules/*) and the
recommendation layer (app/services/recommendations.py). Nothing in here
comes from Gemini - these are 100% DesignLint's own judgments, computed
from the validated ExtractionResult.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.extraction import BoundingBox, ImageMeta

Severity = Literal["major", "minor", "suggestion"]
Category = Literal["Color", "Typography", "Spacing", "Consistency"]


class ColorSuggestion(BaseModel):
    """One entry in a suggested color palette."""
    role: str   # e.g. "Primary", "Background", "Secondary text"
    hex: str
    usage: str  # brief plain-language explanation of where to use it
    # "detected": taken directly from a color found in the screenshot.
    # "derived": computed by DesignLint from detected colors (e.g. lightness
    # adjusted for contrast). Lets the UI tell the two apart without
    # parsing the usage text.
    source: Literal["detected", "derived"] = "derived"


class Recommendation(BaseModel):
    """
    Structured, actionable guidance attached to a finding - built by the
    recommendation layer, never by the rule engine itself. Kept as
    separate fields (not one paragraph) so the frontend can render each
    part distinctly.
    """
    whyItMatters: str
    fix: str
    suggestedValue: Optional[str] = None
    palette: Optional[list[ColorSuggestion]] = None


class RawFinding(BaseModel):
    """
    Produced directly by the rule engine (app/rules/*): the raw detection
    signal only - what was found, how severe, how confident, and which
    elements it relates to. Does NOT include actionable guidance; that's
    added afterward by the recommendation layer, turning a RawFinding
    into a Finding. Keeping these separate means detection logic never
    needs to know or care how its output will be explained to the user.
    """
    id: str
    category: Category
    severity: Severity
    title: str
    description: str
    confidence: float = Field(ge=0, le=1)
    relatedElements: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    """A RawFinding plus the structured, actionable Recommendation built for it."""
    id: str
    category: Category
    severity: Severity
    title: str
    description: str
    confidence: float = Field(ge=0, le=1)
    relatedElements: list[str] = Field(default_factory=list)
    recommendation: Recommendation


class CategoryScore(BaseModel):
    category: Category
    score: int = Field(ge=0, le=100)


class ElementRef(BaseModel):
    """
    Minimal element info needed to position an annotation marker on the
    screenshot - the same bounding box data Gemini returned, carried
    through purely so the frontend can draw markers. Not a new judgment.
    """
    id: str
    type: str
    boundingBox: BoundingBox


class AuditResult(BaseModel):
    overallScore: int = Field(ge=0, le=100)
    categoryScores: list[CategoryScore]
    findings: list[Finding]
    elementCount: int
    image: ImageMeta
    elements: list[ElementRef]
