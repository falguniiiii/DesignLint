
from app.schemas.extraction import (
    BoundingBox,
    ExtractionResult,
    ImageMeta,
    UIElement,
)
from app.rules.spacing_rules import run


def make_element(id, x, y, width=200, height=20):
    return UIElement(
        id=id,
        type="button",
        boundingBox=BoundingBox(
            x=x,
            y=y,
            width=width,
            height=height,
        ),
    )


def run_spacing_rule(elements):
    extraction = ExtractionResult(
        image=ImageMeta(width=1200, height=1000),
        elements=elements,
        colors=[],
    )
    return run(extraction)


def test_separate_columns_with_different_consistent_gaps_are_not_flagged():
    elements = [
        # Left column: 20px gaps.
        make_element("left-1", 100, 0),
        make_element("left-2", 100, 40),
        make_element("left-3", 100, 80),

        # Right column: 80px gaps.
        make_element("right-1", 700, 0),
        make_element("right-2", 700, 100),
        make_element("right-3", 700, 200),
    ]

    findings = run_spacing_rule(elements)

    assert not any(f.id == "SPACING-BUTTON-001" for f in findings)


def test_grid_columns_with_different_consistent_gaps_are_not_flagged():
    elements = []

    # Three independent grid columns, each with internally consistent gaps.
    column_positions = [
        (40, 60),    # 20px gaps
        (340, 90),   # 50px gaps
        (640, 130),  # 90px gaps
    ]

    for column_index, (x, row_step) in enumerate(column_positions):
        for row_index in range(3):
            elements.append(
                make_element(
                    f"col-{column_index}-row-{row_index}",
                    x,
                    row_index * row_step,
                    width=180,
                    height=40,
                )
            )

    findings = run_spacing_rule(elements)

    assert not any(f.id == "SPACING-BUTTON-001" for f in findings)


def test_inconsistent_spacing_within_a_column_is_still_flagged():
    elements = [
        make_element("item-1", 100, 0),
        make_element("item-2", 100, 40),
        make_element("item-3", 100, 140),
    ]

    findings = run_spacing_rule(elements)

    spacing_findings = [
        finding
        for finding in findings
        if finding.id == "SPACING-BUTTON-001"
    ]

    assert len(spacing_findings) == 1
    assert spacing_findings[0].severity == "minor"
    assert spacing_findings[0].relatedElements == [
        "item-1",
        "item-2",
        "item-3",
    ]


def test_only_the_inconsistent_column_is_included_in_the_finding():
    elements = [
        # Left column: inconsistent gaps (20px and 80px).
        make_element("left-1", 100, 0),
        make_element("left-2", 100, 40),
        make_element("left-3", 100, 140),

        # Right column: consistent gaps (80px and 80px).
        make_element("right-1", 700, 0),
        make_element("right-2", 700, 100),
        make_element("right-3", 700, 200),
    ]

    findings = run_spacing_rule(elements)

    spacing_findings = [
        finding
        for finding in findings
        if finding.id == "SPACING-BUTTON-001"
    ]

    assert len(spacing_findings) == 1
    assert set(spacing_findings[0].relatedElements) == {
        "left-1",
        "left-2",
        "left-3",
    }

def test_different_sections_are_not_compared():
    elements = [
        make_element("section-a-1", 100, 0),
        make_element("section-a-2", 100, 40),
        make_element("section-a-3", 100, 80),
        make_element("section-b-1", 100, 300),
        make_element("section-b-2", 100, 400),
        make_element("section-b-3", 100, 500),
    ]

    for element in elements[:3]:
        element.sectionId = "section-a"

    for element in elements[3:]:
        element.sectionId = "section-b"

    findings = run_spacing_rule(elements)

    assert not any(f.id == "SPACING-BUTTON-001" for f in findings)


def test_different_groups_are_not_compared():
    elements = [
        make_element("group-a-1", 100, 0),
        make_element("group-a-2", 100, 40),
        make_element("group-a-3", 100, 80),
        make_element("group-b-1", 100, 300),
        make_element("group-b-2", 100, 400),
        make_element("group-b-3", 100, 500),
    ]

    for element in elements[:3]:
        element.groupId = "group-a"

    for element in elements[3:]:
        element.groupId = "group-b"

    findings = run_spacing_rule(elements)

    assert not any(f.id == "SPACING-BUTTON-001" for f in findings)


def test_overlapping_elements_are_excluded_from_related_elements():
    elements = [
        make_element("item-1", 100, 0, height=40),
        make_element("item-2", 100, 30, height=40),
        make_element("item-3", 100, 80, height=20),
        make_element("item-4", 100, 200, height=20),
    ]

    findings = run_spacing_rule(elements)

    spacing_findings = [
        finding
        for finding in findings
        if finding.id == "SPACING-BUTTON-001"
    ]

    assert len(spacing_findings) == 1
    assert spacing_findings[0].relatedElements == [
        "item-2",
        "item-3",
        "item-4",
    ]