"""
Tests for app/services/color_utils.py - the shared, deterministic WCAG
color math used by both the contrast rule and the palette generator.
Checked against known reference values, not just internal consistency.
"""
from app.services.color_utils import relative_luminance, contrast_ratio, hex_to_hls, hls_to_hex


def test_contrast_ratio_black_vs_white_is_the_wcag_maximum():
    assert round(contrast_ratio("#000000", "#ffffff"), 2) == 21.0


def test_contrast_ratio_identical_colors_is_one():
    assert contrast_ratio("#336699", "#336699") == 1.0


def test_contrast_ratio_is_symmetric():
    a, b = "#336699", "#ffcc00"
    assert contrast_ratio(a, b) == contrast_ratio(b, a)


def test_known_borderline_aa_gray_matches_reference_value():
    """
    #767676 on white is a commonly cited reference gray that sits right
    at the WCAG AA 4.5:1 threshold - a good sanity check that the formula
    itself (not just our thresholds) is implemented correctly.
    """
    ratio = contrast_ratio("#767676", "#ffffff")
    assert 4.4 < ratio < 4.6


def test_relative_luminance_of_black_and_white():
    assert relative_luminance("#000000") == 0.0
    assert round(relative_luminance("#ffffff"), 4) == 1.0


def test_hex_hls_roundtrip_preserves_color():
    original = "#6366f1"
    h, l, s = hex_to_hls(original)
    roundtripped = hls_to_hex(h, l, s)
    assert roundtripped == original
