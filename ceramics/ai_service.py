"""
Claude vision service for ceramic stage detection and description generation.

Workflow
--------
1. User uploads a photo of their ceramic piece.
2. The image bytes are sent to Claude along with the piece title.
3. Claude returns structured JSON:
   - stage_guess    : "greenware" | "bisque" | "glaze"
   - confidence     : 0.0–1.0
   - description    : human-readable, owner-voice sentence
   - glaze_notes    : detailed glaze analysis (only for glaze stage)
4. The view pre-fills the form with these values.
5. The user can confirm or correct before saving.
"""

import base64
import json
import logging
import re

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """\
You are an expert ceramics analyst with years of experience identifying clay \
bodies, firing stages, and glaze chemistry from photographs.

Analyse the image of a ceramic piece and return a JSON object with exactly \
these four keys:

1. "stage_guess"  — one of exactly: "greenware", "bisque", or "glaze"
   Greenware  : raw, unfired clay — grey/brown, matte, slightly rough or \
leathery surface, often shows tool marks or finger prints.
   Bisque     : fired once, unglazed — off-white or cream, porous, chalky \
matte finish, solid but still somewhat fragile.
   Glaze      : has glaze applied and (usually) been glaze-fired — vitreous \
or semi-vitreous surface with colour, sheen, or obvious glaze layer; may \
still be unfired if raw glaze powder/liquid is visible.

2. "confidence"   — float between 0.0 and 1.0 reflecting how certain you are.

3. "description"  — one or two sentences written from the owner's perspective, \
prefaced with "This is my [PIECE_TITLE] at the [stage] stage." followed by a \
warm, specific observation about the piece (shape, form, texture, colour, \
visible craftsmanship). Keep the tone personal and proud.

4. "glaze_notes"  — if stage_guess is "glaze", write one short phrase (under \
20 words) naming the glazes the way a potter would jot them in a studio \
notebook. Identify recognisable commercial glaze names where possible; \
otherwise describe by colour and finish. The potter will edit this before \
saving, so a best-guess starting point is perfect. \
Example: "Golden Hour yellow on the body, Carmel and White Gloss on the lid." \
If the stage is NOT glaze, set this to an empty string "".

Piece title: {title}

Return ONLY valid JSON — no markdown fences, no commentary, just the JSON object.
"""

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def analyze_ceramic_image(
    image_data: bytes,
    piece_title: str,
    media_type: str = "image/jpeg",
) -> dict:
    """
    Send an image to Claude and return the ceramic analysis.

    Returns a dict with keys:
        stage_guess  : str
        confidence   : float
        description  : str
        glaze_notes  : str
        error        : str | None  (set only on failure)
    """
    fallback = {
        "stage_guess": "greenware",
        "confidence": 0.5,
        "description": f"This is my {piece_title} ceramic piece.",
        "glaze_notes": "",
        "error": None,
    }

    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY is not set — skipping AI analysis.")
        fallback["error"] = "ANTHROPIC_API_KEY not configured."
        return fallback

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
        prompt = ANALYSIS_PROMPT.format(title=piece_title)

        message = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        response_text = message.content[0].text
        result = _parse_json_response(response_text, piece_title)
        result["error"] = None
        return result

    except anthropic.APIError as exc:
        logger.error("Anthropic API error during ceramic analysis: %s", exc)
        fallback["error"] = f"AI service error: {exc}"
        return fallback
    except Exception as exc:
        logger.exception("Unexpected error during ceramic analysis: %s", exc)
        fallback["error"] = "Unexpected error during AI analysis."
        return fallback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_STAGES = {"greenware", "bisque", "glaze"}


def _parse_json_response(text: str, piece_title: str) -> dict:
    """Extract and validate the JSON payload from Claude's response."""
    # Strip markdown code fences if present
    clean = re.sub(r"```(?:json)?", "", text).strip()

    # Find the outermost {...}
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in Claude response.")

    data = json.loads(match.group())

    stage = data.get("stage_guess", "greenware").lower().strip()
    if stage not in _VALID_STAGES:
        stage = "greenware"

    confidence = float(data.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))

    description = data.get("description", "").strip()
    if not description:
        description = f"This is my {piece_title} ceramic piece."

    glaze_notes = data.get("glaze_notes", "").strip() if stage == "glaze" else ""

    return {
        "stage_guess": stage,
        "confidence": confidence,
        "description": description,
        "glaze_notes": glaze_notes,
    }
