"""
Typography rules.

All checks here operate on `estimatedFontSize`, which is explicitly a
Gemini estimate, not a measured value. Findings and descriptions are
worded accordingly ("appears to", "estimated") rather than stating
exact pixel facts.
"""
from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding

TEXT_TYPES = {"heading", "body_text"}
MAX_DISTINCT_SIZES = 4
SMALL_TEXT_THRESHOLD_PX = 12


def run(extraction: ExtractionResult) -> list[RawFinding]:
    findings: list[RawFinding] = []

    text_elements = [
        e for e in extraction.elements
        if e.type in TEXT_TYPES and e.estimatedFontSize is not None
    ]

    findings.extend(_check_font_size_proliferation(text_elements))
    findings.extend(_check_small_text(text_elements))
    findings.extend(_check_heading_hierarchy(extraction.elements))

    return findings


def _check_font_size_proliferation(text_elements) -> list[RawFinding]:
    distinct_sizes = {e.estimatedFontSize for e in text_elements}
    if len(distinct_sizes) <= MAX_DISTINCT_SIZES:
        return []

    return [
        RawFinding(
            id="TYPOGRAPHY-001",
            category="Typography",
            severity="minor",
            title="Many distinct text sizes detected",
            description=(
                f"Text elements appear to use {len(distinct_sizes)} different "
                "estimated font sizes. A large number of size levels can make "
                "typographic hierarchy feel inconsistent."
            ),
            confidence=0.5,
            relatedElements=[e.id for e in text_elements],
        )
    ]


def _check_small_text(text_elements) -> list[RawFinding]:
    small = [e for e in text_elements if e.estimatedFontSize < SMALL_TEXT_THRESHOLD_PX]
    if not small:
        return []

    return [
        RawFinding(
            id="TYPOGRAPHY-002",
            category="Typography",
            severity="major",
            title="Very small text detected",
            description=(
                f"{len(small)} text element(s) have an estimated font size below "
                f"{SMALL_TEXT_THRESHOLD_PX}px, which may be difficult to read for many users."
            ),
            confidence=0.6,
            relatedElements=[e.id for e in small],
        )
    ]


def _check_heading_hierarchy(elements) -> list[RawFinding]:
    headings = [e for e in elements if e.type == "heading" and e.estimatedFontSize]
    body = [e for e in elements if e.type == "body_text" and e.estimatedFontSize]

    if not headings or not body:
        return []

    avg_heading = sum(e.estimatedFontSize for e in headings) / len(headings)
    avg_body = sum(e.estimatedFontSize for e in body) / len(body)

    if avg_heading > avg_body:
        return []

    return [
        RawFinding(
            id="TYPOGRAPHY-003",
            category="Typography",
            severity="minor",
            title="Weak heading hierarchy",
            description=(
                "Headings do not appear noticeably larger than body text, which can "
                "make it harder for users to scan the page's structure."
            ),
            confidence=0.5,
            relatedElements=[e.id for e in headings + body],
        )
    ]
