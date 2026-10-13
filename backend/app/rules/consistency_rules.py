"""
Consistency rules.

Checks whether repeated instances of the same component type (buttons,
cards) have noticeably different dimensions. Width is intentionally
excluded for buttons since button width naturally varies with label
text length - height is the more meaningful consistency signal there.
"""
from collections import defaultdict

from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding

CHECK_TYPES = {"button", "card"}
MIN_INSTANCES_TO_COMPARE = 2
RELATIVE_VARIANCE_THRESHOLD = 0.2  # 20% difference from the largest


def run(extraction: ExtractionResult) -> list[RawFinding]:
    findings: list[RawFinding] = []

    by_type: dict[str, list] = defaultdict(list)
    for element in extraction.elements:
        if element.type in CHECK_TYPES:
            by_type[element.type].append(element)

    for element_type, elements in by_type.items():
        if len(elements) < MIN_INSTANCES_TO_COMPARE:
            continue

        finding = _check_height_consistency(element_type, elements)
        if finding:
            findings.append(finding)

        if element_type == "card":
            finding = _check_width_consistency(element_type, elements)
            if finding:
                findings.append(finding)

    return findings


def _check_height_consistency(element_type: str, elements: list) -> RawFinding | None:
    heights = [e.boundingBox.height for e in elements]
    if max(heights) == 0 or (max(heights) - min(heights)) / max(heights) <= RELATIVE_VARIANCE_THRESHOLD:
        return None

    return RawFinding(
        id=f"CONSISTENCY-{element_type.upper()}-HEIGHT",
        category="Consistency",
        severity="minor",
        title=f"Inconsistent {element_type} heights",
        description=(
            f"Repeated {element_type} elements have heights ranging from "
            f"{min(heights)}px to {max(heights)}px."
        ),
        confidence=0.55,
        relatedElements=[e.id for e in elements],
    )


def _check_width_consistency(element_type: str, elements: list) -> RawFinding | None:
    widths = [e.boundingBox.width for e in elements]
    if max(widths) == 0 or (max(widths) - min(widths)) / max(widths) <= RELATIVE_VARIANCE_THRESHOLD:
        return None

    return RawFinding(
        id=f"CONSISTENCY-{element_type.upper()}-WIDTH",
        category="Consistency",
        severity="suggestion",
        title=f"Inconsistent {element_type} widths",
        description=(
            f"Repeated {element_type} elements have widths ranging from "
            f"{min(widths)}px to {max(widths)}px."
        ),
        confidence=0.45,
        relatedElements=[e.id for e in elements],
    )
