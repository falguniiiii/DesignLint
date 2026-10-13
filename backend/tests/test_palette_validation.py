"""Whole-palette tests: Text/Background contrast and derived-role handling."""
import pytest

from app.schemas.extraction import DominantColor
from app.services.color_utils import contrast_ratio
from app.services.recommendations import _derive_palette

AA = 4.5


def _p(hexes, roles=None):
    """roles: optional {hex: role}; Gemini's role labels drive light/dark detection."""
    roles = roles or {}
    palette = _derive_palette([DominantColor(hex=h, role=roles.get(h)) for h in hexes])
    return palette, ({s.role: s for s in palette} if palette else {})


def _assert_readable(by_role):
    bg = by_role["Background"].hex
    assert contrast_ratio(by_role["Text"].hex, bg) >= AA
    if "Secondary text" in by_role:
        assert contrast_ratio(by_role["Secondary text"].hex, bg) >= AA
    if "Surface" in by_role:
        assert contrast_ratio(by_role["Text"].hex, by_role["Surface"].hex) >= AA


LIGHT_NEUTRALS = ["#F2F2F2", "#F5F5F5", "#FAFAFA", "#FFFFFF"]
DARK_NEUTRALS = ["#0A0A0A", "#0F0F0F", "#141414", "#1A1A1A"]


def test_light_ui_with_insufficient_darkest_color_gets_readable_text():
    _, r = _p(LIGHT_NEUTRALS + ["#3B82F6"])
    assert r["Background"].hex.lower() == "#ffffff"
    assert r["Text"].hex.lower() != "#f2f2f2"
    assert r["Text"].hex.lower() != "#3b82f6"  # accent never becomes body text
    assert "derived" in r["Text"].usage.lower()
    _assert_readable(r)


def test_dark_ui_with_insufficient_lightest_color_gets_readable_text():
    _, r = _p(DARK_NEUTRALS + ["#3B82F6"])
    assert r["Text"].hex.lower() != "#1a1a1a"
    assert r["Text"].hex.lower() != "#3b82f6"
    _assert_readable(r)


def test_normal_light_ui_keeps_detected_text_color():
    _, r = _p(["#111111", "#666666", "#FFFFFF", "#2563EB"], {"#FFFFFF": "background"})
    assert r["Text"].hex.lower() == "#111111"
    assert "detected" in r["Text"].usage.lower() and "derived" not in r["Text"].usage.lower()
    _assert_readable(r)


def test_normal_dark_ui_keeps_detected_text_color():
    _, r = _p(["#0B0B0F", "#E5E7EB", "#6B7280", "#2563EB"])
    assert r["Background"].hex.lower() == "#0b0b0f"
    assert r["Text"].hex.lower() == "#e5e7eb"
    _assert_readable(r)


@pytest.mark.parametrize("hexes", [
    LIGHT_NEUTRALS,
    DARK_NEUTRALS,
    ["#FFFFFF", "#FEFEFE", "#FDFDFD"],          # very light
    ["#000000", "#010101", "#020202"],          # very dark
    ["#F2F2F2", "#FFFFFF"],
    ["#0A0A0A", "#1A1A1A"],
    ["#FFFFFF", "#3B82F6"],                     # only a background + accent
    ["#0A0A0A", "#3B82F6"],
    ["#111111", "#777777", "#EEEEEE", "#FFFFFF"],  # neutral-only, mixed
])
def test_text_background_contrast_always_passes_aa(hexes):
    palette, r = _p(hexes)
    assert palette is not None
    _assert_readable(r)


def test_neutral_only_has_no_primary_and_is_readable():
    _, r = _p(LIGHT_NEUTRALS)
    assert "Primary" not in r
    _assert_readable(r)


def test_insufficient_colors_returns_none():
    assert _derive_palette([DominantColor(hex="#FFFFFF")]) is None
    assert _derive_palette([]) is None


def test_multiple_accents_pick_one_primary_and_keep_text_neutral():
    _, r = _p(["#FFFFFF", "#111111", "#3B82F6", "#EF4444", "#10B981"], {"#FFFFFF": "background"})
    assert r["Primary"].hex.lower() in {"#3b82f6", "#ef4444", "#10b981"}
    assert r["Text"].hex.lower() == "#111111"
    _assert_readable(r)


def test_real_accent_plus_neutrals_uses_accent_as_primary_only():
    _, r = _p(["#FFFFFF", "#F5F5F5", "#222222", "#3B82F6"])
    assert r["Primary"].hex.lower() == "#3b82f6"
    assert r["Text"].hex.lower() == "#222222"


def test_palette_is_deterministic():
    hexes = LIGHT_NEUTRALS + ["#3B82F6"]
    assert _derive_palette([DominantColor(hex=h) for h in hexes]) == _derive_palette([DominantColor(hex=h) for h in hexes])


def test_no_hardcoded_primary_fallback():
    for hexes in (LIGHT_NEUTRALS, DARK_NEUTRALS, ["#FFFFFF", "#000000"]):
        _, r = _p(hexes)
        assert "Primary" not in r
        assert all(s.hex.lower() != "#6366f1" for s in r.values())


def test_every_palette_color_is_extracted_or_marked_derived():
    extracted = {h.lower() for h in LIGHT_NEUTRALS + ["#3B82F6"]}
    _, r = _p(LIGHT_NEUTRALS + ["#3B82F6"])
    for s in r.values():
        assert s.hex.lower() in extracted or "derived" in s.usage.lower()


def test_light_surface_is_derived_from_background_not_hardcoded_white():
    _, r = _p(["#E8E0D0", "#222222"], {"#E8E0D0": "background"})  # warm beige page
    assert r["Surface"].hex.lower() != "#ffffff" or r["Background"].hex.lower() == "#ffffff"
    assert "derived" in r["Surface"].usage.lower()


def test_role_labeled_background_is_never_promoted_to_primary():
    _, r = _p(["#E8E0D0", "#222222"], {"#E8E0D0": "background"})
    assert "Primary" not in r
    assert r["Background"].hex.lower() == "#e8e0d0"


# --- Explicit role labels ---------------------------------------------------

def _roles(pairs):
    palette = _derive_palette([DominantColor(hex=h, role=r) for h, r in pairs])
    return {s.role: s for s in palette}


def test_explicit_roles_are_honored_over_lightness_extremes():
    r = _roles([("#E8E0D0", "background"), ("#222222", "text"), ("#FFFFFF", "surface"), ("#EA580C", "primary")])
    assert r["Background"].hex.lower() == "#e8e0d0"   # not the lightest (#FFFFFF)
    assert r["Text"].hex.lower() == "#222222"
    assert r["Surface"].hex.lower() == "#ffffff"
    assert r["Primary"].hex.lower() == "#ea580c"
    assert "derived" not in r["Background"].usage.lower()
    assert "derived" not in r["Text"].usage.lower()
    assert "derived" not in r["Surface"].usage.lower()
    _assert_readable(r)


def test_explicit_text_that_is_not_the_darkest_color_is_kept():
    r = _roles([("#FFFFFF", "background"), ("#333333", "text"), ("#000000", None), ("#2563EB", None)])
    assert r["Text"].hex.lower() == "#333333"      # #000000 is darker but unlabeled
    assert r["Background"].hex.lower() == "#ffffff"


def test_explicit_dark_background_that_is_not_the_darkest_color():
    r = _roles([("#1E1E2E", "background"), ("#000000", None), ("#E5E7EB", "text")])
    assert r["Background"].hex.lower() == "#1e1e2e"
    assert r["Text"].hex.lower() == "#e5e7eb"


def test_explicit_primary_is_used_even_if_not_the_most_saturated():
    r = _roles([("#FFFFFF", "background"), ("#111111", "text"), ("#6B7FD7", "primary"), ("#FF0000", None)])
    assert r["Primary"].hex.lower() == "#6b7fd7"


def test_explicit_roles_with_insufficient_contrast_derive_readable_text():
    r = _roles([("#FFFFFF", "background"), ("#E0E0E0", "text"), ("#2563EB", "primary")])
    assert r["Background"].hex.lower() == "#ffffff"
    assert r["Text"].hex.lower() != "#e0e0e0"
    assert contrast_ratio(r["Text"].hex, r["Background"].hex) >= AA
    assert "derived" in r["Text"].usage.lower()
    assert "#e0e0e0" in r["Text"].usage.lower()


def test_explicit_surface_that_hurts_text_contrast_is_replaced_by_derived_surface():
    r = _roles([("#FFFFFF", "background"), ("#767676", "text"), ("#B0B0B0", "surface")])
    assert r["Surface"].hex.lower() != "#b0b0b0"
    assert "derived" in r["Surface"].usage.lower()
    _assert_readable(r)


def test_duplicated_background_labels_on_different_colors_are_ignored():
    r = _roles([("#FFFFFF", "background"), ("#F5F5F5", "background"), ("#111111", None)])
    assert r["Background"].hex.lower() == "#ffffff"   # falls back to lightest
    _assert_readable(r)


def test_one_color_with_conflicting_roles_is_not_trusted():
    # #E8E0D0 labeled both background and text -> neither label is used,
    # so the normal light-mode fallback decides.
    r = _roles([("#E8E0D0", "background"), ("#E8E0D0", "text"), ("#FFFFFF", None), ("#222222", None)])
    assert r["Background"].hex.lower() == "#ffffff"
    assert r["Text"].hex.lower() == "#222222"
    _assert_readable(r)


def test_same_label_repeated_on_the_same_color_is_still_reliable():
    r = _roles([("#E8E0D0", "background"), ("#E8E0D0", "Background"), ("#222222", "text")])
    assert r["Background"].hex.lower() == "#e8e0d0"


def test_unrecognized_labels_fall_back_to_heuristics():
    r = _roles([("#FFFFFF", "banner"), ("#111111", "logo")])
    assert r["Background"].hex.lower() == "#ffffff"
    assert r["Text"].hex.lower() == "#111111"


def test_secondary_text_and_border_labels_are_used_when_valid():
    r = _roles([("#FFFFFF", "background"), ("#111111", "text"), ("#555555", "secondary text"), ("#DDDDDD", "border")])
    assert r["Secondary text"].hex.lower() == "#555555"
    assert r["Border"].hex.lower() == "#dddddd"


def test_labeled_palette_is_deterministic():
    pairs = [("#E8E0D0", "background"), ("#222222", "text"), ("#FFFFFF", "surface"), ("#EA580C", "primary")]
    assert _roles(pairs) == _roles(pairs)


def test_no_labels_still_uses_light_dark_fallback_and_neutral_only_rules():
    _, light = _p(["#111111", "#FFFFFF", "#2563EB"])
    assert light["Background"].hex.lower() == "#ffffff" or light["Background"].hex.lower() == "#111111"
    _, dark = _p(DARK_NEUTRALS)
    assert contrast_ratio(dark["Text"].hex, dark["Background"].hex) >= AA
    assert "Primary" not in dark
    assert _derive_palette([DominantColor(hex="#FFFFFF", role="background")]) is None
