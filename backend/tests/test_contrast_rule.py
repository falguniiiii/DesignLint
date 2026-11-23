"""
Tests for app/rules/contrast_rules.py.

Contrast findings must be based on explicit, element-linked
foreground/background pairs.
"""

from app.schemas.extraction import (
    ContrastPair,
    ExtractionResult,
    ImageMeta,
    UIElement,
    BoundingBox,
    DominantColor,
)
from app.rules import contrast_rules


def _element(element_id="text-1", label="Sample text"):
    return UIElement(
        id=element_id,
        type="body_text",
        label=label,
        boundingBox=BoundingBox(
            x=0,
            y=0,
            width=100,
            height=20,
        ),
        estimatedFontSize=16,
        role="body_copy",
    )


def _pair(
    element_id="text-1",
    foreground="#B8B8B8",
    background="#FFFFFF",
):
    return ContrastPair(
        elementId=element_id,
        foregroundColor=foreground,
        backgroundColor=background,
    )


def _extraction(pairs=None, elements=None, colors=None):
    return ExtractionResult(
        image=ImageMeta(width=1000, height=800),
        elements=elements or [],
        colors=colors or [],
        contrastPairs=pairs or [],
    )


def test_sufficient_contrast_produces_no_finding():
    extraction = _extraction(
        pairs=[
            _pair(
                foreground="#111111",
                background="#FFFFFF",
            )
        ],
        elements=[_element()],
    )

    assert contrast_rules.run(extraction) == []


def test_insufficient_contrast_produces_a_finding():
    extraction = _extraction(
        pairs=[_pair()],
        elements=[_element()],
    )

    findings = contrast_rules.run(extraction)

    assert len(findings) == 1
    assert findings[0].category == "Color"
    assert findings[0].severity == "major"
    assert findings[0].relatedElements == ["text-1"]
    assert "B8B8B8" in findings[0].id


def test_severity_reflects_contrast_ratio():
    major_extraction = _extraction(
        pairs=[
            _pair(
                foreground="#B8B8B8",
                background="#FFFFFF",
            )
        ],
        elements=[_element()],
    )

    major_findings = contrast_rules.run(major_extraction)

    assert len(major_findings) == 1
    assert major_findings[0].severity == "major"

    minor_extraction = _extraction(
        pairs=[
            _pair(
                foreground="#777777",
                background="#FFFFFF",
            )
        ],
        elements=[_element()],
    )

    minor_findings = contrast_rules.run(minor_extraction)

    assert len(minor_findings) == 1
    assert minor_findings[0].severity == "minor"


def test_no_finding_without_explicit_contrast_pairs():
    extraction = _extraction(
        elements=[_element()],
        colors=[
            DominantColor(hex="#B8B8B8", role="text"),
            DominantColor(hex="#FFFFFF", role="background"),
        ],
    )

    assert contrast_rules.run(extraction) == []


def test_pair_without_matching_element_is_ignored():
    extraction = _extraction(
        pairs=[_pair(element_id="missing-element")],
        elements=[_element()],
    )

    assert contrast_rules.run(extraction) == []


def test_duplicate_contrast_pairs_produce_only_one_finding():
    extraction = _extraction(
        pairs=[
            _pair(),
            _pair(),
        ],
        elements=[_element()],
    )

    findings = contrast_rules.run(extraction)

    assert len(findings) == 1


def test_same_colors_on_different_elements_produce_separate_findings():
    extraction = _extraction(
        pairs=[
            _pair(element_id="text-1"),
            _pair(element_id="text-2"),
        ],
        elements=[
            _element("text-1", "First paragraph"),
            _element("text-2", "Second paragraph"),
        ],
    )

    findings = contrast_rules.run(extraction)

    assert len(findings) == 2
    assert findings[0].relatedElements == ["text-1"]
    assert findings[1].relatedElements == ["text-2"]


def test_identical_foreground_and_background_is_reported():
    extraction = _extraction(
        pairs=[
            _pair(
                foreground="#FFFFFF",
                background="#FFFFFF",
            )
        ],
        elements=[_element()],
    )

    findings = contrast_rules.run(extraction)

    assert len(findings) == 1
    assert findings[0].severity == "major"


def test_contrast_findings_are_deterministic():
    extraction = _extraction(
        pairs=[_pair()],
        elements=[_element()],
    )

    result_1 = contrast_rules.run(extraction)
    result_2 = contrast_rules.run(extraction)

    assert [
        finding.model_dump()
        for finding in result_1
    ] == [
        finding.model_dump()
        for finding in result_2
    ]
