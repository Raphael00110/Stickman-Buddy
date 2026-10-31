"""Pure-Python checks that run even when PyQt6/Windows is not installed."""
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from fun import SCENES, SAY_PRESETS, parse_script
from sound import BANKS, generate_all
from speech import Speaker
from voice_chat import extract_text


class TestDemoFeatures(unittest.TestCase):
    def test_judges_scenes_parse(self):
        for name in ('Hi Judges', 'Goodbye Judges', 'Coding moment'):
            self.assertIn(name, SCENES)
        self.assertIn('Goodbye judges', ' '.join(SAY_PRESETS))
        names = {'wave', 'code'}
        for name in ('Hi Judges', 'Goodbye Judges', 'Coding moment'):
            steps, errors = parse_script(SCENES[name], names, set(), set(), {'applause'})
            self.assertFalse(errors, errors)
            self.assertGreater(len(steps), 0)

    def test_sound_assets_are_valid_wav_files(self):
        self.assertIn('laugh', BANKS)
        self.assertIn('drumroll', BANKS)
        with tempfile.TemporaryDirectory() as td:
            written = generate_all(td)
            self.assertGreater(written, 2)
            for name in ('drumroll_0.wav', 'laugh_0.wav'):
                path = Path(td) / name
                with wave.open(str(path), 'rb') as audio:
                    self.assertEqual(audio.getnchannels(), 1)
                    self.assertGreater(audio.getnframes(), 10000)
                    raw = audio.readframes(audio.getnframes())
                self.assertNotEqual(set(raw), {0})

    def test_voice_json(self):
        self.assertEqual(extract_text('{"text":"hello buddy"}'), 'hello buddy')
        self.assertEqual(extract_text('bad json'), '')
        self.assertEqual(extract_text('{}'), '')

    def test_speech_busy_does_not_stick_when_voice_unavailable(self):
        speech = Speaker()
        speech._q.put('queued sentence')
        speech.available = False
        self.assertFalse(speech.busy)


if __name__ == '__main__':
    unittest.main()
