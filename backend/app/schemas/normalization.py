"""
Generic normalization utilities used throughout the extraction schema
and sanitization layer.

Gemini doesn't treat field names or enum-like values as a fixed
vocabulary - across requests it has sent "type" values as "body text",
"text", and would just as easily send a KEY like "font_size" instead of
"estimatedFontSize". Patching one exact string at a time is a losing
game. This module provides two small, well-separated mechanisms instead:

1. `resolve_alias` - for VALUE normalization (e.g. the `type` field's
   enum-like values). Preserves underscores as meaningful word
   separators, since canonical values like "body_text" use them.

2. `remap_keys` - for KEY (field name) normalization. Flattens away
   ALL formatting (case, spaces, hyphens, underscores, camelCase) before
   comparing, since the canonical key spelling itself mixes conventions
   (e.g. "estimatedFontSize" has no separators at all) - word-boundary
   preservation doesn't make sense for keys the way it does for values.

Both mechanisms share the same rule: normalize FORMATTING only, then
require an explicit match (via an alias table or the canonical set
itself) before accepting anything. A genuinely unrecognized key or value
is never invented or guessed at - it's left alone (for keys) or mapped
to an explicit fallback (for values).
"""
import re

_WHITESPACE_OR_HYPHEN = re.compile(r"[\s\-]+")
_REPEATED_UNDERSCORE = re.compile(r"_+")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]")


def normalize_token(value: str) -> str:
    """
    Canonicalize FORMATTING ONLY for VALUES: lowercase, collapse
    whitespace/hyphen runs into single underscores, collapse repeated
    underscores, trim leading/trailing underscores. Word boundaries are
    preserved as underscores, since canonical enum values ("body_text")
    rely on them. "Body   Text", "body-text", "BODY_TEXT" all become
    "body_text"; genuinely different words stay genuinely different.
    """
    token = value.strip().lower()
    token = _WHITESPACE_OR_HYPHEN.sub("_", token)
    token = _REPEATED_UNDERSCORE.sub("_", token)
    return token.strip("_")


def resolve_alias(raw: str, aliases: dict[str, str], valid_values: set[str], fallback: str) -> str:
    """
    Normalize a value's formatting, then resolve it to a canonical value
    using an explicit alias table and a set of already-canonical values.
    Anything that isn't a recognized formatting variant of something we
    actually know returns `fallback` instead of being accepted as-is -
    this is what prevents "blindly accepting unknown or unrelated values"
    while still tolerating formatting noise for values we DO recognize.
    """
    normalized = normalize_token(raw)
    if normalized in aliases:
        return aliases[normalized]
    if normalized in valid_values:
        return normalized
    return fallback


def flatten_key(key: str) -> str:
    """
    Canonicalize FORMATTING ONLY for KEYS: strip every non-alphanumeric
    character and lowercase. Unlike `normalize_token`, this does NOT
    preserve word boundaries, because the canonical key spellings we
    compare against mix conventions ("estimatedFontSize" has none,
    "boundingBox" has none, but a Gemini variant might send "font_size"
    or "bounding_box"). Flattening unifies camelCase/snake_case/kebab-
    case/spaced variants into one comparable form regardless of where
    each convention places its word boundaries.
    """
    return _NON_ALPHANUMERIC.sub("", key.lower())


def remap_keys(d: dict, canonical_keys: set[str], key_aliases: dict[str, str] | None = None) -> dict:
    """
    Build a new dict where any key matching a canonical field name - or
    a known alias of one - by FORMATTING ONLY is renamed to its exact
    canonical spelling. `key_aliases` maps a flattened alias string
    (e.g. "fontsize") to the canonical key it stands for (e.g.
    "estimatedFontSize") - use it only when two names are genuinely the
    same concept, not as a catch-all. Keys that don't match anything
    recognized are left completely unchanged (harmless extra data) -
    nothing is invented, and downstream code only ever reads known
    canonical keys, so unrecognized ones are simply never consulted.
    """
    key_aliases = key_aliases or {}
    canonical_lookup = {flatten_key(k): k for k in canonical_keys}

    remapped = {}
    for key, value in d.items():
        if not isinstance(key, str):
            remapped[key] = value
            continue

        flattened = flatten_key(key)
        if flattened in key_aliases:
            remapped[key_aliases[flattened]] = value
        elif flattened in canonical_lookup:
            remapped[canonical_lookup[flattened]] = value
        else:
            remapped[key] = value  # unrecognized - left as-is, ignored downstream

    return remapped
