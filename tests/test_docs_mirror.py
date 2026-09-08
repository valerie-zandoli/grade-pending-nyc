"""Checks that docs/README.md stays an exact copy of README.md.

Vercel's static deploy silently excludes a root-level README.md from what
it actually serves (confirmed empirically: every case variant of
/README.md 404s in production, while an identical file one directory down
serves fine) -- it treats that specific root filename as project metadata,
not a servable asset. docs/README.md exists only so the two in-site links
that point readers to the write-up (index.html's Contents list,
live-check.html's cold-read paragraph) resolve to something real. This
test is the guard against the two drifting apart after an edit to one and
not the other.

Run with: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestDocsReadmeMirror(unittest.TestCase):
    def test_docs_readme_matches_root_readme(self):
        root_readme = (ROOT / "README.md").read_text()
        docs_readme = (ROOT / "docs" / "README.md").read_text()
        self.assertEqual(
            root_readme,
            docs_readme,
            "docs/README.md has drifted from README.md -- copy README.md over "
            "docs/README.md (or vice versa, whichever has the correct content) "
            "and commit both together.",
        )
