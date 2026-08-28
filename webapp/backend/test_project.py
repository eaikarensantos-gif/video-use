from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project import Project


class ProjectSafetyTests(unittest.TestCase):
    def test_trash_is_recoverable_and_handles_special_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project(Path(tmp))
            source = Path(tmp) / "vídeo teste (1).mp4"
            source.write_bytes(b"original")
            trashed = project.trash_file(source)
            self.assertFalse(source.exists())
            self.assertEqual(trashed.read_bytes(), b"original")
            self.assertEqual(trashed.parent, project.edit_dir / "trash")

    def test_imported_images_are_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Project(Path(tmp))
            (Path(tmp) / "cover.jpg").write_bytes(b"image")
            (Path(tmp) / "ignore.txt").write_text("no")
            self.assertEqual([p.name for p in project.list_image_files()], ["cover.jpg"])


if __name__ == "__main__":
    unittest.main()
