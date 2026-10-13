"""
Contrast rule.

Checks contrast between colors Gemini labeled as text-like and colors
labeled as background-like, using the actual WCAG 2.x contrast-ratio
formula (app/services/color_utils.py) - never a guess based on raw RGB
brightness. This rule only runs when the extracted colors give us a
role-labeled text/background pair to compare; if Gemini didn't label
any colors that way, it produces no finding rather than guessing which
extracted colors are "the text" and "the background" - matching the
project's rule of not inventing data we don't actually have.

We check against the WCAG AA "normal text" threshold (4.5:1) since we
don't have per-element font size tied to these page-level dominant
colors, so we can't reliably apply the "large text" exception (3:1).
That's a real limitation, so it's a threshold check, not a claim of
full WCAG compliance for any specific piece of text.
"""
from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding
from app.services.color_utils import contrast_ratio

WCAG_AA_NORMAL_TEXT_RATIO = 4.5
LOW_CONTRAST_MAJOR_THRESHOLD = 3.0


def run(extraction: ExtractionResult) -> list[RawFinding]:
    text_colors = [c for c in extraction.colors if c.role and "text" in c.role.lower()]
    background_colors = [c for c in extraction.colors if c.role and "background" in c.role.lower()]

    if not text_colors or not background_colors:
        return []  # not enough role-labeled data to reliably identify a text/background pair

    findings: list[RawFinding] = []
    seen_pairs = set()

    for text_color in text_colors:
        for bg_color in background_colors:
            if text_color.hex == bg_color.hex:
                continue
            pair_key = (text_color.hex, bg_color.hex)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            ratio = contrast_ratio(text_color.hex, bg_color.hex)
            if ratio >= WCAG_AA_NORMAL_TEXT_RATIO:
                continue  # meets the threshold - not a finding

            severity = "major" if ratio < LOW_CONTRAST_MAJOR_THRESHOLD else "minor"
            role_label = text_color.role or "text"
            bg_label = bg_color.role or "background"

            findings.append(
                RawFinding(
                    id=f"CONTRAST-{text_color.hex.lstrip('#').upper()}-{bg_color.hex.lstrip('#').upper()}",
                    category="Color",
                    severity=severity,
                    title=f"Weak contrast for {role_label}",
                    description=(
                        f"The contrast ratio between the {role_label} color ({text_color.hex}) "
                        f"and the {bg_label} color ({bg_color.hex}) is about {ratio:.1f}:1, which "
                        f"is below the commonly recommended minimum of {WCAG_AA_NORMAL_TEXT_RATIO}:1 "
                        "for normal text (WCAG AA)."
                    ),
                    confidence=0.6,
                    relatedElements=[],
                )
            )

    return findings
