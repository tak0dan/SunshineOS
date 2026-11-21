"""Tests for the one-shot terminal success animation."""
from __future__ import annotations

import importlib.util
import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PLAY = (Path(__file__).resolve().parents[1] / "profile" / "airootfs" / "usr" / "share"
        / "sunshine" / "logo-anim" / "play.py")


def load_play():
    spec = importlib.util.spec_from_file_location("sunshine_logo_play", PLAY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    with patch.object(sys, "argv", ["play.py", "--lite"]):
        spec.loader.exec_module(module)
    return module


class ToolAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.play = load_play()

    def test_tool_text_is_collapsed_and_bounded(self):
        self.assertEqual(self.play.fit_text("  System   updated  ", 15), "System updated")
        self.assertEqual(self.play.fit_text("System updated", 15), "System updated")
        bounded = self.play.fit_text("System updated successfully", 15)
        self.assertEqual(len(bounded), 15)
        self.assertTrue(bounded.endswith("…"))

    def test_small_terminals_get_a_shorter_bound(self):
        self.assertEqual(self.play.fit_text("Migration complete", 5), "Migr…")
        self.assertEqual(len(self.play.fit_text("Migration complete", 4)), 4)

    def test_tool_animation_is_one_shot(self):
        source = inspect.getsource(self.play.run_tool)
        self.assertNotIn("while True", source)
        self.assertNotIn("select.select", source)
        self.assertIn("draw_strip(end, 1.0, 1.0)", source)
        self.assertIn("midrow", source)

    def test_player_exposes_the_tool_options(self):
        text = PLAY.read_text()
        self.assertIn("--tool", text)
        self.assertIn("--max-text=", text)
        self.assertIn("--title=", text)


if __name__ == "__main__":
    unittest.main()
