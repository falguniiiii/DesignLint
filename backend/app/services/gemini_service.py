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

EXTRACTION_PROMPT = """You are a visual perception system. Analyze the supplied UI screenshot and report ONLY objectively observable visual information.

Do not evaluate design quality, make judgments, assign scores, identify problems, or suggest improvements. Your task is strictly visual extraction.

Extract the following information:

1. IMAGE
- Actual screenshot width and height in pixels.

2. UI ELEMENTS
- Identify visible UI elements such as buttons, headings, body text, cards, navigation items, images, inputs, icons, and containers.
- For each element, report:
  - A unique id.
  - Its visual type.
  - A short label containing visible text, when applicable.
  - An approximate bounding box in screenshot pixels: x, y, width, height.
  - Estimated font size in pixels when the element contains text.
  - Its semantic role, using one of:
    page_title, section_heading, body_copy, primary_action,
    secondary_action, navigation_item, price, metric,
    product_image, decorative_image, form_control, other.
  - sectionId: the id of the section containing the element, if identifiable.
  - groupId: a shared identifier for elements that clearly belong to the same repeated component group. Use null when no clear repeated group exists.

Do not infer semantic roles from visual styling alone when the role is unclear. Use "other" rather than guessing.

3. SECTIONS
- Identify visually distinct, meaningful page regions.
- For each section, report:
  - A unique id.
  - Its type, using one of:
    header, hero, navigation, sidebar, main_content,
    product_grid, content_grid, form, footer, other.
  - A short visible label when applicable.
  - Its approximate bounding box in screenshot pixels.
- Use section boundaries based on visible layout structure.
- Do not invent sections for areas that cannot be identified confidently.
- Every non-null sectionId on an element must reference an id in the returned sections array.
- Do not create duplicate section ids.

4. COLORS
- Identify up to 6 dominant colors actually visible in the interface.
- Report each as a hex color code and an observable color role when identifiable.

BOUNDING BOX RULES
- Use pixel coordinates relative to the top-left corner of the screenshot.
- Report x and y as the top-left position.
- Report width and height as positive dimensions.
- Keep coordinates within the screenshot boundaries.
- Do not fabricate precise measurements; approximate visible boundaries.

RESPONSE REQUIREMENTS
- Return ONLY valid JSON.
- Use the exact field names and structure shown below.
- Use null for unavailable optional values.
- Use empty arrays when no sections, elements, or colors can be identified.
- Do not include markdown, code fences, explanations, or additional fields.
- Include only information that can be observed in the screenshot.

JSON STRUCTURE:

{
  "image": {
    "width": 1440,
    "height": 900
  },
  "elements": [
    {
      "id": "element-1",
      "type": "heading",
      "label": "Welcome",
      "boundingBox": {
        "x": 100,
        "y": 120,
        "width": 300,
        "height": 40
      },
      "estimatedFontSize": 32,
      "role": "page_title",
      "sectionId": "hero-1",
      "groupId": null
    }
  ],
  "sections": [
    {
      "id": "hero-1",
      "type": "hero",
      "label": "Welcome section",
      "boundingBox": {
        "x": 0,
        "y": 80,
        "width": 1440,
        "height": 500
      }
    }
  ],
  "colors": [
    {
      "hex": "#123456",
      "role": "primary"
    }
  ]
}

The values above are illustrative examples of the JSON structure, not elements or colors to copy. Extract the actual screenshot content only."""


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
