from __future__ import annotations

import unittest
from unittest.mock import patch

from updater import _version_tuple, check_for_update


class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, *_args):
        return self.payload


class UpdaterTests(unittest.TestCase):
    def test_semantic_version_comparison(self):
        self.assertGreater(_version_tuple("v0.2.0"), _version_tuple("0.1.9"))
        self.assertEqual(_version_tuple("0.2.0"), (0, 2, 0))

    @patch("urllib.request.urlopen")
    def test_finds_expected_release_asset(self, urlopen):
        urlopen.return_value = _Response(
            b'{"tag_name":"v9.0.0","name":"Nine","body":"notes","assets":['
            b'{"name":"video-use-setup.exe","browser_download_url":"https://example.invalid/setup.exe",'
            b'"size":1234,"digest":"sha256:abc"}]}'
        )
        result = check_for_update()
        self.assertTrue(result["available"])
        self.assertEqual(result["latest_version"], "9.0.0")
        self.assertEqual(result["digest"], "sha256:abc")


if __name__ == "__main__":
    unittest.main()
