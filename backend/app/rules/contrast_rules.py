"""
Contrast rule.

Evaluates only explicit foreground/background pairs extracted for
specific UI elements. It never constructs pairs from dominant colors.

Gemini identifies the visual relationship; this rule calculates the
WCAG contrast ratio and applies deterministic thresholds.
"""

from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding
from app.services.color_utils import contrast_ratio


WCAG_AA_NORMAL_TEXT_RATIO = 4.5
LOW_CONTRAST_MAJOR_THRESHOLD = 3.0


def run(extraction: ExtractionResult) -> list[RawFinding]:
    elements_by_id = {
        element.id: element
        for element in extraction.elements
    }

    findings: list[RawFinding] = []
    seen_pairs: set[tuple[str, str, str]] = set()

    for pair in extraction.contrastPairs:
        element = elements_by_id.get(pair.elementId)

        # Never evaluate a pair without a matching extracted element.
        if element is None:
            continue

        foreground = pair.foregroundColor.lower()
        background = pair.backgroundColor.lower()

        pair_key = (pair.elementId, foreground, background)

        if pair_key in seen_pairs:
            continue

        seen_pairs.add(pair_key)

        ratio = contrast_ratio(foreground, background)

        if ratio >= WCAG_AA_NORMAL_TEXT_RATIO:
            continue

        severity = (
            "major"
            if ratio < LOW_CONTRAST_MAJOR_THRESHOLD
            else "minor"
        )

        element_label = (
            element.label
            or element.role
            or element.type
        )

        findings.append(
            RawFinding(
                id=(
                    f"CONTRAST-{pair.elementId}-"
                    f"{foreground.lstrip('#').upper()}-"
                    f"{background.lstrip('#').upper()}"
                ),
                category="Color",
                severity=severity,
                title=f"Weak contrast for {element_label}",
                description=(
                    f"The text associated with the {element_label} element "
                    f"has a foreground color ({foreground}) against its "
                    f"background ({background}), producing a contrast ratio "
                    f"of {ratio:.2f}:1. This is below the WCAG AA "
                    f"normal-text threshold of "
                    f"{WCAG_AA_NORMAL_TEXT_RATIO}:1."
                ),
                confidence=0.6,
                relatedElements=[pair.elementId],
            )
        )

    return findings
