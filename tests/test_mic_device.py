"""Microphone selection and voice-chat behaviour, tested with a fake microphone (no hardware needed)."""
import contextlib
import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import voice
import voice_chat

try:
    import numpy as np
except ImportError:                        # the voice-chat tests need numpy; the parsing tests below don't
    np = None


class TestMicDevice(unittest.TestCase):
    def test_default_is_the_system_default_device(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("STICKMAN_MIC_DEVICE", None)
            self.assertIsNone(voice.mic_device())

    def test_number_name_and_blank(self):
        for raw, expected in (("15", 15), (" 3 ", 3), ("Wave Pro", "Wave Pro"), ("", None), ("   ", None)):
            with mock.patch.dict(os.environ, {"STICKMAN_MIC_DEVICE": raw}):
                self.assertEqual(voice.mic_device(), expected, repr(raw))


@unittest.skipIf(np is None, "numpy not installed")
class TestVoiceChat(unittest.TestCase):
    """Runs the real VoiceChat worker against a fake sounddevice + fake Vosk."""

    def _run(self, block, final_text="", stream_error=None, env=None):
        seen = {}
        sd = types.ModuleType("sounddevice")

        class RawInputStream:
            def __init__(self, **kw):
                if stream_error:
                    raise stream_error
                seen.update(kw)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n):
                return block, False

        sd.RawInputStream = RawInputStream
        vosk = types.ModuleType("vosk")

        class Model:
            def __init__(self, path):
                pass

        class KaldiRecognizer:
            def __init__(self, model, rate):
                pass

            def AcceptWaveform(self, data):
                return False

            def Result(self):
                return "{}"

            def FinalResult(self):
                return '{"text": "%s"}' % final_text

        vosk.Model, vosk.KaldiRecognizer, vosk.SetLogLevel = Model, KaldiRecognizer, lambda level: None

        ticks = iter(x * 0.5 for x in range(10000))      # fake clock: 0.5 s per call, so the 7 s recording is instant
        fake_time = types.SimpleNamespace(monotonic=lambda: next(ticks), sleep=lambda s: None)
        statuses, texts, out = [], [], io.StringIO()
        with tempfile.TemporaryDirectory() as model_dir, \
                mock.patch.dict(sys.modules, {"sounddevice": sd, "vosk": vosk}), \
                mock.patch.dict(os.environ, env or {}), \
                mock.patch.object(voice_chat, "time", fake_time), \
                contextlib.redirect_stdout(out):
            if not env:
                os.environ.pop("STICKMAN_MIC_DEVICE", None)
            chat = voice_chat.VoiceChat(texts.append, statuses.append, model_dir=Path(model_dir))
            chat._listen(0.0)
        return seen, statuses, texts, out.getvalue()

    def test_uses_the_default_microphone(self):
        seen, _, _, _ = self._run(np.zeros(3200, dtype=np.int16).tobytes())
        self.assertIn("device", seen)
        self.assertIsNone(seen["device"], "must not hardcode a device index")

    def test_env_var_selects_the_microphone(self):
        seen, _, _, _ = self._run(np.zeros(3200, dtype=np.int16).tobytes(), env={"STICKMAN_MIC_DEVICE": "15"})
        self.assertEqual(seen["device"], 15)

    def test_silent_mic_explains_what_to_do(self):
        _, statuses, texts, _ = self._run(np.zeros(3200, dtype=np.int16).tobytes())
        self.assertEqual(texts, [])
        self.assertIn("couldn't hear anything", statuses[-1])
        self.assertIn("STICKMAN_MIC_DEVICE", statuses[-1])

    def test_recognised_speech_is_forwarded(self):
        loud = (np.ones(3200, dtype=np.int16) * 8000).tobytes()
        _, statuses, texts, _ = self._run(loud, final_text="hello buddy")
        self.assertEqual(texts, ["hello buddy"])

    def test_unavailable_device_gives_a_helpful_message(self):
        _, statuses, texts, _ = self._run(b"", stream_error=OSError("Invalid device"))
        self.assertEqual(texts, [])
        self.assertIn("Microphone unavailable", statuses[-1])
        self.assertIn("STICKMAN_MIC_DEVICE", statuses[-1])

    def test_no_debug_spam_on_the_console(self):
        loud = (np.ones(3200, dtype=np.int16) * 8000).tobytes()
        _, _, _, console = self._run(loud, final_text="hi")
        self.assertNotIn("DEBUG", console)


if __name__ == "__main__":
    unittest.main()
