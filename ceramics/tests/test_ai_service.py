"""
AI service tests
================
These tests cover the two public-facing layers of ``ceramics/ai_service.py``:

1. ``_parse_json_response`` — pure parsing / validation logic, no network calls.
   We feed it raw text strings and assert the returned dict is correct.

2. ``analyze_ceramic_image`` — the top-level function that calls the Anthropic
   API.  The real API is **never called** in tests; instead we:
   - Use ``@override_settings(ANTHROPIC_API_KEY="")`` to verify the early-
     return / fallback path when no key is configured.
   - Use ``unittest.mock.patch`` to replace ``anthropic.Anthropic`` with a
     mock and verify the happy path and error paths.
"""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from ceramics.ai_service import _parse_json_response, analyze_ceramic_image


# ---------------------------------------------------------------------------
# _parse_json_response
# ---------------------------------------------------------------------------

class ParseJsonResponseTest(TestCase):
    """Unit tests for the JSON parsing / normalisation helper."""

    def _valid_payload(self, **overrides):
        base = {
            "stage_guess": "bisque",
            "confidence": 0.85,
            "description": "This is my Mug at the bisque stage.",
            "glaze_notes": "",
        }
        base.update(overrides)
        return json.dumps(base)

    def test_parses_valid_json(self):
        result = _parse_json_response(self._valid_payload(), "Mug")
        self.assertEqual(result["stage_guess"], "bisque")
        self.assertAlmostEqual(result["confidence"], 0.85)
        self.assertEqual(result["description"], "This is my Mug at the bisque stage.")
        self.assertEqual(result["glaze_notes"], "")

    def test_strips_markdown_code_fences(self):
        """Claude sometimes wraps JSON in ```json … ``` — the parser must strip that."""
        wrapped = f"```json\n{self._valid_payload()}\n```"
        result = _parse_json_response(wrapped, "Mug")
        self.assertEqual(result["stage_guess"], "bisque")

    def test_strips_plain_code_fences(self):
        wrapped = f"```\n{self._valid_payload()}\n```"
        result = _parse_json_response(wrapped, "Mug")
        self.assertEqual(result["stage_guess"], "bisque")

    def test_unknown_stage_defaults_to_greenware(self):
        payload = self._valid_payload(stage_guess="raku")
        result = _parse_json_response(payload, "Mug")
        self.assertEqual(result["stage_guess"], "greenware")

    def test_stage_is_case_insensitive(self):
        """'BISQUE' should be normalised to 'bisque'."""
        payload = self._valid_payload(stage_guess="BISQUE")
        result = _parse_json_response(payload, "Mug")
        self.assertEqual(result["stage_guess"], "bisque")

    def test_confidence_clamped_above_one(self):
        payload = self._valid_payload(confidence=1.5)
        result = _parse_json_response(payload, "Mug")
        self.assertEqual(result["confidence"], 1.0)

    def test_confidence_clamped_below_zero(self):
        payload = self._valid_payload(confidence=-0.2)
        result = _parse_json_response(payload, "Mug")
        self.assertEqual(result["confidence"], 0.0)

    def test_missing_description_uses_fallback(self):
        payload = self._valid_payload(description="")
        result = _parse_json_response(payload, "My Mug")
        self.assertIn("My Mug", result["description"])

    def test_glaze_notes_cleared_for_non_glaze_stage(self):
        """glaze_notes should be empty string when stage is not 'glaze'."""
        payload = self._valid_payload(stage_guess="bisque", glaze_notes="Some glaze text")
        result = _parse_json_response(payload, "Mug")
        self.assertEqual(result["glaze_notes"], "")

    def test_glaze_notes_preserved_for_glaze_stage(self):
        payload = self._valid_payload(
            stage_guess="glaze",
            glaze_notes="Golden Hour yellow on the body.",
        )
        result = _parse_json_response(payload, "Mug")
        self.assertEqual(result["glaze_notes"], "Golden Hour yellow on the body.")

    def test_raises_on_no_json_object(self):
        """Should raise ValueError when there is no JSON object in the text."""
        with self.assertRaises(ValueError):
            _parse_json_response("No JSON here at all", "Mug")


# ---------------------------------------------------------------------------
# analyze_ceramic_image — integration with Anthropic client
# ---------------------------------------------------------------------------

class AnalyzeCeramicImageTest(TestCase):
    """Tests for the top-level analyze function."""

    FAKE_IMAGE = b"\xff\xd8\xff\xe0fake_jpeg_bytes"  # not a real image; API is mocked

    def _mock_response(self, payload: dict):
        """Build a mock Anthropic message whose .content[0].text is JSON."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(payload))]
        return mock_msg

    # ── No API key ────────────────────────────────────────────────────────────

    @override_settings(ANTHROPIC_API_KEY="")
    def test_returns_fallback_when_no_api_key(self):
        """When ANTHROPIC_API_KEY is empty the function must not call the API."""
        result = analyze_ceramic_image(self.FAKE_IMAGE, "Mug")
        self.assertIsNotNone(result["error"])
        self.assertIn("ANTHROPIC_API_KEY", result["error"])
        self.assertEqual(result["stage_guess"], "greenware")  # safe fallback

    # ── Happy path ────────────────────────────────────────────────────────────

    @override_settings(ANTHROPIC_API_KEY="sk-test-key")
    @patch("ceramics.ai_service.anthropic.Anthropic")
    def test_returns_parsed_result_on_success(self, MockAnthropic):
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._mock_response({
            "stage_guess": "bisque",
            "confidence": 0.92,
            "description": "This is my Mug at the bisque stage.",
            "glaze_notes": "",
        })

        result = analyze_ceramic_image(self.FAKE_IMAGE, "Mug")

        self.assertEqual(result["stage_guess"], "bisque")
        self.assertAlmostEqual(result["confidence"], 0.92)
        self.assertIsNone(result["error"])

    @override_settings(ANTHROPIC_API_KEY="sk-test-key")
    @patch("ceramics.ai_service.anthropic.Anthropic")
    def test_passes_base64_image_to_api(self, MockAnthropic):
        """The function must encode the image as base64 and include it in the request."""
        import base64
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._mock_response({
            "stage_guess": "greenware", "confidence": 0.7,
            "description": "desc", "glaze_notes": "",
        })

        analyze_ceramic_image(self.FAKE_IMAGE, "Mug", media_type="image/jpeg")

        call_kwargs = mock_client.messages.create.call_args
        messages_arg = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][1]
        image_content = messages_arg[0]["content"][0]
        self.assertEqual(image_content["type"], "image")
        expected_b64 = base64.standard_b64encode(self.FAKE_IMAGE).decode()
        self.assertEqual(image_content["source"]["data"], expected_b64)

    @override_settings(ANTHROPIC_API_KEY="sk-test-key")
    @patch("ceramics.ai_service.anthropic.Anthropic")
    def test_passes_piece_title_in_prompt(self, MockAnthropic):
        """The piece title must appear in the text prompt sent to Claude."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._mock_response({
            "stage_guess": "greenware", "confidence": 0.7,
            "description": "desc", "glaze_notes": "",
        })

        analyze_ceramic_image(self.FAKE_IMAGE, "My Special Teapot")

        call_kwargs = mock_client.messages.create.call_args
        messages_arg = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][1]
        text_content = messages_arg[0]["content"][1]["text"]
        self.assertIn("My Special Teapot", text_content)

    # ── Error paths ───────────────────────────────────────────────────────────

    @override_settings(ANTHROPIC_API_KEY="sk-test-key")
    @patch("ceramics.ai_service.anthropic.Anthropic")
    def test_returns_fallback_on_api_error(self, MockAnthropic):
        """An Anthropic API error must return the fallback dict with error set."""
        import anthropic as _anthropic
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.side_effect = _anthropic.APIError(
            message="rate limited", request=MagicMock(), body=None
        )

        result = analyze_ceramic_image(self.FAKE_IMAGE, "Mug")

        self.assertIsNotNone(result["error"])
        self.assertIn("AI service error", result["error"])
        self.assertEqual(result["stage_guess"], "greenware")

    @override_settings(ANTHROPIC_API_KEY="sk-test-key")
    @patch("ceramics.ai_service.anthropic.Anthropic")
    def test_returns_fallback_on_unexpected_exception(self, MockAnthropic):
        """Any unexpected exception must be caught and return the fallback."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_client.messages.create.side_effect = RuntimeError("unexpected!")

        result = analyze_ceramic_image(self.FAKE_IMAGE, "Mug")

        self.assertIsNotNone(result["error"])
        self.assertEqual(result["stage_guess"], "greenware")

    @override_settings(ANTHROPIC_API_KEY="sk-test-key")
    @patch("ceramics.ai_service.anthropic.Anthropic")
    def test_returns_fallback_on_malformed_json(self, MockAnthropic):
        """If Claude returns non-JSON text the function must not raise."""
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Sorry, I cannot analyse this image.")]
        mock_client.messages.create.return_value = mock_msg

        result = analyze_ceramic_image(self.FAKE_IMAGE, "Mug")

        self.assertIsNotNone(result["error"])
