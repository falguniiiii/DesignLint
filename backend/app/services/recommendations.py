"""
Recommendation layer - runs AFTER the rule engine has produced findings,
turning each RawFinding into a Finding with structured, actionable
guidance attached.

The rule engine's job is detection ("is this a problem, how severe").
This layer's job is explanation ("what exactly should someone with no
UI/UX background do about it"). Keeping them separate means detection
logic stays untouched and independently testable - this layer only adds
guidance on top of findings that already exist. It never invents new
findings and never changes severity, category, or confidence.

Everything here is built deterministically from the SAME data the rule
already had access to (the finding + the validated extraction) - nothing
calls Gemini, and nothing is randomized. The same input always produces
the exact same recommendation, including color suggestions.
"""
from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding, Finding, Recommendation, ColorSuggestion
from app.services.color_utils import hex_to_hls, hls_to_hex, relative_luminance, contrast_ratio

SPACING_SCALE = [8, 16, 24, 32, 40, 48]
WCAG_AA_NORMAL_TEXT_RATIO = 4.5


def enrich_findings(raw_findings: list[RawFinding], extraction: ExtractionResult) -> list[Finding]:
    """Attach a structured Recommendation to every raw finding."""
    elements_by_id = {e.id: e for e in extraction.elements}
    return [
        Finding(
            **raw.model_dump(),
            recommendation=_build_recommendation(raw, extraction, elements_by_id),
        )
        for raw in raw_findings
    ]


def _build_recommendation(finding: RawFinding, extraction: ExtractionResult, elements_by_id: dict) -> Recommendation:
    if finding.id == "COLOR-001":
        return _color_palette_recommendation(extraction)
    if finding.id.startswith("CONTRAST-"):
        return _contrast_recommendation(finding)
    if finding.id == "TYPOGRAPHY-001":
        return _typography_many_sizes_recommendation(extraction)
    if finding.id == "TYPOGRAPHY-002":
        return _typography_small_text_recommendation(finding, elements_by_id)
    if finding.id == "TYPOGRAPHY-003":
        return _typography_hierarchy_recommendation(extraction)
    if finding.id.startswith("SPACING-"):
        return _spacing_recommendation(finding, elements_by_id)
    if finding.id.startswith("CONSISTENCY-") and finding.id.endswith("HEIGHT"):
        return _consistency_recommendation(finding, elements_by_id, dimension="height")
    if finding.id.startswith("CONSISTENCY-") and finding.id.endswith("WIDTH"):
        return _consistency_recommendation(finding, elements_by_id, dimension="width")

    # Fallback for any future rule ID we haven't written specific
    # guidance for yet. Not reachable with today's rule set, but keeps
    # the layer safe if a new rule is added without updating this file.
    return Recommendation(
        whyItMatters="This affects how polished and predictable the interface feels to users.",
        fix="Review the specific values mentioned above and make them consistent with the rest of the page.",
    )


# --- Color -------------------------------------------------------------

def _is_dark_ui(colors: list) -> bool:
    """
    Deterministic light-vs-dark detection. Prefers a role-labeled
    background color if Gemini provided one (the most direct evidence
    available); otherwise falls back to the average luminance across all
    extracted colors, which tends to be low for dark UIs (dominated by
    dark background/surface tones) and high for light UIs. This exists
    specifically so the palette generator doesn't assume every screenshot
    is light-mode.
    """
    labeled_backgrounds = [c for c in colors if c.role and "background" in c.role.lower()]
    if labeled_backgrounds:
        avg = sum(relative_luminance(c.hex) for c in labeled_backgrounds) / len(labeled_backgrounds)
        return avg < 0.5
    avg = sum(relative_luminance(c.hex) for c in colors) / len(colors)
    return avg < 0.5


def _derive_palette(colors: list) -> list[ColorSuggestion] | None:
    """
    Deterministically derive a 6-role palette from the colors Gemini
    actually extracted from the screenshot. Every role is grounded in a
    documented rule, not a random or "aesthetically pleasing" guess, and
    the assignment direction adapts to whether the UI reads as light or
    dark (see _is_dark_ui) rather than always treating the lightest
    extracted color as "the background":

    Explicit role labels come first: if Gemini labeled exactly one color as
    background/text/primary/surface/secondary text/border (and the labels
    don't conflict), that color is used for that role. Everything below is
    the fallback for roles with no reliable label.

    Light UI:
    - Background = lightest extracted color; Text = darkest
    - Surface = Background nudged slightly lighter (derived, not a fixed white)
    - Border = Background nudged slightly darker

    Dark UI:
    - Background = darkest extracted color; Text = lightest
    - Surface = Background nudged slightly LIGHTER (a raised dark card),
      never white
    - Border = Background nudged a bit more than Surface

    Both:
    - Primary = the most saturated extracted color that isn't near-white
      or near-black (so it reads as an intentional accent, not a neutral).
      If NO extracted color has meaningful saturation (a genuinely
      neutral-only set - all grays/near-white/near-black), Primary is
      OMITTED from the result entirely rather than invented. The other
      five roles are still legitimately grounded in extracted data, so
      only the one unsupported role is dropped, not the whole palette.
    - Secondary text = Text, pulled toward a mid-gray in whichever
      direction keeps it readable against Background

    Text vs Background is validated with contrast_ratio; if the extracted
    pair is below 4.5:1, Text is replaced by a lightness-only adjustment of
    the extracted color (see _find_accessible_text_color). Surface, Border,
    Secondary text, and any adjusted Text are DERIVED, and their usage
    notes say so - the palette is a suggestion, not a list of detected colors.

    Returns None when there's too little data (fewer than 2 extracted
    colors) to derive anything meaningfully tied to this screenshot -
    the caller is responsible for saying so rather than presenting an
    invented palette as if it came from the screenshot.
    """
    if len(colors) < 2:
        return None

    hls_values = [(hex_to_hls(c.hex), c.hex) for c in colors]
    roles = _reliable_roles(colors)
    labeled_hexes = {c.hex.lower() for c in colors if _role_kind(c.role)}  # any recognized label
    reliable_hexes = set(roles.values())  # only unambiguous labels

    # --- Primary: an explicit, unambiguous label wins; otherwise the most
    # saturated unlabeled mid-lightness color (a pure gray has lightness but
    # no saturation, so it is never an accent). None if neither exists.
    MIN_ACCENT_SATURATION = 0.15
    primary_hex = roles.get("primary")
    if primary_hex is None:
        saturated_candidates = [
            item for item in hls_values
            if 0.15 < item[0][1] < 0.9 and item[0][2] > MIN_ACCENT_SATURATION
            and item[1].lower() not in labeled_hexes  # labeled colors are not guessed to be accents
        ]
        primary_hex = max(saturated_candidates, key=lambda item: item[0][2])[1] if saturated_candidates else None

    # Pool for guessing Background/Text when a label is missing: never the
    # accent, and never a color reliably labeled for another role (surface,
    # border, ...). Falls back to wider pools only if this one is empty.
    pool = [
        item for item in hls_values
        if item[1].lower() != (primary_hex or "").lower()
        and not (item[1].lower() in reliable_hexes and item[1].lower() not in (roles.get("background"), roles.get("text")))
    ] or [item for item in hls_values if item[1].lower() != (primary_hex or "").lower()] or hls_values

    # --- Light vs dark: an explicit Background decides; else the old fallback.
    background_hex = roles.get("background")
    text_hex = roles.get("text")
    dark_ui = relative_luminance(background_hex) < 0.5 if background_hex else _is_dark_ui(colors)

    # --- Background / Text: explicit labels first, lightness extremes only
    # for whichever role is still missing (and never the same color twice
    # if another choice exists).
    if background_hex is None:
        options = [i for i in pool if i[1].lower() != (text_hex or "")] or pool
        pick = min(options, key=lambda i: i[0][1]) if dark_ui else max(options, key=lambda i: i[0][1])
        background_hex = pick[1]
    if text_hex is None:
        options = [i for i in pool if i[1].lower() != background_hex.lower()] or pool
        pick = max(options, key=lambda i: i[0][1]) if dark_ui else min(options, key=lambda i: i[0][1])
        text_hex = pick[1]
    bg_h, bg_l, bg_s = hex_to_hls(background_hex)

    # --- Text vs Background validation (existing WCAG contrast_ratio) ---
    # Applies to labeled and guessed Text alike. If the pair fails AA, keep
    # the original hue/saturation and move only lightness (deterministic).
    text_note = "Taken as detected."
    if contrast_ratio(text_hex, background_hex) < WCAG_AA_NORMAL_TEXT_RATIO:
        original_text = text_hex
        text_hex = _find_accessible_text_color(
            text_hex, background_hex, direction=_readable_direction(background_hex)
        )
        text_note = (
            f"Derived from detected {original_text.lower()}: its lightness was adjusted "
            f"to reach {WCAG_AA_NORMAL_TEXT_RATIO}:1 contrast with the background."
        )
    text_h, text_l, text_s = hex_to_hls(text_hex)

    # --- Secondary text: a labeled color if it is readable and distinct,
    # otherwise Text pulled toward mid-gray and re-validated.
    secondary_note = "Taken as detected."
    secondary_text_hex = roles.get("secondary_text")
    if (
        secondary_text_hex is None
        or secondary_text_hex == text_hex.lower()
        or contrast_ratio(secondary_text_hex, background_hex) < WCAG_AA_NORMAL_TEXT_RATIO
    ):
        secondary_note = "Derived from the text color."
        if dark_ui:
            secondary_text_hex = hls_to_hex(text_h, max(0.4, text_l - 0.35), min(text_s, 0.05))
        else:
            secondary_text_hex = hls_to_hex(text_h, min(0.6, text_l + 0.35), min(text_s, 0.05))
        if contrast_ratio(secondary_text_hex, background_hex) < WCAG_AA_NORMAL_TEXT_RATIO:
            secondary_text_hex = _find_accessible_text_color(
                secondary_text_hex, background_hex, direction=_readable_direction(background_hex)
            )
        if secondary_text_hex.lower() == text_hex.lower():
            secondary_text_hex = None  # no distinct readable shade - omit rather than duplicate Text

    # --- Surface: a labeled color if Text stays readable on it, otherwise
    # derived from Background (never a hardcoded white).
    surface_note = "Taken as detected."
    surface_hex = roles.get("surface")
    if surface_hex is not None and contrast_ratio(text_hex, surface_hex) < WCAG_AA_NORMAL_TEXT_RATIO:
        surface_hex = None
    if surface_hex is None:
        surface_note = "Derived from the background color."
        for step in (0.08, 0.04) if dark_ui else (0.04,):
            candidate = hls_to_hex(bg_h, min(1.0, bg_l + step), min(bg_s, 0.05))
            if contrast_ratio(text_hex, candidate) >= WCAG_AA_NORMAL_TEXT_RATIO:
                surface_hex = candidate
                break

    # --- Border: a labeled color, otherwise derived from Background.
    border_note = "Taken as detected."
    border_hex = roles.get("border")
    if border_hex is None:
        border_note = "Derived from the background color."
        if dark_ui:
            border_hex = hls_to_hex(bg_h, min(1.0, bg_l + 0.12), min(bg_s, 0.05))
        else:
            border_hex = hls_to_hex(bg_h, max(0.0, bg_l - 0.08), min(bg_s, 0.05))

    palette = []
    if primary_hex:
        palette.append(ColorSuggestion(
            role="Primary", hex=primary_hex,
            usage="Main buttons, links, and primary actions. Taken as detected.",
            source="detected",
        ))
    palette.append(ColorSuggestion(
        role="Background", hex=background_hex,
        usage="The page's main background. Taken as detected.",
        source="detected",
    ))
    if surface_hex:
        palette.append(ColorSuggestion(
            role="Surface", hex=surface_hex,
            usage=f"Cards, panels, and content blocks on top of the background. {surface_note}",
            source=_source_of(surface_note),
        ))
    palette.append(ColorSuggestion(
        role="Text", hex=text_hex, usage=f"Primary body and heading text. {text_note}",
        source=_source_of(text_note),
    ))
    if secondary_text_hex:
        palette.append(ColorSuggestion(
            role="Secondary text", hex=secondary_text_hex,
            usage=f"Captions, hints, and less important text. {secondary_note}",
            source=_source_of(secondary_note),
        ))
    palette.append(ColorSuggestion(
        role="Border", hex=border_hex, usage=f"Dividers and input borders. {border_note}",
        source=_source_of(border_note),
    ))
    return palette


def _source_of(note: str) -> str:
    """The notes above start with "Taken as detected." or "Derived ..."."""
    return "detected" if note.startswith("Taken") else "derived"


def _role_kind(role: str | None) -> str | None:
    """Map Gemini's free-text role label to a palette role, or None if unrecognized."""
    r = (role or "").lower().replace("_", " ").replace("-", " ").strip()
    if not r:
        return None
    if "text" in r or "foreground" in r or "heading" in r:
        return "secondary_text" if ("secondary" in r or "muted" in r) else "text"
    if "surface" in r or "card" in r:
        return "surface"
    if "background" in r or r == "bg":
        return "background"
    if "border" in r:
        return "border"
    if "primary" in r or "accent" in r:
        return "primary"
    return None


def _reliable_roles(colors: list) -> dict[str, str]:
    """
    Role -> lowercase hex, but ONLY for labels that are unambiguous:
    - a role labeled on two or more DIFFERENT colors is ambiguous (skipped)
    - one color labeled with two DIFFERENT roles is a conflict (skipped for both)
    Skipped roles fall back to the normal derivation rules.
    """
    hexes_by_kind: dict[str, set] = {}
    kinds_by_hex: dict[str, set] = {}
    for c in colors:
        kind = _role_kind(c.role)
        if kind:
            hexes_by_kind.setdefault(kind, set()).add(c.hex.lower())
            kinds_by_hex.setdefault(c.hex.lower(), set()).add(kind)
    reliable = {}
    for kind, hexes in hexes_by_kind.items():
        if len(hexes) == 1:
            only = next(iter(hexes))
            if len(kinds_by_hex[only]) == 1:
                reliable[kind] = only
    return reliable


def _readable_direction(background_hex: str) -> int:
    """
    -1 (darken) or +1 (lighten): whichever of black/white contrasts more
    with the background, so the adjustment always moves toward a reachable
    readable shade. Deterministic, uses the shared contrast_ratio.
    """
    return -1 if contrast_ratio("#000000", background_hex) >= contrast_ratio("#FFFFFF", background_hex) else 1


def _color_palette_recommendation(extraction: ExtractionResult) -> Recommendation:
    palette = _derive_palette(extraction.colors)

    if palette is None:
        return Recommendation(
            whyItMatters=(
                "When a screen uses too many different colors, it becomes hard to tell which "
                "elements are actually important. Buttons, warnings, and regular content all "
                "start to look similar, so users aren't sure what to focus on or click."
            ),
            fix=(
                "Reduce the palette to a small, consistent set of colors: one primary color for "
                "actions, one background, one text color, and a couple of supporting neutrals."
            ),
            suggestedValue="Not enough reliable color information was detected to generate a tailored palette.",
            palette=None,
        )

    return Recommendation(
        whyItMatters=(
            "When a screen uses too many different colors, it becomes hard to tell which "
            "elements are actually important. Buttons, warnings, and regular content all "
            "start to look similar, so users aren't sure what to focus on or click."
        ),
        fix=(
            "Reduce the palette to a small, consistent set of colors: one primary color for "
            "actions, one background, one text color, and a couple of supporting neutrals. "
            "Save any other colors for rare situations, like error messages."
        ),
        suggestedValue=(
            "Suggested palette to try, built from the colors detected in this screenshot. "
            "Some colors are used as detected; others are derived from them (each one says which) "
            "so that text stays readable. This is a starting point, not the single objectively best palette:"
        ),
        palette=palette,
    )


# --- Contrast --------------------------------------------------------------

def _find_accessible_text_color(text_hex: str, background_hex: str, target_ratio: float = WCAG_AA_NORMAL_TEXT_RATIO, direction: int | None = None) -> str:
    """
    Deterministically adjusts only the text color's HLS lightness (never
    hue or saturation, so it stays recognizably "the same color") toward
    black or white until it reaches the target contrast ratio against the
    given background, or hits pure black/white. Same inputs always
    produce the same output - no randomness.
    """
    h, l, s = hex_to_hls(text_hex)
    bg_luminance = relative_luminance(background_hex)
    text_luminance = relative_luminance(text_hex)

    # If the background is the lighter of the two, darkening the text
    # widens the gap; otherwise lightening it does.
    if direction is None:
        direction = -1 if bg_luminance >= text_luminance else 1

    candidate_l = l
    candidate_hex = text_hex
    step = 0.02
    for _ in range(50):
        candidate_l = max(0.0, min(1.0, candidate_l + direction * step))
        candidate_hex = hls_to_hex(h, candidate_l, s)
        if contrast_ratio(candidate_hex, background_hex) >= target_ratio:
            return candidate_hex
        if candidate_l in (0.0, 1.0):
            break

    return candidate_hex  # best effort reached (still an improvement), even if target wasn't fully hit


def _contrast_recommendation(finding: RawFinding) -> Recommendation:
    # Parse back out of the id, formatted as CONTRAST-<TEXTHEX>-<BGHEX>
    # (uppercase hex, no '#') by contrast_rules.py.
    _, text_hex_part, bg_hex_part = finding.id.split("-")
    text_hex = f"#{text_hex_part.lower()}"
    background_hex = f"#{bg_hex_part.lower()}"

    suggested_hex = _find_accessible_text_color(text_hex, background_hex)
    new_ratio = contrast_ratio(suggested_hex, background_hex)

    return Recommendation(
        whyItMatters=(
            "Low contrast between text and its background makes text harder to read, "
            "especially for people with low vision, older users, or anyone using their "
            "phone outdoors in bright light."
        ),
        fix=f"Change the text color from {text_hex} to a darker or lighter shade so it stands out more clearly against the background.",
        suggestedValue=(
            f"Try changing {text_hex} to {suggested_hex} "
            f"(raises the contrast ratio to about {new_ratio:.1f}:1 against {background_hex})."
        ),
    )


# --- Typography ----------------------------------------------------------

def _typography_many_sizes_recommendation(extraction: ExtractionResult) -> Recommendation:
    sizes = sorted({
        e.estimatedFontSize for e in extraction.elements
        if e.type in {"heading", "body_text"} and e.estimatedFontSize
    })
    if len(sizes) >= 3:
        suggested = (
            f"Use only these sizes: {sizes[-1]}px for headings, {sizes[len(sizes) // 2]}px "
            f"for body text, and {sizes[0]}px for small text or captions."
        )
    else:
        suggested = "Pick 3-4 fixed sizes total (for example 24px, 18px, 16px, 13px) and use only those across the page."

    return Recommendation(
        whyItMatters=(
            "Too many different text sizes make it hard to tell what's a heading and what's "
            "regular text, and the page can feel inconsistent, like it was assembled from "
            "different pieces rather than designed as one system."
        ),
        fix="Pick a small, fixed set of font sizes and use only those everywhere on the page.",
        suggestedValue=suggested,
    )


def _typography_small_text_recommendation(finding: RawFinding, elements_by_id: dict) -> Recommendation:
    sizes = [
        elements_by_id[eid].estimatedFontSize
        for eid in finding.relatedElements
        if eid in elements_by_id and elements_by_id[eid].estimatedFontSize
    ]
    smallest = min(sizes) if sizes else None
    suggested = (
        f"Change the affected text from {smallest}px to at least 14px (16px is even safer for body text)."
        if smallest is not None
        else "Increase the affected text to at least 14px (16px is even safer for body text)."
    )
    return Recommendation(
        whyItMatters=(
            "Text smaller than 12px is difficult to read for most people, especially on "
            "phone screens or for anyone with reduced vision."
        ),
        fix="Increase the font size of the affected text.",
        suggestedValue=suggested,
    )


def _typography_hierarchy_recommendation(extraction: ExtractionResult) -> Recommendation:
    headings = [e.estimatedFontSize for e in extraction.elements if e.type == "heading" and e.estimatedFontSize]
    body = [e.estimatedFontSize for e in extraction.elements if e.type == "body_text" and e.estimatedFontSize]

    if headings and body:
        avg_body = sum(body) / len(body)
        suggested_heading = round(avg_body) + 8
        suggested = f"Make headings at least {suggested_heading}px (your body text is currently about {round(avg_body)}px)."
    else:
        suggested = "Make headings at least 6-8px larger than your body text."

    return Recommendation(
        whyItMatters=(
            "When headings and body text are nearly the same size, it's hard for users to "
            "quickly scan the page and understand its structure."
        ),
        fix="Make headings noticeably bigger (and usually bolder) than body text.",
        suggestedValue=suggested,
    )


# --- Spacing -------------------------------------------------------------

def _closest_scale_value(value: float) -> int:
    return min(SPACING_SCALE, key=lambda s: abs(s - value))


def _spacing_recommendation(finding: RawFinding, elements_by_id: dict) -> Recommendation:
    elements = [elements_by_id[eid] for eid in finding.relatedElements if eid in elements_by_id]
    elements_sorted = sorted(elements, key=lambda e: e.boundingBox.y)

    gaps = []
    for a, b in zip(elements_sorted, elements_sorted[1:]):
        gap = b.boundingBox.y - (a.boundingBox.y + a.boundingBox.height)
        if gap >= 0:
            gaps.append(gap)

    if gaps:
        suggested_value = _closest_scale_value(sum(gaps) / len(gaps))
        suggested = f"Use {suggested_value}px between each of these elements (currently ranging from {min(gaps)}px to {max(gaps)}px)."
    else:
        suggested = "Pick one spacing value (for example 16px or 24px) and use it consistently between these elements."

    return Recommendation(
        whyItMatters=(
            "When the space between similar items varies a lot, the layout feels unplanned "
            "and messy, even if each item looks fine on its own."
        ),
        fix="Use one consistent gap size between all of these elements instead of different amounts each time.",
        suggestedValue=suggested,
    )


# --- Consistency -----------------------------------------------------------

def _consistency_recommendation(finding: RawFinding, elements_by_id: dict, dimension: str) -> Recommendation:
    elements = [elements_by_id[eid] for eid in finding.relatedElements if eid in elements_by_id]
    values = [getattr(e.boundingBox, dimension) for e in elements]

    # e.g. "CONSISTENCY-BUTTON-HEIGHT" -> "button"
    id_parts = finding.id.split("-")
    type_word = id_parts[1].lower() if len(id_parts) > 1 else "element"

    if values:
        suggested_value = round(sum(values) / len(values))
        suggested = f"Set all {type_word}s to {suggested_value}px {dimension} (currently ranging from {min(values)}px to {max(values)}px)."
    else:
        suggested = f"Pick one {dimension} and use it for all {type_word}s."

    return Recommendation(
        whyItMatters=(
            f"When {type_word}s on the same page have different sizes, the interface feels "
            "less organized and it's harder for users to predict what they're looking at."
        ),
        fix=f"Make all {type_word}s the same {dimension}.",
        suggestedValue=suggested,
    )
