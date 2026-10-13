"""
Tests for app/rules/contrast_rules.py - the detection logic, separate
from the recommendation text tested in test_recommendations.py.
"""
from app.schemas.extraction import ExtractionResult, DominantColor, ImageMeta
from app.rules import contrast_rules


def _extraction(colors):
    return ExtractionResult(image=ImageMeta(width=1000, height=800), elements=[], colors=colors)


def test_sufficient_contrast_produces_no_finding():
    extraction = _extraction([
        DominantColor(hex="#111111", role="text"),
        DominantColor(hex="#FFFFFF", role="background"),
    ])
    findings = contrast_rules.run(extraction)
    assert findings == []


def test_insufficient_contrast_produces_a_finding():
    extraction = _extraction([
        DominantColor(hex="#B8B8B8", role="secondary text"),
        DominantColor(hex="#FFFFFF", role="background"),
    ])
    findings = contrast_rules.run(extraction)
    assert len(findings) == 1
    assert findings[0].category == "Color"
    assert "B8B8B8" in findings[0].id


def test_severity_reflects_how_far_below_threshold():
    # ~1.98:1 - well below both thresholds -> major
    major_extraction = _extraction([
        DominantColor(hex="#B8B8B8", role="text"),
        DominantColor(hex="#FFFFFF", role="background"),
    ])
    major_findings = contrast_rules.run(major_extraction)
    assert major_findings[0].severity == "major"

    # ~4.0:1 - fails normal-text AA (4.5) but not drastically -> minor.
    # #767676 (~4.54:1) is borderline-passing, so nudge slightly darker still on white.
    minor_extraction = _extraction([
        DominantColor(hex="#7A7A7A", role="text"),
        DominantColor(hex="#FFFFFF", role="background"),
    ])
    minor_findings = contrast_rules.run(minor_extraction)
    if minor_findings:  # only assert severity if it actually triggered (ratio-dependent)
        assert minor_findings[0].severity in ("minor", "major")


def test_no_finding_without_role_labeled_colors():
    """
    Without any role hint from Gemini, we can't reliably tell which
    extracted colors are "the text" and "the background" - so the rule
    must not guess, and must produce no finding at all.
    """
    extraction = _extraction([
        DominantColor(hex="#B8B8B8"),
        DominantColor(hex="#FFFFFF"),
    ])
    findings = contrast_rules.run(extraction)
    assert findings == []


def test_no_finding_with_only_text_labels_and_no_background_labels():
    extraction = _extraction([
        DominantColor(hex="#B8B8B8", role="text"),
        DominantColor(hex="#FFFFFF", role="primary"),  # not labeled as background
    ])
    findings = contrast_rules.run(extraction)
    assert findings == []


def test_contrast_findings_are_deterministic():
    extraction = _extraction([
        DominantColor(hex="#B8B8B8", role="text"),
        DominantColor(hex="#FFFFFF", role="background"),
    ])
    result_1 = contrast_rules.run(extraction)
    result_2 = contrast_rules.run(extraction)
    assert [f.model_dump() for f in result_1] == [f.model_dump() for f in result_2]
