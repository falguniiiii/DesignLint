"""
Tests for the generic normalization layer (app/schemas/normalization.py)
and its use in validation.py. These specifically prove the mechanism
generalizes across DIFFERENT fields and object types - not just the
`type` value that originally exposed the problem - and that it never
blindly accepts genuinely unrelated names.
"""
import json

from app.schemas.normalization import normalize_token, flatten_key, remap_keys, resolve_alias
from app.services.validation import validate_extraction


def _payload(elements=None, colors=None, image=None):
    return json.dumps({
        "image": image or {"width": 1000, "height": 800},
        "elements": elements or [],
        "colors": colors or [],
    })


# --- Unit tests on the generic utilities themselves ---

def test_flatten_key_unifies_camel_snake_kebab_and_spaced_forms():
    variants = ["estimatedFontSize", "estimated_font_size", "estimated-font-size",
                "Estimated Font Size", "ESTIMATEDFONTSIZE"]
    flattened = {flatten_key(v) for v in variants}
    assert len(flattened) == 1


def test_resolve_alias_rejects_unrelated_values():
    aliases = {"text": "body_text"}
    valid = {"body_text", "button"}
    assert resolve_alias("text", aliases, valid, fallback="other") == "body_text"
    assert resolve_alias("some random thing", aliases, valid, fallback="other") == "other"


def test_remap_keys_only_renames_known_keys_leaves_others_untouched():
    result = remap_keys(
        {"font size": 16, "totally_unrelated_key": "x"},
        canonical_keys={"estimatedFontSize"},
        key_aliases={"fontsize": "estimatedFontSize"},
    )
    assert result["estimatedFontSize"] == 16
    assert result["totally_unrelated_key"] == "x"  # left alone, not renamed or dropped


# --- Integration tests: multiple different fields, multiple formatting styles ---

def test_font_size_key_variants_all_map_to_estimatedFontSize():
    for key_variant in ["font size", "Font Size", "font-size", "font_size", "FontSize"]:
        result = validate_extraction(_payload(elements=[
            {"id": "e1", "type": "body_text",
             "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10},
             key_variant: 18},
        ]))
        assert result.elements[0].estimatedFontSize == 18, f"failed for key {key_variant!r}"


def test_bounding_box_key_variants_all_map_correctly():
    for key_variant in ["bounding box", "Bounding Box", "bounding-box", "bounding_box", "bbox"]:
        result = validate_extraction(_payload(elements=[
            {"id": "e1", "type": "button", key_variant: {"x": 1, "y": 2, "width": 30, "height": 40}},
        ]))
        box = result.elements[0].boundingBox
        assert (box.x, box.y, box.width, box.height) == (1, 2, 30, 40), f"failed for key {key_variant!r}"


def test_color_hex_key_variants_all_map_correctly():
    for key_variant in ["hex", "Hex", "color", "Color", "colour", "COLOUR"]:
        result = validate_extraction(_payload(colors=[{key_variant: "#abcdef"}]))
        assert result.colors[0].hex == "#abcdef", f"failed for key {key_variant!r}"


def test_top_level_key_variants_all_map_correctly():
    for elements_key, colors_key in [("elements", "colors"), ("Elements", "Colours"),
                                      ("ELEMENTS", "colours")]:
        payload = json.dumps({
            "image": {"width": 1000, "height": 800},
            elements_key: [],
            colors_key: [{"hex": "#111111"}],
        })
        result = validate_extraction(payload)
        assert len(result.colors) == 1, f"failed for keys {elements_key!r}/{colors_key!r}"


def test_element_id_and_type_key_variants_map_correctly():
    result = validate_extraction(_payload(elements=[
        {"element id": "e1", "element type": "button",
         "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10}},
    ]))
    assert result.elements[0].id == "e1"
    assert result.elements[0].type == "button"


def test_bounding_box_short_key_aliases_w_and_h():
    result = validate_extraction(_payload(elements=[
        {"id": "e1", "type": "button", "boundingBox": {"x": 0, "y": 0, "w": 50, "h": 20}},
    ]))
    box = result.elements[0].boundingBox
    assert box.width == 50 and box.height == 20


# --- Rejection tests: genuinely unknown/unrelated names must NOT be accepted ---

def test_genuinely_unrelated_element_key_is_ignored_not_misassigned():
    """
    An unrecognized key should be left alone (and therefore never read),
    not guessed at or merged into a real field.
    """
    result = validate_extraction(_payload(elements=[
        {"id": "e1", "type": "button",
         "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10},
         "someRandomUnrelatedField": "should not affect anything"},
    ]))
    assert len(result.elements) == 1
    assert result.elements[0].id == "e1"
    assert result.elements[0].type == "button"


def test_genuinely_unrelated_type_value_still_falls_back_to_other_regardless_of_formatting():
    for variant in ["sidebar widget", "Sidebar Widget", "SIDEBAR-WIDGET", "sidebar_widget"]:
        result = validate_extraction(_payload(elements=[
            {"id": "e1", "type": variant, "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10}},
        ]))
        assert result.elements[0].type == "other", f"should not be accepted: {variant!r}"


def test_natural_language_label_is_never_touched_by_normalization():
    """
    Normalization must only apply to structured field names/values, never
    to free-text content like labels - a label happening to contain
    formatting-like characters should pass through completely unchanged.
    """
    label_text = "Sign-Up / Log In  (Free Trial!)"
    result = validate_extraction(_payload(elements=[
        {"id": "e1", "type": "button",
         "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10},
         "label": label_text},
    ]))
    assert result.elements[0].label == label_text
