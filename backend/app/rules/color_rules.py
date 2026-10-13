"""
Color rules.

Gemini can only report colors it visually distinguished as dominant -
it has no access to the actual CSS palette. So these rules stay
conservative: they flag patterns visible in that extracted list, not
absolute accessibility judgments the screenshot can't support.
"""
from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding

MAX_RECOMMENDED_COLORS = 5


def run(extraction: ExtractionResult) -> list[RawFinding]:
    findings: list[RawFinding] = []
    colors = extraction.colors

    if len(colors) > MAX_RECOMMENDED_COLORS:
        findings.append(
            RawFinding(
                id="COLOR-001",
                category="Color",
                severity="suggestion",
                title="Many prominent colors detected",
                description=(
                    f"{len(colors)} visually dominant colors were identified in this "
                    "interface. A large number of prominent colors can weaken visual "
                    "hierarchy and make the palette feel less intentional."
                ),
                confidence=0.55,
                relatedElements=[],
            )
        )

    return findings
