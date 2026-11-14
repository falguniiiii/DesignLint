
import pytest
from pydantic import ValidationError

from app.schemas.extraction import ExtractionResult


def make_extraction(**overrides):
    payload = {
        "image": {"width": 1200, "height": 800},
        "elements": [],
        "colors": [],
    }
    payload.update(overrides)
    return ExtractionResult.model_validate(payload)


def test_old_extraction_payload_remains_valid():
    result = make_extraction()

    assert result.elements == []
    assert result.colors == []
    assert result.sections == []


def test_element_structural_metadata_is_optional():
    result = make_extraction(
        elements=[
            {
                "id": "button-1",
                "type": "button",
                "boundingBox": {
                    "x": 10,
                    "y": 20,
                    "width": 120,
                    "height": 40,
                },
            }
        ]
    )

    element = result.elements[0]

    assert element.role is None
    assert element.sectionId is None
    assert element.groupId is None


def test_element_role_is_normalized():
    result = make_extraction(
        elements=[
            {
                "id": "button-1",
                "type": "button",
                "role": "primary CTA",
                "boundingBox": {
                    "x": 10,
                    "y": 20,
                    "width": 120,
                    "height": 40,
                },
            }
        ]
    )

    assert result.elements[0].role == "primary_action"


def test_unknown_element_role_falls_back_to_other():
    result = make_extraction(
        elements=[
            {
                "id": "element-1",
                "type": "other",
                "role": "unrecognized-purpose",
                "boundingBox": {
                    "x": 10,
                    "y": 20,
                    "width": 100,
                    "height": 30,
                },
            }
        ]
    )

    assert result.elements[0].role == "other"


def test_section_type_is_normalized():
    result = make_extraction(
        sections=[
            {
                "id": "section-1",
                "type": "product listing",
                "boundingBox": {
                    "x": 0,
                    "y": 100,
                    "width": 1200,
                    "height": 500,
                },
            }
        ]
    )

    assert result.sections[0].type == "product_grid"


def test_unknown_section_type_falls_back_to_other():
    result = make_extraction(
        sections=[
            {
                "id": "section-1",
                "type": "unrecognized-region",
                "boundingBox": {
                    "x": 0,
                    "y": 100,
                    "width": 1200,
                    "height": 500,
                },
            }
        ]
    )

    assert result.sections[0].type == "other"


def test_invalid_bounding_box_is_rejected():
    with pytest.raises(ValidationError):
        make_extraction(
            sections=[
                {
                    "id": "section-1",
                    "type": "hero",
                    "boundingBox": {
                        "x": 0,
                        "y": 0,
                        "width": 0,
                        "height": 200,
                    },
                }
            ]
        )
