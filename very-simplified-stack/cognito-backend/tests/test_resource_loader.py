import os
import unittest
import tempfile
import logging
from pathlib import Path

from app.core.resource_loader import ResourceLoader


class TestResourceLoader(unittest.TestCase):
    def test_discover_agents_md_recursive_and_precedence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            root_agents = tmp_path / "AGENTS.md"
            root_agents.write_text("Root instructions")

            sub_dir = tmp_path / "subdir" / "nested"
            sub_dir.mkdir(parents=True)

            nested_agents = sub_dir / "AGENTS.md"
            nested_agents.write_text("Nested instructions")

            loader = ResourceLoader(str(sub_dir))
            content = loader.discover_agents_md()

            # Precedence check: root instructions first, nested instructions last (preceding position in concatenated prompt context)
            self.assertIn("Root instructions", content)
            self.assertIn("Nested instructions", content)
            self.assertTrue(content.index("Root instructions") < content.index("Nested instructions"))

            # Discovered files list order
            files = loader.discover_agents_md_files()
            self.assertEqual(len(files), 2)
            self.assertEqual(files[0], str(root_agents.resolve()))
            self.assertEqual(files[1], str(nested_agents.resolve()))

    def test_discover_agents_md_malformed_file_handling(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            root_agents = tmp_path / "AGENTS.md"
            root_agents.write_text("Root valid instructions")

            sub_dir = tmp_path / "child"
            sub_dir.mkdir()

            malformed_agents = sub_dir / "AGENTS.md"
            # Write non-utf8 binary data to cause UnicodeDecodeError on text read
            malformed_agents.write_bytes(b"\x80\x81\xff\xfe invalid unicode")

            loader = ResourceLoader(str(sub_dir))
            with self.assertLogs("app.core.resource_loader", level="WARNING") as cm:
                content = loader.discover_agents_md()

            # Startup/discovery does not crash and returns the valid instructions
            self.assertIn("Root valid instructions", content)
            self.assertTrue(any("Error reading AGENTS.md" in log for log in cm.output))

    def test_get_effective_protected_files_with_nested_agents_md(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            sub_dir = tmp_path / "sub"
            sub_dir.mkdir()

            agents_file = sub_dir / "AGENTS.md"
            agents_file.write_text("- `secret_config.json` (protected)")

            loader = ResourceLoader(str(sub_dir))
            protected = loader.get_effective_protected_files()

            self.assertIn("secret_config.json", protected)


if __name__ == "__main__":
    unittest.main()
