import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from focus import FocusPreset, FOCUS_OVERRIDES


class TestFocusPreset(unittest.TestCase):
    def test_restore_preferences_and_idempotency(self):
        original = {k: True for k in FOCUS_OVERRIDES}
        original["chat_level"] = 2
        original["skip_songs"] = False
        settings = dict(original)
        settings["unrelated"] = "unchanged"
        mode = FocusPreset(settings)
        self.assertTrue(mode.set_active(True))
        self.assertTrue(mode.active)
        self.assertFalse(settings["ai_director"])
        self.assertEqual(settings["chat_level"], 0)
        self.assertFalse(mode.set_active(True))
        self.assertTrue(mode.set_active(False))
        self.assertEqual(settings, {**original, "unrelated": "unchanged"})
        self.assertFalse(mode.active)
        self.assertFalse(mode.set_active(False))


if __name__ == "__main__":
    unittest.main()
