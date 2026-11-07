"""Every effect must exist on a fresh clone, even with no GIF files in assets/gifs."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@unittest.skipUnless(importlib.util.find_spec("PyQt6"), "PyQt6 not installed")
class TestEffects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_every_effect_has_built_in_art_or_a_gif(self):
        import fx_art
        import gifs
        for name in gifs.FX:
            self.assertTrue(name in fx_art.BUILDERS or (gifs.GIF_DIR / f"{name}.gif").exists(), name)

    def test_built_in_art_draws_something_visible(self):
        import fx_art
        for name in fx_art.BUILDERS:
            frames = fx_art.build(name)
            self.assertGreater(len(frames), 3, name)
            visible = False
            for pm, delay in frames:
                self.assertGreater(delay, 0)
                img = pm.toImage()
                if any(img.pixelColor(x, y).alpha() > 0 for x in range(0, pm.width(), 8) for y in range(0, pm.height(), 8)):
                    visible = True
            self.assertTrue(visible, f"{name} drew nothing")

    def test_fresh_clone_has_all_effects_with_no_gif_files(self):
        import gifs
        with tempfile.TemporaryDirectory() as empty:
            layer = gifs.GifLayer(folder=empty)
            missing = [n for n in gifs.FX if not layer.has(n)]
            self.assertEqual(missing, [])

    def test_a_gif_file_overrides_the_built_in_art(self):
        """Drop a GIF named after an effect into the folder: it must win over the built-in drawing."""
        import shutil
        import fx_art
        import gifs
        shipped = gifs.GIF_DIR / "heart.gif"
        self.assertTrue(shipped.exists(), "the repo ships heart.gif")
        with tempfile.TemporaryDirectory() as folder:
            shutil.copy(shipped, Path(folder) / "impact.gif")        # pretend the user supplied their own impact.gif
            mine = gifs.GifLayer(folder=folder).frames("impact")
            built_in = fx_art.build("impact")
            self.assertEqual(len(mine), len(gifs.GifLayer().frames("heart")))       # it IS the user's GIF...
            self.assertNotEqual((len(mine), mine[0][0].width()),
                                (len(built_in), built_in[0][0].width()))              # ...not the drawing

if __name__ == "__main__":
    unittest.main()
