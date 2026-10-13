"""
Rule engine tests using synthetic ExtractionResult data - no Gemini
or network calls involved. This is the actual unit-testable boundary:
given known input, the rules must produce known, sensible output.
"""
from app.schemas.extraction import ExtractionResult, UIElement, BoundingBox, DominantColor, ImageMeta
from app.services.rule_engine import run_rule_engine
from app.services.scoring import calculate_scores


def make_element(id, type, x, y, w, h, font=None):
    return UIElement(
        id=id, type=type,
        boundingBox=BoundingBox(x=x, y=y, width=w, height=h),
        estimatedFontSize=font,
    )


def test_clean_design_has_no_findings_and_scores_100():
    clean = ExtractionResult(
        image=ImageMeta(width=1440, height=900),
        colors=[DominantColor(hex="#111111"), DominantColor(hex="#ffffff")],
        elements=[
            make_element("h1", "heading", 40, 40, 400, 40, font=32),
            make_element("b1", "body_text", 40, 100, 400, 20, font=16),
            make_element("btn1", "button", 40, 300, 140, 48),
            make_element("btn2", "button", 40, 370, 140, 48),
            make_element("btn3", "button", 40, 440, 140, 48),
        ],
    )
    findings = run_rule_engine(clean)
    _, overall = calculate_scores(findings)

    assert findings == []
    assert overall == 100


def test_too_many_colors_triggers_color_finding():
    result = ExtractionResult(
        image=ImageMeta(width=1000, height=800),
        colors=[DominantColor(hex=c) for c in
                ["#111", "#222", "#333", "#444", "#555", "#666"]],
        elements=[],
    )
    findings = run_rule_engine(result)
    assert any(f.category == "Color" for f in findings)


def test_small_text_triggers_major_typography_finding():
    result = ExtractionResult(
        image=ImageMeta(width=1000, height=800),
        colors=[],
        elements=[make_element("t1", "body_text", 0, 0, 100, 20, font=9)],
    )
    findings = run_rule_engine(result)
    small_text_findings = [f for f in findings if f.id == "TYPOGRAPHY-002"]
    assert len(small_text_findings) == 1
    assert small_text_findings[0].severity == "major"


def test_inconsistent_button_heights_triggers_consistency_finding():
    result = ExtractionResult(
        image=ImageMeta(width=1000, height=800),
        colors=[],
        elements=[
            make_element("btn1", "button", 0, 0, 140, 40),
            make_element("btn2", "button", 0, 60, 140, 70),
        ],
    )
    findings = run_rule_engine(result)
    assert any(f.id == "CONSISTENCY-BUTTON-HEIGHT" for f in findings)


def test_scoring_deducts_by_severity_and_stays_within_bounds():
    result = ExtractionResult(
        image=ImageMeta(width=1000, height=800),
        colors=[],
        elements=[make_element("t1", "body_text", 0, 0, 100, 20, font=5)],
    )
    findings = run_rule_engine(result)
    category_scores, overall = calculate_scores(findings)

    for score in category_scores:
        assert 0 <= score.score <= 100
    assert 0 <= overall <= 100


def test_extraction_tolerates_space_separated_type_and_zero_font_size():
    """
    Regression test for a real failure: Gemini returned "body text" (space)
    instead of "body_text", and 0 for estimatedFontSize on icons/containers
    instead of omitting the field. Both should be tolerated, not rejected.
    """
    from app.schemas.extraction import ExtractionResult as ER, UIElement, BoundingBox, ImageMeta as IM

    element = UIElement(
        id="element-2",
        type="body text",  # space, not underscore - as Gemini actually sent it
        boundingBox=BoundingBox(x=0, y=0, width=100, height=20),
        estimatedFontSize=0,  # Gemini's placeholder for "not applicable"
    )
    assert element.type == "body_text"
    assert element.estimatedFontSize is None

    # Should not raise when building the full result either.
    ER(image=IM(width=100, height=100), elements=[element], colors=[])


def test_extraction_maps_unlisted_type_synonyms_and_falls_back_to_other():
    """
    Regression test for a second real failure: Gemini used "text" (a
    different synonym than "body text") for the same concept. Also checks
    that a genuinely unrecognized type falls back to "other" instead of
    raising, so one odd label doesn't fail the whole analysis.
    """
    from app.schemas.extraction import UIElement, BoundingBox

    synonym_element = UIElement(
        id="e1", type="text",
        boundingBox=BoundingBox(x=0, y=0, width=10, height=10),
    )
    assert synonym_element.type == "body_text"

    unknown_element = UIElement(
        id="e2", type="sidebar-widget",
        boundingBox=BoundingBox(x=0, y=0, width=10, height=10),
    )
    assert unknown_element.type == "other"


def test_formatting_variants_of_a_known_type_all_normalize_identically():
    """
    Space vs underscore vs hyphen vs casing vs repeated whitespace are all
    just formatting differences for the same concept and must all collapse
    to the exact same canonical value - none of them should be treated as
    a different type, and none should raise.
    """
    from app.schemas.extraction import UIElement, BoundingBox

    formatting_variants = [
        "body text", "Body Text", "BODY TEXT", "body-text", "Body-Text",
        "body_text", "BODY_TEXT", "body   text", "  body text  ",
        "body - text",
    ]

    results = {
        variant: UIElement(
            id="e1", type=variant,
            boundingBox=BoundingBox(x=0, y=0, width=10, height=10),
        ).type
        for variant in formatting_variants
    }

    # Every variant must produce the exact same canonical value.
    assert set(results.values()) == {"body_text"}


def test_formatting_variants_of_an_unrelated_value_do_not_get_accepted():
    """
    Formatting normalization must not turn into "accept anything spelled
    consistently" - a genuinely unrelated value stays unrecognized (falls
    back to "other") regardless of how it's formatted, rather than being
    treated as a new valid type.
    """
    from app.schemas.extraction import UIElement, BoundingBox

    for variant in ["sidebar widget", "Sidebar Widget", "sidebar-widget", "SIDEBAR_WIDGET"]:
        el = UIElement(
            id="e1", type=variant,
            boundingBox=BoundingBox(x=0, y=0, width=10, height=10),
        )
        assert el.type == "other"


def test_type_formatting_variants_do_not_cause_a_502_end_to_end():
    """
    Full pipeline check (not just the schema unit): a raw Gemini-shaped
    response using a formatting variant of a known type must produce a
    normal 200 result through validate_extraction, identical to the
    canonical spelling - never a validation failure.
    """
    import json
    from app.services.validation import validate_extraction

    variant_payload = json.dumps({
        "image": {"width": 1000, "height": 800},
        "elements": [
            {"id": "e1", "type": "Body   Text",
             "boundingBox": {"x": 0, "y": 0, "width": 100, "height": 20}},
        ],
        "colors": [],
    })
    canonical_payload = json.dumps({
        "image": {"width": 1000, "height": 800},
        "elements": [
            {"id": "e1", "type": "body_text",
             "boundingBox": {"x": 0, "y": 0, "width": 100, "height": 20}},
        ],
        "colors": [],
    })

    variant_result = validate_extraction(variant_payload)
    canonical_result = validate_extraction(canonical_payload)

    assert variant_result.elements[0].type == "body_text"
    assert variant_result.model_dump() == canonical_result.model_dump()
