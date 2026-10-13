"""
Tests for the sanitization pass in app/services/validation.py. This is
the layer that makes DesignLint resilient to Gemini's real-world
unpredictability: it should coerce what's fixable and drop only the
individual bad element/color, never fail the whole analysis over one
odd field - unless the payload is unrecoverable (unparseable JSON, or
not a usable structure at all).
"""
import json

from app.services.validation import validate_extraction, ExtractionValidationError


def _payload(elements=None, colors=None, image=None):
    return json.dumps({
        "image": image or {"width": 1000, "height": 800},
        "elements": elements or [],
        "colors": colors or [],
    })


def test_float_coordinates_are_rounded_not_rejected():
    result = validate_extraction(_payload(elements=[
        {"id": "e1", "type": "button",
         "boundingBox": {"x": 10.7, "y": 20.3, "width": 200.5, "height": 30.1}},
    ]))
    assert len(result.elements) == 1
    box = result.elements[0].boundingBox
    assert box.x == 11 and box.y == 20 and box.width == 200 and box.height == 30


def test_negative_coordinates_are_clamped_not_rejected():
    result = validate_extraction(_payload(elements=[
        {"id": "e1", "type": "card", "boundingBox": {"x": -5, "y": -10, "width": 300, "height": 200}},
    ]))
    assert result.elements[0].boundingBox.x == 0
    assert result.elements[0].boundingBox.y == 0


def test_zero_size_bounding_box_is_clamped_to_minimum():
    result = validate_extraction(_payload(elements=[
        {"id": "e1", "type": "icon", "boundingBox": {"x": 0, "y": 0, "width": 0, "height": 0}},
    ]))
    assert result.elements[0].boundingBox.width >= 1
    assert result.elements[0].boundingBox.height >= 1


def test_element_missing_bounding_box_is_dropped_not_fatal():
    result = validate_extraction(_payload(elements=[
        {"id": "good", "type": "button", "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10}},
        {"id": "bad", "type": "button"},  # no boundingBox at all
    ]))
    assert len(result.elements) == 1
    assert result.elements[0].id == "good"


def test_element_with_non_numeric_coordinates_is_dropped_not_fatal():
    result = validate_extraction(_payload(elements=[
        {"id": "good", "type": "button", "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10}},
        {"id": "bad", "type": "button", "boundingBox": {"x": "not a number", "y": 0, "width": 10, "height": 10}},
    ]))
    assert len(result.elements) == 1


def test_non_dict_element_in_list_is_dropped_not_fatal():
    result = validate_extraction(_payload(elements=[
        {"id": "good", "type": "button", "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10}},
        "this is not an element",
    ]))
    assert len(result.elements) == 1


def test_missing_element_id_gets_a_stable_fallback():
    result = validate_extraction(_payload(elements=[
        {"type": "button", "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10}},
    ]))
    assert result.elements[0].id  # non-empty, doesn't raise


def test_font_size_as_numeric_string_is_coerced():
    result = validate_extraction(_payload(elements=[
        {"id": "e1", "type": "body_text", "boundingBox": {"x": 0, "y": 0, "width": 10, "height": 10},
         "estimatedFontSize": "16"},
    ]))
    assert result.elements[0].estimatedFontSize == 16


def test_color_missing_hash_prefix_is_normalized():
    result = validate_extraction(_payload(colors=[{"hex": "abcdef"}]))
    assert result.colors[0].hex == "#abcdef"


def test_color_with_alpha_channel_is_truncated():
    result = validate_extraction(_payload(colors=[{"hex": "#12345678"}]))
    assert result.colors[0].hex == "#123456"


def test_non_hex_color_is_dropped_not_fatal():
    result = validate_extraction(_payload(colors=[
        {"hex": "#123456"},
        {"hex": "rgb(1,2,3)"},  # not a hex color at all
    ]))
    assert len(result.colors) == 1
    assert result.colors[0].hex == "#123456"


def test_fully_chaotic_payload_still_produces_a_usable_result():
    """
    A single payload with many different kinds of malformed data mixed
    with good data. The whole analysis should still succeed, salvaging
    what it can.
    """
    result = validate_extraction(_payload(
        elements=[
            {"id": "e1", "type": "button", "boundingBox": {"x": 10, "y": 10, "width": 100, "height": 40}},
            {"id": "e2", "type": "text", "boundingBox": {"x": 5, "y": 5, "width": 50, "height": 20}},
            {"id": "e3", "type": "totally-made-up-type", "boundingBox": {"x": 5, "y": 5, "width": 50, "height": 20}},
            {"id": "e4", "type": "button"},  # dropped: no boundingBox
            "not an element",  # dropped: not a dict
        ],
        colors=[
            {"hex": "#123456"},
            {"hex": "not-a-color"},  # dropped
        ],
    ))
    assert len(result.elements) == 3
    assert result.elements[1].type == "body_text"  # "text" synonym normalized
    assert result.elements[2].type == "other"  # unrecognized type falls back
    assert len(result.colors) == 1


def test_unparseable_json_still_raises_a_clear_error():
    """Genuinely unrecoverable input should still fail clearly, not silently succeed empty."""
    try:
        validate_extraction("this is not json at all {")
        assert False, "should have raised"
    except ExtractionValidationError:
        pass
