"""Guards the things a judge hits first on a fresh clone: do the README commands point at real files,
does every doc agree on the AI model, and is the license present?"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class TestFreshClone(unittest.TestCase):
    def test_readme_commands_point_at_real_files(self):
        # README: pip install -r requirements.txt / python src/main.py / unittest discover -s tests
        for rel in ("README.md", "LICENSE", "requirements.txt", "src/main.py", "tests", "tools/mictest.py",
                    "tools/get_vosk_model.py", "tools/soundtest.py"):
            self.assertTrue((ROOT / rel).exists(), f"missing {rel}")

    def test_no_nested_project_folder(self):
        self.assertFalse((ROOT / "stickman buddy").exists(), "the project must live at the repo root")

    def test_every_doc_names_the_same_model(self):
        import settings
        pull = f"ollama pull {settings.LLAMA_MODEL}"
        for rel in ("README.md", "requirements.txt", "src/settings.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn(pull, text, f"{rel} should tell people to run: {pull}")

    def test_no_stale_model_names(self):
        stale = "llama" + "3.2"            # built from pieces so this file doesn't match itself
        for path in list(ROOT.glob("*.md")) + list(ROOT.glob("*.txt")) + list(ROOT.glob("src/*.py")):
            self.assertNotIn(stale, path.read_text(encoding="utf-8").lower().replace(" ", ""),
                             f"{path.name} still mentions the old model")

    def test_license_is_the_full_gpl3(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", text)
        self.assertIn("Version 3, 29 June 2007", text)
        self.assertGreater(len(text), 30000)


if __name__ == "__main__":
    unittest.main()
