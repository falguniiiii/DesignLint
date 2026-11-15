import logging

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.config.settings import settings
from app.services.gemini_service import (
    extract_visual_structure,
    GeminiExtractionError,
)
from app.services.validation import (
    validate_extraction,
    ExtractionValidationError,
)
from app.services.rule_engine import run_rule_engine
from app.services.scoring import calculate_scores
from app.services.recommendations import enrich_findings, build_palette
from app.schemas.findings import AuditResult, ElementRef

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


def sniff_image_type(data: bytes) -> str | None:
    """
    Identify PNG/JPEG/WEBP from the file's own first bytes instead of
    trusting the browser-supplied Content-Type.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _looks_like_image(data: bytes, mime_type: str) -> bool:
    """
    Check the file signature against the declared MIME type.
    """
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


@router.post("/analyze")
async def analyze_screenshot(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a PNG, JPG, or WEBP image.",
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    image_bytes = await file.read(max_bytes + 1)

    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Image is too large. Please use a file smaller than {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    detected_type = sniff_image_type(image_bytes)

    if detected_type is None:
        raise HTTPException(
            status_code=400,
            detail="This file doesn't look like a valid PNG, JPG, or WEBP image. Please export the screenshot again and retry.",
        )

    if not _looks_like_image(image_bytes, file.content_type):
        raise HTTPException(
            status_code=400,
            detail="This file doesn't appear to be a valid PNG, JPG, or WEBP image. Please export the screenshot again and retry.",
        )

    try:
        raw_result = extract_visual_structure(image_bytes, detected_type)

    except GeminiExtractionError as exc:
        logger.warning("Gemini extraction call failed: %s", exc)

        if "GEMINI_API_KEY" in str(exc):
            raise HTTPException(
                status_code=500,
                detail="The analysis service isn't set up on the server yet. If you are running DesignLint yourself, check the backend configuration.",
            ) from exc

        raise HTTPException(
            status_code=502,
            detail="DesignLint couldn't reach the analysis service right now. Please try again.",
        ) from exc

    try:
        extraction = validate_extraction(raw_result)

    except ExtractionValidationError as exc:
        logger.warning("Extraction validation failed: %s", exc)

        raise HTTPException(
            status_code=502,
            detail="DesignLint received an unexpected response while analyzing this image. Please try again.",
        ) from exc

    # Gemini handles visual extraction only. All judgments, scoring,
    # recommendations, and palette derivation happen deterministically here.
    try:
        raw_findings = run_rule_engine(extraction)
        category_scores, overall_score = calculate_scores(raw_findings)
        findings = enrich_findings(raw_findings, extraction)
        palette = build_palette(extraction)

        audit = AuditResult(
            overallScore=overall_score,
            categoryScores=category_scores,
            findings=findings,
            palette=palette,
            elementCount=len(extraction.elements),
            image=extraction.image,
            elements=[
                ElementRef(
                    id=element.id,
                    type=element.type,
                    boundingBox=element.boundingBox,
                )
                for element in extraction.elements
            ],
        )

        return audit.model_dump()

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while building the audit")

        raise HTTPException(
            status_code=500,
            detail="Something went wrong while analyzing this screenshot. Please try again, or try a different screenshot.",
        ) from exc