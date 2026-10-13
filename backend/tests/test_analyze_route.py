"""
Integration test for the full /api/analyze route: upload validation ->
(mocked) Gemini call -> extraction validation -> rule engine -> scoring.
Gemini itself is mocked here since we don't want tests hitting a real
API or requiring a key to run in CI.
"""
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.extraction import ExtractionResult, UIElement, BoundingBox, ImageMeta

client = TestClient(app)

# Minimal valid PNG signature + padding: enough for the route's file-signature check
# (Gemini itself is mocked in these tests, so the image never has to decode).
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _fake_gemini_response() -> str:
    extraction = ExtractionResult(
        image=ImageMeta(width=1440, height=900),
        colors=[],
        elements=[
            UIElement(id="btn1", type="button", boundingBox=BoundingBox(x=0, y=0, width=140, height=40)),
            UIElement(id="btn2", type="button", boundingBox=BoundingBox(x=0, y=60, width=140, height=70)),
        ],
    )
    return extraction.model_dump_json()


def test_analyze_rejects_non_image_file():
    response = client.post(
        "/api/analyze",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_analyze_rejects_empty_file():
    response = client.post(
        "/api/analyze",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400


@patch("app.routes.analyze.extract_visual_structure")
def test_analyze_returns_audit_with_findings_and_scores(mock_extract):
    mock_extract.return_value = _fake_gemini_response()

    response = client.post(
        "/api/analyze",
        files={"file": ("screenshot.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 200
    body = response.json()

    assert "overallScore" in body
    assert 0 <= body["overallScore"] <= 100
    assert len(body["categoryScores"]) == 4
    assert body["elementCount"] == 2
    # Two buttons with heights 40 and 70 should trigger a consistency finding
    assert any(f["id"] == "CONSISTENCY-BUTTON-HEIGHT" for f in body["findings"])


@patch("app.routes.analyze.extract_visual_structure")
def test_analyze_returns_502_on_malformed_gemini_response(mock_extract):
    mock_extract.return_value = "this is not valid json"

    response = client.post(
        "/api/analyze",
        files={"file": ("screenshot.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 502


def test_analyze_rejects_file_with_image_content_type_but_non_image_bytes():
    response = client.post(
        "/api/analyze",
        files={"file": ("fake.png", b"this is not an image at all", "image/png")},
    )
    assert response.status_code == 400
    assert "valid PNG, JPG, or WEBP" in response.json()["detail"]


def test_analyze_rejects_oversized_upload(monkeypatch):
    from app.config.settings import settings
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (1024 * 1024 + 10)
    response = client.post("/api/analyze", files={"file": ("big.png", big, "image/png")})
    assert response.status_code == 400
    assert "too large" in response.json()["detail"]


def test_sniff_image_type_recognizes_supported_formats():
    from app.routes.analyze import sniff_image_type
    assert sniff_image_type(b"\x89PNG\r\n\x1a\nxxxx") == "image/png"
    assert sniff_image_type(b"\xff\xd8\xff\xe0xxxx") == "image/jpeg"
    assert sniff_image_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert sniff_image_type(b"GIF89a...") is None
    assert sniff_image_type(b"") is None


@patch("app.routes.analyze.extract_visual_structure")
def test_missing_api_key_error_does_not_leak_configuration_details(mock_extract):
    from app.services.gemini_service import GeminiExtractionError
    mock_extract.side_effect = GeminiExtractionError("GEMINI_API_KEY is not configured. Add it to backend/.env.")
    response = client.post("/api/analyze", files={"file": ("s.png", PNG_BYTES, "image/png")})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "GEMINI_API_KEY" not in detail and ".env" not in detail


@patch("app.routes.analyze.extract_visual_structure")
def test_gemini_failure_returns_generic_502_without_internal_details(mock_extract):
    from app.services.gemini_service import GeminiExtractionError
    mock_extract.side_effect = GeminiExtractionError("Gemini API request failed: 503 secret-internal-detail")
    response = client.post("/api/analyze", files={"file": ("s.png", PNG_BYTES, "image/png")})
    assert response.status_code == 502
    assert "secret-internal-detail" not in response.text


@patch("app.routes.analyze.run_rule_engine")
@patch("app.routes.analyze.extract_visual_structure")
def test_unexpected_error_after_extraction_returns_safe_500(mock_extract, mock_rules):
    mock_extract.return_value = _fake_gemini_response()
    mock_rules.side_effect = RuntimeError("boom with /internal/path")
    response = client.post("/api/analyze", files={"file": ("s.png", PNG_BYTES, "image/png")})
    assert response.status_code == 500
    assert "boom" not in response.text and "/internal/path" not in response.text


@patch("app.routes.analyze.extract_visual_structure")
def test_analysis_with_no_findings_returns_valid_empty_result(mock_extract):
    clean = ExtractionResult(image=ImageMeta(width=800, height=600), colors=[], elements=[])
    mock_extract.return_value = clean.model_dump_json()
    response = client.post("/api/analyze", files={"file": ("s.png", PNG_BYTES, "image/png")})
    assert response.status_code == 200
    assert response.json()["findings"] == []
    assert response.json()["overallScore"] == 100
