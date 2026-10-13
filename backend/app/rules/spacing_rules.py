"""
Spacing rules.

We deliberately do NOT claim to detect exact spacing values (e.g. "this
gap is 19px, others are 16px") - a screenshot-derived bounding box isn't
precise enough to support that. Instead we look at RELATIVE variance
between gaps among the same element type and flag it only when the
deviation is large enough to plausibly be a real inconsistency rather
than measurement noise.
"""
from collections import defaultdict

from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding

MIN_ELEMENTS_TO_COMPARE = 3
RELATIVE_DEVIATION_THRESHOLD = 0.5  # 50% deviation from the average gap


def run(extraction: ExtractionResult) -> list[RawFinding]:
    findings: list[RawFinding] = []

    by_type: dict[str, list] = defaultdict(list)
    for element in extraction.elements:
        by_type[element.type].append(element)

    for element_type, elements in by_type.items():
        if len(elements) < MIN_ELEMENTS_TO_COMPARE:
            continue

        finding = _check_vertical_gap_consistency(element_type, elements)
        if finding:
            findings.append(finding)

    return findings


def _check_vertical_gap_consistency(element_type: str, elements: list) -> RawFinding | None:
    elements_sorted = sorted(elements, key=lambda e: e.boundingBox.y)

    gaps = []
    for a, b in zip(elements_sorted, elements_sorted[1:]):
        gap = b.boundingBox.y - (a.boundingBox.y + a.boundingBox.height)
        if gap >= 0:
            gaps.append(gap)

    if len(gaps) < 2:
        return None

    average_gap = sum(gaps) / len(gaps)
    if average_gap <= 0:
        return None

    max_deviation = max(abs(g - average_gap) for g in gaps)
    if (max_deviation / average_gap) <= RELATIVE_DEVIATION_THRESHOLD:
        return None

    return RawFinding(
        id=f"SPACING-{element_type.upper()}-001",
        category="Spacing",
        severity="minor",
        title=f"Possible inconsistent spacing between {element_type.replace('_', ' ')} elements",
        description=(
            f"Vertical gaps between repeated {element_type.replace('_', ' ')} elements "
            f"range from about {min(gaps)}px to {max(gaps)}px, which is a noticeable spread."
        ),
        confidence=0.5,
        relatedElements=[e.id for e in elements_sorted],
    )
