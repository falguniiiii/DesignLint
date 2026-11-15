"""
Structures produced by the rule engine (app/rules/*) and the
recommendation layer (app/services/recommendations.py). Nothing in here
comes from Gemini - these are DesignLint's own judgments and suggestions,
computed from the validated ExtractionResult.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.extraction import BoundingBox, ImageMeta

Severity = Literal["major", "minor", "suggestion"]
Category = Literal["Color", "Typography", "Spacing", "Consistency"]


class ColorSuggestion(BaseModel):
    """One entry in a suggested color palette."""
    role: str
    hex: str
    usage: str
    source: Literal["detected", "derived"] = "derived"


class Recommendation(BaseModel):
    """
    Structured, actionable guidance attached to a finding.
    """
    whyItMatters: str
    fix: str
    suggestedValue: Optional[str] = None
    palette: Optional[list[ColorSuggestion]] = None


class RawFinding(BaseModel):
    """
    Produced directly by the rule engine. Contains detection evidence,
    not user-facing recommendation text.
    """
    id: str
    category: Category
    severity: Severity
    title: str
    description: str
    confidence: float = Field(ge=0, le=1)
    relatedElements: list[str] = Field(default_factory=list)
    spacingGaps: Optional[list[float]] = Field(default=None, exclude=True)


class Finding(BaseModel):
    """A RawFinding plus its structured recommendation."""
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
    Minimal element information needed to position annotations
    on the uploaded screenshot.
    """
    id: str
    type: str
    boundingBox: BoundingBox


class AuditResult(BaseModel):
    overallScore: int = Field(ge=0, le=100)
    categoryScores: list[CategoryScore]
    findings: list[Finding]

    # Palette guidance is independent of whether any finding exists.
    palette: list[ColorSuggestion] = Field(default_factory=list)

    elementCount: int
    image: ImageMeta
    elements: list[ElementRef]