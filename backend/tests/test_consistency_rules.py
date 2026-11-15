from app.schemas.extraction import (
    ExtractionResult,
    UIElement,
    BoundingBox,
    ImageMeta,
)
from app.rules.consistency_rules import run


def make_element(
    element_id,
    element_type,
    x=0,
    y=0,
    width=140,
    height=40,
    section_id=None,
    group_id=None,
):
    return UIElement(
        id=element_id,
        type=element_type,
        boundingBox=BoundingBox(
            x=x,
            y=y,
            width=width,
            height=height,
        ),
        sectionId=section_id,
        groupId=group_id,
    )


def run_consistency_rule(elements):
    extraction = ExtractionResult(
        image=ImageMeta(width=1440, height=900),
        colors=[],
        elements=elements,
    )
    return run(extraction)


def test_buttons_in_different_sections_are_not_compared():
    elements = [
        make_element("btn-a1", "button", height=40, section_id="hero"),
        make_element("btn-a2", "button", height=40, section_id="hero"),
        make_element("btn-b1", "button", height=80, section_id="footer"),
        make_element("btn-b2", "button", height=80, section_id="footer"),
    ]

    findings = run_consistency_rule(elements)

    assert not any(
        finding.id == "CONSISTENCY-BUTTON-HEIGHT"
        for finding in findings
    )


def test_buttons_in_different_groups_are_not_compared():
    elements = [
        make_element("btn-a1", "button", height=40, group_id="group-a"),
        make_element("btn-a2", "button", height=40, group_id="group-a"),
        make_element("btn-b1", "button", height=80, group_id="group-b"),
        make_element("btn-b2", "button", height=80, group_id="group-b"),
    ]

    findings = run_consistency_rule(elements)

    assert not any(
        finding.id == "CONSISTENCY-BUTTON-HEIGHT"
        for finding in findings
    )


def test_inconsistent_button_heights_within_same_group_are_flagged():
    elements = [
        make_element("btn-1", "button", height=40, group_id="actions"),
        make_element("btn-2", "button", height=70, group_id="actions"),
    ]

    findings = run_consistency_rule(elements)

    height_findings = [
        finding for finding in findings
        if finding.id == "CONSISTENCY-BUTTON-HEIGHT"
    ]

    assert len(height_findings) == 1
    assert set(height_findings[0].relatedElements) == {"btn-1", "btn-2"}


def test_buttons_without_metadata_preserve_legacy_behavior():
    elements = [
        make_element("btn-1", "button", height=40),
        make_element("btn-2", "button", height=70),
    ]

    findings = run_consistency_rule(elements)

    assert any(
        finding.id == "CONSISTENCY-BUTTON-HEIGHT"
        for finding in findings
    )


def test_inconsistent_card_heights_are_flagged():
    elements = [
        make_element("card-1", "card", width=200, height=150),
        make_element("card-2", "card", width=200, height=250),
    ]

    findings = run_consistency_rule(elements)

    assert any(
        finding.id == "CONSISTENCY-CARD-HEIGHT"
        for finding in findings
    )


def test_inconsistent_card_widths_are_flagged():
    elements = [
        make_element("card-1", "card", width=150, height=200),
        make_element("card-2", "card", width=250, height=200),
    ]

    findings = run_consistency_rule(elements)

    assert any(
        finding.id == "CONSISTENCY-CARD-WIDTH"
        for finding in findings
    )

def test_missing_metadata_does_not_bridge_different_sections():
    elements = [
        make_element("btn-hero", "button", height=40, section_id="hero"),
        make_element("btn-footer", "button", height=80, section_id="footer"),
        make_element("btn-unknown", "button", height=40),
    ]

    findings = run_consistency_rule(elements)

    assert not any(
        finding.id == "CONSISTENCY-BUTTON-HEIGHT"
        for finding in findings
    )
