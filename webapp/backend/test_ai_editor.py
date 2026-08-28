from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_editor import parse_ranges, validate_ranges


class AiEditorValidationTests(unittest.TestCase):
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
