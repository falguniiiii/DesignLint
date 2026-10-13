"""
Tests for the recommendation layer (app/services/recommendations.py).

These prove: every rule ID gets a structured, non-vague recommendation;
color suggestions are derived deterministically from actual extracted
colors (never random); palette role assignment adapts to light vs dark
UIs instead of always assuming light mode; and running the same input
twice always produces the exact same output.
"""
from app.schemas.extraction import ExtractionResult, UIElement, BoundingBox, DominantColor, ImageMeta
from app.schemas.findings import RawFinding, Recommendation
from app.services.recommendations import enrich_findings, _derive_palette


def _el(id, type, x, y, w, h, font=None):
    return UIElement(id=id, type=type, boundingBox=BoundingBox(x=x, y=y, width=w, height=h), estimatedFontSize=font)


def _extraction(elements=None, colors=None):
    return ExtractionResult(
        image=ImageMeta(width=1440, height=900),
        elements=elements or [],
        colors=colors or [],
    )


def _raw(id, category, relatedElements=None):
    return RawFinding(
        id=id, category=category, severity="minor", title="t", description="d",
        confidence=0.5, relatedElements=relatedElements or [],
    )


# --- Structure: every finding gets a real Recommendation, not a placeholder ---

def test_every_current_rule_id_gets_a_structured_non_empty_recommendation():
    extraction = _extraction(
        elements=[
            _el("h1", "heading", 0, 0, 100, 20, font=14),
            _el("b1", "body_text", 0, 30, 100, 20, font=16),
            _el("b2", "body_text", 0, 60, 100, 20, font=9),
            _el("btn1", "button", 0, 200, 140, 40),
            _el("btn2", "button", 0, 260, 140, 70),
        ],
        colors=[DominantColor(hex=c) for c in ["#111", "#222", "#333", "#444", "#555", "#666"]],
    )
    raw_findings = [
        _raw("COLOR-001", "Color"),
        _raw("CONTRAST-B8B8B8-FFFFFF", "Color"),
        _raw("TYPOGRAPHY-002", "Typography", relatedElements=["b2"]),
        _raw("TYPOGRAPHY-003", "Typography", relatedElements=["h1", "b1"]),
        _raw("CONSISTENCY-BUTTON-HEIGHT", "Consistency", relatedElements=["btn1", "btn2"]),
    ]
    enriched = enrich_findings(raw_findings, extraction)

    assert len(enriched) == len(raw_findings)
    for finding in enriched:
        rec = finding.recommendation
        assert isinstance(rec, Recommendation)
        assert len(rec.whyItMatters) > 15   # not a placeholder/empty string
        assert len(rec.fix) > 10
        assert "consider improving" not in rec.fix.lower()  # the exact vague phrasing the user asked to avoid


def test_recommendation_never_uses_banned_vague_phrasing():
    """The request specifically called out this phrase as an example of what NOT to produce."""
    extraction = _extraction(elements=[_el("h1", "heading", 0, 0, 100, 20, font=10)])
    finding = _raw("TYPOGRAPHY-002", "Typography", relatedElements=["h1"])
    enriched = enrich_findings([finding], extraction)
    text = (enriched[0].recommendation.fix + enriched[0].recommendation.whyItMatters).lower()
    assert "consider improving visual hierarchy" not in text


# --- Suggested values are concrete, not generic ---

def test_small_text_recommendation_names_the_actual_smallest_size():
    extraction = _extraction(elements=[
        _el("t1", "body_text", 0, 0, 50, 20, font=9),
        _el("t2", "body_text", 0, 30, 50, 20, font=11),
    ])
    finding = _raw("TYPOGRAPHY-002", "Typography", relatedElements=["t1", "t2"])
    enriched = enrich_findings([finding], extraction)
    suggested = enriched[0].recommendation.suggestedValue
    assert "9px" in suggested  # the actual smallest observed size, not a vague instruction
    assert "14px" in suggested or "16px" in suggested  # a concrete target


def test_consistency_recommendation_names_actual_average_and_range():
    extraction = _extraction(elements=[
        _el("btn1", "button", 0, 0, 140, 40),
        _el("btn2", "button", 0, 60, 140, 60),
    ])
    finding = _raw("CONSISTENCY-BUTTON-HEIGHT", "Consistency", relatedElements=["btn1", "btn2"])
    enriched = enrich_findings([finding], extraction)
    suggested = enriched[0].recommendation.suggestedValue
    assert "50px" in suggested  # average of 40 and 60
    assert "40px" in suggested and "60px" in suggested  # the observed range


def test_spacing_recommendation_suggests_a_value_from_the_standard_scale():
    extraction = _extraction(elements=[
        _el("c1", "card", 0, 0, 100, 50),
        _el("c2", "card", 0, 66, 100, 50),   # gap = 16
        _el("c3", "card", 0, 180, 100, 50),  # gap = 64
    ])
    finding = _raw("SPACING-CARD-001", "Spacing", relatedElements=["c1", "c2", "c3"])
    enriched = enrich_findings([finding], extraction)
    suggested = enriched[0].recommendation.suggestedValue
    from app.services.recommendations import SPACING_SCALE
    assert any(str(v) in suggested for v in SPACING_SCALE)


# --- Color palette: deterministic, grounded in extracted colors, never random ---

def test_palette_derivation_is_deterministic_across_repeated_calls():
    colors = [DominantColor(hex=c) for c in ["#0B0B0D", "#F8F8FA", "#6366F1", "#EF4444"]]
    palette_1 = _derive_palette(colors)
    palette_2 = _derive_palette(colors)
    assert [c.hex for c in palette_1] == [c.hex for c in palette_2]


def test_light_ui_palette_uses_lightest_as_background_darkest_as_text():
    colors = [
        DominantColor(hex="#000000", role="text"),
        DominantColor(hex="#FFFFFF", role="background"),
        DominantColor(hex="#6366F1", role="primary"),
    ]
    palette = _derive_palette(colors)
    background = next(c for c in palette if c.role == "Background")
    text = next(c for c in palette if c.role == "Text")
    surface = next(c for c in palette if c.role == "Surface")
    assert background.hex == "#ffffff"
    assert text.hex == "#000000"
    assert surface.hex.lower() == "#ffffff"  # light-mode surface stays a fixed white


def test_dark_ui_palette_does_not_invert_into_a_light_theme():
    """
    Regression test for the exact bug reported: a dark UI (dark
    role-labeled background) must NOT get Background/Surface assigned to
    white just because white happens to be the lightest extracted color.
    """
    colors = [
        DominantColor(hex="#0B0B0D", role="background"),
        DominantColor(hex="#F5F5F7", role="text"),
        DominantColor(hex="#6EE7B7", role="accent"),
    ]
    palette = _derive_palette(colors)
    background = next(c for c in palette if c.role == "Background")
    text = next(c for c in palette if c.role == "Text")
    surface = next(c for c in palette if c.role == "Surface")

    assert background.hex == "#0b0b0d"   # the actual dark background, not white
    assert text.hex == "#f5f5f7"         # the actual light text color
    assert surface.hex != "#ffffff"      # must NOT turn into a white card on a dark page

    # Surface should be a lighter dark tone than the background (a raised
    # card), not darker and not full white.
    from app.services.color_utils import relative_luminance
    assert relative_luminance(surface.hex) > relative_luminance(background.hex)
    assert relative_luminance(surface.hex) < 0.5


def test_dark_ui_detected_via_average_luminance_when_no_roles_given():
    """Falls back to average luminance across all extracted colors when nothing is role-labeled."""
    colors = [DominantColor(hex=c) for c in ["#0A0A0C", "#111114", "#18181B", "#E4E4E7"]]
    palette = _derive_palette(colors)
    background = next(c for c in palette if c.role == "Background")
    # The darkest of these four should become the background in a dark UI.
    assert background.hex == "#0a0a0c"


def test_palette_has_six_roles_with_usage_explanations():
    colors = [DominantColor(hex=c) for c in ["#111111", "#EEEEEE", "#3B82F6", "#F87171"]]
    palette = _derive_palette(colors)
    roles = {c.role for c in palette}
    assert roles == {"Primary", "Background", "Surface", "Text", "Secondary text", "Border"}
    for suggestion in palette:
        assert len(suggestion.usage) > 5  # every suggestion explains where to use it


def test_insufficient_color_data_returns_none_not_an_invented_palette():
    palette = _derive_palette([DominantColor(hex="#123456")])  # only 1 color - not enough to derive from
    assert palette is None


def test_insufficient_color_data_recommendation_says_so_explicitly():
    extraction = _extraction(colors=[DominantColor(hex="#123456")])
    finding = _raw("COLOR-001", "Color")
    enriched = enrich_findings([finding], extraction)
    rec = enriched[0].recommendation
    assert rec.palette is None
    assert "not enough" in rec.suggestedValue.lower()


def test_color_finding_recommendation_includes_a_palette():
    # Includes a genuine accent color (#3B82F6) so this specifically tests
    # "a full 6-role palette is generated when an accent is present" -
    # the neutral-only case (no accent) is its own dedicated test below.
    extraction = _extraction(colors=[
        DominantColor(hex=c) for c in ["#111111", "#222222", "#3B82F6", "#444444", "#555555", "#EEEEEE"]
    ])
    finding = _raw("COLOR-001", "Color")
    enriched = enrich_findings([finding], extraction)
    rec = enriched[0].recommendation
    assert rec.palette is not None
    assert len(rec.palette) == 6
    assert any(c.role == "Primary" for c in rec.palette)


def test_neutral_only_colors_do_not_invent_a_primary_accent():
    """
    Regression test for the exact bug reported: when every extracted
    color is a pure neutral (gray/near-white/near-black, saturation ~0),
    DesignLint must NOT invent a hardcoded accent color like #6366F1.
    The other five roles are still legitimately derivable and should
    still be present - only Primary, which has no grounded candidate,
    is omitted.
    """
    extraction = _extraction(colors=[
        DominantColor(hex=c) for c in
        ["#111111", "#333333", "#777777", "#CCCCCC", "#EEEEEE", "#FFFFFF"]
    ])
    finding = _raw("COLOR-001", "Color")
    enriched = enrich_findings([finding], extraction)
    rec = enriched[0].recommendation

    assert rec.palette is not None  # other 5 roles are still grounded, so still useful
    roles = {c.role for c in rec.palette}
    assert roles == {"Background", "Surface", "Text", "Secondary text", "Border"}
    assert "Primary" not in roles
    assert not any(c.hex.lower() == "#6366f1" for c in rec.palette)


def test_derive_palette_directly_omits_primary_for_pure_grays():
    """Unit-level check on _derive_palette itself, not just the full recommendation."""
    from app.services.recommendations import _derive_palette

    colors = [DominantColor(hex=c) for c in
              ["#101010", "#404040", "#808080", "#B0B0B0", "#E0E0E0"]]
    palette = _derive_palette(colors)
    assert palette is not None
    assert all(c.role != "Primary" for c in palette)
    assert not any(c.hex.lower() == "#6366f1" for c in palette)


def test_palette_still_finds_a_genuine_accent_among_mostly_neutral_colors():
    """Sanity check that the fix didn't become overly conservative - a real accent is still found."""
    from app.services.recommendations import _derive_palette

    colors = [DominantColor(hex=c) for c in
              ["#111111", "#222222", "#444444", "#EEEEEE", "#3B82F6"]]
    palette = _derive_palette(colors)
    primary = next((c for c in palette if c.role == "Primary"), None)
    assert primary is not None
    assert primary.hex.lower() == "#3b82f6"


def test_color_recommendation_does_not_overclaim_the_best_palette():
    extraction = _extraction(colors=[
        DominantColor(hex=c) for c in ["#111", "#222", "#333", "#444", "#555", "#666"]
    ])
    finding = _raw("COLOR-001", "Color")
    enriched = enrich_findings([finding], extraction)
    suggested = enriched[0].recommendation.suggestedValue.lower()
    assert "suggested palette" in suggested
    assert "not the single objectively best" in suggested or "starting point" in suggested


def test_non_color_finding_has_no_palette():
    extraction = _extraction(elements=[_el("h1", "heading", 0, 0, 100, 20, font=10)])
    finding = _raw("TYPOGRAPHY-002", "Typography", relatedElements=["h1"])
    enriched = enrich_findings([finding], extraction)
    assert enriched[0].recommendation.palette is None


# --- Contrast recommendations ---

def test_contrast_recommendation_suggests_a_more_accessible_color_and_states_new_ratio():
    finding = _raw("CONTRAST-B8B8B8-FFFFFF", "Color")
    enriched = enrich_findings([finding], _extraction())
    suggested = enriched[0].recommendation.suggestedValue
    assert "#b8b8b8" in suggested.lower()
    assert ":1" in suggested  # states the new contrast ratio achieved


def test_contrast_recommendation_suggested_color_actually_passes_wcag_aa():
    from app.services.color_utils import contrast_ratio
    from app.services.recommendations import _find_accessible_text_color

    suggested_hex = _find_accessible_text_color("#B8B8B8", "#FFFFFF")
    assert contrast_ratio(suggested_hex, "#FFFFFF") >= 4.5


def test_contrast_suggestion_is_deterministic():
    from app.services.recommendations import _find_accessible_text_color
    assert _find_accessible_text_color("#B8B8B8", "#FFFFFF") == _find_accessible_text_color("#B8B8B8", "#FFFFFF")


# --- Full determinism check: same input -> byte-identical output ---

def test_enrich_findings_is_fully_deterministic():
    extraction = _extraction(
        elements=[_el("btn1", "button", 0, 0, 140, 40), _el("btn2", "button", 0, 60, 140, 70)],
        colors=[DominantColor(hex=c) for c in ["#111", "#222", "#333", "#444", "#555", "#666"]],
    )
    raw = [_raw("CONSISTENCY-BUTTON-HEIGHT", "Consistency", relatedElements=["btn1", "btn2"]),
           _raw("COLOR-001", "Color")]

    result_1 = enrich_findings(raw, extraction)
    result_2 = enrich_findings(raw, extraction)

    assert [f.model_dump() for f in result_1] == [f.model_dump() for f in result_2]
