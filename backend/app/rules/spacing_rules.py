
"""
Spacing rules.

We deliberately do NOT claim to detect exact spacing values (e.g. this
gap is 19px, others are 16px) - a screenshot-derived bounding box isn't
precise enough to support that. Instead we look at RELATIVE variance
between gaps among the same element type and within the same vertical
layout track.

Elements in separate columns or grid tracks are evaluated independently
so their different spacing systems are not incorrectly compared.

Known structural metadata is used as an additional grouping constraint:
elements from different known sections or component groups are never
compared.
"""

from collections import defaultdict

from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding

MIN_ELEMENTS_TO_COMPARE = 3
RELATIVE_DEVIATION_THRESHOLD = 0.5  # 50% deviation from the average gap

# Elements must overlap horizontally and have a reasonably aligned
# left, center, or right edge to belong to the same vertical track.
MIN_HORIZONTAL_OVERLAP_RATIO = 0.5
MAX_ALIGNMENT_OFFSET_RATIO = 0.25


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


def _metadata_compatible(a, b) -> bool:
    """
    Prevent comparisons across known, different structural groups.

    Missing metadata does not establish a relationship or a conflict,
    so geometric matching remains available when metadata is unavailable.
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


def _same_vertical_track(a, b) -> bool:
    """Return whether two elements share a horizontal layout track."""
    if not _metadata_compatible(a, b):
        return False

    box_a = a.boundingBox
    box_b = b.boundingBox

    overlap = max(
        0,
        min(box_a.x + box_a.width, box_b.x + box_b.width)
        - max(box_a.x, box_b.x),
    )

    narrower_width = min(box_a.width, box_b.width)
    overlap_ratio = overlap / narrower_width

    if overlap_ratio < MIN_HORIZONTAL_OVERLAP_RATIO:
        return False

    left_edge_difference = abs(box_a.x - box_b.x)

    center_a = box_a.x + box_a.width / 2
    center_b = box_b.x + box_b.width / 2
    center_difference = abs(center_a - center_b)

    right_edge_a = box_a.x + box_a.width
    right_edge_b = box_b.x + box_b.width
    right_edge_difference = abs(right_edge_a - right_edge_b)

    closest_alignment = min(
        left_edge_difference,
        center_difference,
        right_edge_difference,
    )

    return closest_alignment <= narrower_width * MAX_ALIGNMENT_OFFSET_RATIO


def _group_into_vertical_tracks(elements: list) -> list[list]:
    """
    Group elements into independent vertical tracks.

    Complete-link matching is intentional: an element must align with
    every existing member of a track. This prevents a wide element from
    accidentally bridging two otherwise separate columns.
    """
    tracks: list[list] = []

    elements_sorted = sorted(
        elements,
        key=lambda element: (
            element.boundingBox.x + element.boundingBox.width / 2,
            element.boundingBox.y,
        ),
    )

    for element in elements_sorted:
        compatible_tracks = []

        element_center = (
            element.boundingBox.x + element.boundingBox.width / 2
        )

        for track in tracks:
            if all(_same_vertical_track(element, member) for member in track):
                track_center = sum(
                    member.boundingBox.x + member.boundingBox.width / 2
                    for member in track
                ) / len(track)

                compatible_tracks.append(
                    (abs(element_center - track_center), track)
                )

        if compatible_tracks:
            _, best_track = min(
                compatible_tracks,
                key=lambda item: item[0],
            )
            best_track.append(element)
        else:
            tracks.append([element])

    return tracks


def _get_vertical_gaps(elements: list) -> tuple[list, list]:
    """Return valid consecutive gaps and the elements participating in them."""
    elements_sorted = sorted(
        elements,
        key=lambda element: element.boundingBox.y,
    )

    gaps = []
    participating_elements = []
    seen_ids = set()

    for a, b in zip(elements_sorted, elements_sorted[1:]):
        gap = (
            b.boundingBox.y
            - (a.boundingBox.y + a.boundingBox.height)
        )

        if gap >= 0:
            gaps.append(gap)

            for element in (a, b):
                if element.id not in seen_ids:
                    participating_elements.append(element)
                    seen_ids.add(element.id)

    return gaps, participating_elements


def _check_vertical_gap_consistency(
    element_type: str,
    elements: list,
) -> RawFinding | None:
    inconsistent_tracks = []

    for track in _group_into_vertical_tracks(elements):
        if len(track) < MIN_ELEMENTS_TO_COMPARE:
            continue

        gaps, participating_elements = _get_vertical_gaps(track)

        if len(gaps) < 2:
            continue

        average_gap = sum(gaps) / len(gaps)

        if average_gap <= 0:
            continue

        max_deviation = max(
            abs(gap - average_gap)
            for gap in gaps
        )

        if (max_deviation / average_gap) > RELATIVE_DEVIATION_THRESHOLD:
            inconsistent_tracks.append((gaps, participating_elements))

    if not inconsistent_tracks:
        return None

    # Report only gaps and elements from tracks that actually contain
    # inconsistent spacing.
    inconsistent_gaps = [
        gap
        for gaps, _ in inconsistent_tracks
        for gap in gaps
    ]

    related_elements = [
        element
        for _, track_elements in inconsistent_tracks
        for element in track_elements
    ]

    return RawFinding(
        id=f"SPACING-{element_type.upper()}-001",
        category="Spacing",
        severity="minor",
        title=(
            f"Possible inconsistent spacing between "
            f"{element_type.replace('_', ' ')} elements"
        ),
        description=(
            f"Vertical gaps between repeated {element_type.replace('_', ' ')} "
            f"elements range from about {min(inconsistent_gaps)}px to "
            f"{max(inconsistent_gaps)}px, which is a noticeable spread."
        ),
        confidence=0.5,
        relatedElements=[element.id for element in related_elements],
    )
