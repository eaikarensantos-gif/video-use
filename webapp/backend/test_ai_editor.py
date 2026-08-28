from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_editor import build_prompt, configured_provider, parse_ranges, parse_text_overlays, validate_ranges


class AiEditorValidationTests(unittest.TestCase):
    def test_parses_structured_openai_response(self):
        ranges = parse_ranges('{"cuts":[{"source":"a","start":0,"end":1,"beat":"intro","reason":"clear"}]}')
        self.assertEqual(ranges[0]["source"], "a")

    @patch("ai_editor.load_env_value")
    def test_openai_is_preferred_when_both_keys_exist(self, load_value):
        values = {"OPENAI_API_KEY": "openai-key", "OPENAI_MODEL": "", "ANTHROPIC_API_KEY": "anthropic-key"}
        load_value.side_effect = lambda name: values.get(name, "")
        status = configured_provider()
        self.assertEqual(status["provider"], "openai")
        self.assertEqual(status["model"], "gpt-5.4-mini")

    def test_visual_request_plan_can_contain_text_without_cuts(self):
        payload = json.dumps({"cuts": [], "text_overlays": [{
            "text": "home office", "start": 12, "duration": 3, "position": "center",
            "font_size": 64, "color": "white", "background": False, "reason": "requested text",
        }]})
        self.assertEqual(parse_ranges(payload), [])
        overlays = parse_text_overlays(payload, timeline_duration=30)
        self.assertEqual(overlays[0]["text"], "home office")
        self.assertEqual(overlays[0]["start"], 12)

    def test_prompt_includes_playhead_and_visual_routing_rule(self):
        prompt = build_prompt("none", "escreva home office na tela", None, playhead=8.5, timeline_duration=20)
        self.assertIn("Current playhead: 8.50", prompt)
        self.assertIn("Do not propose cuts for a visual-only request", prompt)

    def test_rejects_invalid_time_range(self):
        with self.assertRaises(RuntimeError):
            parse_ranges('[{"source":"a","start":3,"end":2}]')

    def test_rejects_unknown_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "known.json").write_text(json.dumps({"words": [{"end": 5.0}]}))
            with self.assertRaisesRegex(RuntimeError, "unknown source"):
                validate_ranges([{"source": "invented", "start": 0, "end": 1}], folder)

    def test_rejects_timestamp_past_source_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "known.json").write_text(json.dumps({"words": [{"end": 5.0}]}))
            with self.assertRaisesRegex(RuntimeError, "outside"):
                validate_ranges([{"source": "known", "start": 4, "end": 8}], folder)


if __name__ == "__main__":
    unittest.main()
