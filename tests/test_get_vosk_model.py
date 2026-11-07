"""The speech-model downloader, tested with a local zip (no internet needed)."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "get_vosk_model.py"
spec = importlib.util.spec_from_file_location("get_vosk_model", TOOL)
gvm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gvm)


def make_zip(path, entries):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return Path(path).as_uri()


class TestGetVoskModel(unittest.TestCase):
    def test_installs_the_model_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = make_zip(Path(tmp) / "m.zip", {f"{gvm.NAME}/am/final.mdl": "x", f"{gvm.NAME}/README": "y"})
            models = Path(tmp) / "models"
            target = gvm.install(url, models)
            self.assertEqual(target, models / gvm.NAME)
            self.assertTrue((target / "am" / "final.mdl").exists())

    def test_does_nothing_if_already_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            models = Path(tmp) / "models"
            (models / gvm.NAME).mkdir(parents=True)
            (models / gvm.NAME / "keep.txt").write_text("mine")
            gvm.install("file:///this/would/fail/if/used.zip", models)          # must not even try to download
            self.assertEqual((models / gvm.NAME / "keep.txt").read_text(), "mine")

    def test_rejects_a_zip_without_the_model_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = make_zip(Path(tmp) / "m.zip", {"something_else/file": "x"})
            with self.assertRaises(RuntimeError):
                gvm.install(url, Path(tmp) / "models")
            self.assertFalse((Path(tmp) / "models" / gvm.NAME).exists())

    def test_rejects_paths_that_escape_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = make_zip(Path(tmp) / "m.zip", {"../evil.txt": "x", f"{gvm.NAME}/a": "y"})
            with self.assertRaises(RuntimeError):
                gvm.install(url, Path(tmp) / "models")
            self.assertFalse((Path(tmp) / "evil.txt").exists())


if __name__ == "__main__":
    unittest.main()
