"""
Deterministic color math shared by the contrast rule
(app/rules/contrast_rules.py) and the recommendation layer's palette
generator (app/services/recommendations.py). Pure functions only - no
randomness, no external calls, no Gemini involvement. Consolidated here
so both places use the exact same math rather than duplicating it.
"""
import colorsys


def hex_to_rgb(hex_value: str) -> tuple[int, int, int]:
    h = hex_value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    clamped = [max(0, min(255, round(c))) for c in rgb]
    return "#{:02x}{:02x}{:02x}".format(*clamped)


def hex_to_hls(hex_value: str) -> tuple[float, float, float]:
    r, g, b = hex_to_rgb(hex_value)
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)


def hls_to_hex(h: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return rgb_to_hex((r * 255, g * 255, b * 255))


def _linearize_channel(c: int) -> float:
    """WCAG channel linearization step, applied to one 0-255 RGB channel."""
    c_norm = c / 255
    return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_value: str) -> float:
    """
    WCAG 2.x relative luminance: L = 0.2126*R + 0.7152*G + 0.0722*B,
    using linearized (gamma-corrected) channel values. Range 0.0-1.0.
    This is the actual formula the WCAG contrast-ratio spec defines, not
    a shortcut based on raw RGB brightness.
    """
    r, g, b = hex_to_rgb(hex_value)
    return (
        0.2126 * _linearize_channel(r)
        + 0.7152 * _linearize_channel(g)
        + 0.0722 * _linearize_channel(b)
    )


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """
    WCAG 2.x contrast ratio: (L_lighter + 0.05) / (L_darker + 0.05).
    Always >= 1.0 (identical colors) and <= 21.0 (pure black vs white).
    """
    l1 = relative_luminance(hex_a)
    l2 = relative_luminance(hex_b)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)
