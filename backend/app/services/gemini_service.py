"""
This service is responsible for exactly one thing: asking Gemini to
perceive what's visually present in a screenshot, and returning that
as raw text.

It must NEVER ask Gemini to judge, critique, or score the design.
The prompt below is deliberately restricted to observable facts.
Judgment happens later, in the rule engine (Phase 3), on our own code.
"""
from google import genai
from google.genai import types

from app.config.settings import settings

EXTRACTION_PROMPT = """You are a visual perception system. Look at this UI screenshot and report ONLY what is observably present. Do not evaluate quality, do not say anything is good or bad, do not suggest improvements.

Identify:
- UI elements: buttons, headings, body text, cards, navigation, images, inputs, icons, containers
- For each element: an id, its type, a short label if it has visible text, an approximate bounding box (x, y, width, height in pixels), and an estimated font size in pixels if it is text
- Up to 6 dominant colors present in the interface, as hex codes

Return ONLY valid JSON matching this exact shape, with no markdown formatting, no code fences, and no commentary:

{
  "image": {"width": <int>, "height": <int>},
  "elements": [
    {"id": "element-1", "type": "button", "label": "Login", "boundingBox": {"x": 0, "y": 0, "width": 0, "height": 0}, "estimatedFontSize": 16}
  ],
  "colors": [
    {"hex": "#123456", "role": "primary"}
  ]
}

Only include elements and colors you can actually observe. Do not invent elements to fill the schema."""


class GeminiExtractionError(Exception):
    """Raised when the Gemini call itself fails (network, auth, rate limit)."""


def extract_visual_structure(image_bytes: bytes, mime_type: str) -> str:
    """
    Sends the screenshot to Gemini and returns the raw text response.
    Validation of that text against ExtractionResult happens separately
    in app/services/validation.py - this function's only job is the API call.
    """
    if not settings.GEMINI_API_KEY:
        raise GeminiExtractionError(
            "GEMINI_API_KEY is not configured. Add it to backend/.env."
        )

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                # NOTE: We tried adding `response_schema=ExtractionResult` here
                # to constrain Gemini's structured output to our exact schema.
                # It broke: the installed google-genai==0.3.0 SDK raised
                # "'dict' object has no attribute 'upper'" internally while
                # processing the schema, before the request even reached
                # Gemini. Reverted rather than debugging SDK internals blind -
                # the normalization (schemas/extraction.py) and sanitization
                # (services/validation.py) layers already handle wording
                # variance without depending on this feature, and are
                # actually tested end to end. If you want to retry this later,
                # it would need a newer google-genai version verified against
                # a real API call first, not assumed to work.
                temperature=0.1,
            ),
        )
    except Exception as exc:
        raise GeminiExtractionError(f"Gemini API request failed: {exc}") from exc

    if not response.text:
        raise GeminiExtractionError("Gemini returned an empty response.")

    return response.text
