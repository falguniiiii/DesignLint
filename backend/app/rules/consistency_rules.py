"""
Consistency rules.

Checks whether repeated instances of the same component type (buttons,
cards) have noticeably different dimensions.

Elements with known structural metadata are compared only when their
sectionId and groupId values are compatible. Missing metadata remains
compatible so older extraction results retain their previous behavior.

Width is intentionally excluded for buttons because button width
naturally varies with label text length.
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
        for group in _group_by_metadata(elements):
            if len(group) < MIN_INSTANCES_TO_COMPARE:
                continue

            finding = _check_height_consistency(element_type, group)
            if finding:
                findings.append(finding)

            if element_type == "card":
                finding = _check_width_consistency(element_type, group)
                if finding:
                    findings.append(finding)

    return findings


def _metadata_compatible(a, b) -> bool:
    """
    Return whether two elements can be compared using known metadata.

    A conflict exists only when both elements have a value for the same
    metadata field and those values differ.

    Missing metadata does not block comparison.
    """
    if (
        a.sectionId is not None
        and b.sectionId is not None
        and a.sectionId != b.sectionId
    ):
        return False

    if (
        a.groupId is not None
        and b.groupId is not None
        and a.groupId != b.groupId
    ):
        return False

    return True


def _group_by_metadata(elements: list) -> list[list]:
    """
    Build conservative groups of mutually compatible elements.

    Complete-link grouping prevents an element with missing metadata
    from bridging two elements whose known metadata conflicts.
    """
    groups: list[list] = []

    for element in elements:
        compatible_groups = [
            group
            for group in groups
            if all(
                _metadata_compatible(element, member)
                for member in group
            )
        ]

        if compatible_groups:
            compatible_groups[0].append(element)
        else:
            groups.append([element])

    return groups


def _check_height_consistency(
    element_type: str,
    elements: list,
) -> RawFinding | None:
    heights = [element.boundingBox.height for element in elements]

    if (
        max(heights) == 0
        or (max(heights) - min(heights)) / max(heights)
        <= RELATIVE_VARIANCE_THRESHOLD
    ):
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
        relatedElements=[element.id for element in elements],
    )


def _check_width_consistency(
    element_type: str,
    elements: list,
) -> RawFinding | None:
    widths = [element.boundingBox.width for element in elements]

    if (
        max(widths) == 0
        or (max(widths) - min(widths)) / max(widths)
        <= RELATIVE_VARIANCE_THRESHOLD
    ):
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
        relatedElements=[element.id for element in elements],
    )
