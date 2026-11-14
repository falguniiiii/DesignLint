
import json

from app.services.validation import validate_extraction


def make_payload(**overrides):
    payload = {
        "image": {"width": 1000, "height": 800},
        "elements": [],
        "colors": [],
        "sections": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


def make_box(x=10, y=10, width=100, height=50):
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }


def test_valid_section_is_preserved():
    result = validate_extraction(
        make_payload(
            sections=[
                {
                    "id": "hero-1",
                    "type": "hero",
                    "label": "Hero section",
                    "boundingBox": make_box(),
                }
            ]
        )
    )

    assert len(result.sections) == 1
    assert result.sections[0].id == "hero-1"
    assert result.sections[0].type == "hero"


def test_section_bounding_box_is_clipped():
    result = validate_extraction(
        make_payload(
            sections=[
                {
                    "id": "footer-1",
                    "type": "footer",
                    "boundingBox": make_box(950, 750, 100, 100),
                }
            ]
        )
    )

    bbox = result.sections[0].boundingBox

    assert bbox.x == 950
    assert bbox.y == 750
    assert bbox.width == 50
    assert bbox.height == 50


def test_invalid_section_is_dropped():
    result = validate_extraction(
        make_payload(
            sections=[
                {
                    "id": "invalid",
                    "type": "hero",
                    "boundingBox": make_box(10, 10, 0, 50),
                },
                {
                    "id": "valid",
                    "type": "footer",
                    "boundingBox": make_box(),
                },
            ]
        )
    )

    assert len(result.sections) == 1
    assert result.sections[0].id == "valid"


def test_duplicate_section_ids_keep_first_occurrence():
    result = validate_extraction(
        make_payload(
            sections=[
                {
                    "id": "section-1",
                    "type": "hero",
                    "boundingBox": make_box(),
                },
                {
                    "id": "section-1",
                    "type": "footer",
                    "boundingBox": make_box(10, 100, 200, 100),
                },
            ]
        )
    )

    assert len(result.sections) == 1
    assert result.sections[0].type == "hero"


def test_element_metadata_is_preserved():
    result = validate_extraction(
        make_payload(
            elements=[
                {
                    "id": "button-1",
                    "type": "button",
                    "role": "primary_action",
                    "sectionId": "hero-1",
                    "groupId": "button-group-1",
                    "boundingBox": make_box(),
                }
            ],
            sections=[
                {
                    "id": "hero-1",
                    "type": "hero",
                    "boundingBox": make_box(),
                }
            ],
        )
    )

    element = result.elements[0]

    assert element.role == "primary_action"
    assert element.sectionId == "hero-1"
    assert element.groupId == "button-group-1"


def test_nonexistent_section_reference_is_cleared():
    result = validate_extraction(
        make_payload(
            elements=[
                {
                    "id": "button-1",
                    "type": "button",
                    "sectionId": "missing-section",
                    "boundingBox": make_box(),
                }
            ]
        )
    )

    assert result.elements[0].sectionId is None


def test_invalid_section_reference_is_cleared():
    result = validate_extraction(
        make_payload(
            elements=[
                {
                    "id": "button-1",
                    "type": "button",
                    "sectionId": "section-1",
                    "boundingBox": make_box(),
                }
            ],
            sections=[
                {
                    "id": "section-1",
                    "type": "hero",
                    "boundingBox": make_box(1200, 900, 100, 100),
                }
            ],
        )
    )

    assert result.sections == []
    assert result.elements[0].sectionId is None


def test_group_id_without_group_registry_is_preserved():
    result = validate_extraction(
        make_payload(
            elements=[
                {
                    "id": "button-1",
                    "type": "button",
                    "groupId": "group-1",
                    "boundingBox": make_box(),
                }
            ]
        )
    )

    assert result.elements[0].groupId == "group-1"


def test_section_key_aliases_are_normalized():
    result = validate_extraction(
        make_payload(
            sections=[
                {
                    "sectionId": "hero-1",
                    "sectionType": "hero",
                    "box": make_box(),
                }
            ]
        )
    )

    assert result.sections[0].id == "hero-1"
    assert result.sections[0].type == "hero"
