"""
Voice commands for scrolling short videos ("up" / "go back").

PRIVACY: recognition is fully OFFLINE (Vosk). Your voice is processed on your PC and no audio is
ever sent anywhere. The mic is only opened while "Voice commands" is ticked in the tray menu
(it starts OFF), and nothing is recorded or saved.

One-time setup:
    pip install vosk sounddevice
    Download "vosk-model-small-en-us-0.15" (about 40 MB) from https://alphacephei.com/vosk/models
    and unzip it so this folder exists:   <project>/models/vosk-model-small-en-us-0.15
Then tick "Voice commands (microphone)" in the tray menu.

Say:   "up", "next", "skip"          -> next video   (what swiping UP does)
       "back", "go back", "down"     -> previous video
(or "buddy up" / "hey go back" if you turn on "Voice: say 'buddy' first")

Tips:
  * Use headphones. With speakers on, the mic can hear the video itself, and a video that happens
    to say "next" could set him off. To make accidental triggers rarer he only reacts when the
    WHOLE sentence is a command and the recogniser is confident (VOICE_MIN_CONF in settings.py).
  * He has a 1-second cool-down between commands.
"""
import json
import queue
import os
import threading
import time
from pathlib import Path

import settings
from settings import SETTINGS

RATE = 16000
MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "vosk-model-small-en-us-0.15"


def mic_device():
    """Which microphone to record from.

    By default this is None, which means "the Windows default recording device", so it works on any PC.
    To pick a different one, set STICKMAN_MIC_DEVICE to a device number or to part of its name, e.g. in
    PowerShell:  $env:STICKMAN_MIC_DEVICE = "15"    (list your devices with:  python -m sounddevice)
    """
    raw = os.environ.get("STICKMAN_MIC_DEVICE", "").strip()
    if not raw:
        return None
    return int(raw) if raw.lstrip("-").isdigit() else raw

# whole phrase -> action. "up" = swipe up = NEXT video.
PHRASES = {
    "up": "short_next", "next": "short_next", "skip": "short_next",
    "go up": "short_next", "scroll up": "short_next", "swipe up": "short_next",
    "back": "short_back", "go back": "short_back", "previous": "short_back",
    "down": "short_back", "go down": "short_back",
}
WAKE_WORDS = ("buddy", "hey")
# Vosk only listens for THESE words (plus [unk] for "anything else"), which is far more accurate
# than open dictation and keeps CPU use tiny.
GRAMMAR = sorted({w for phrase in PHRASES for w in phrase.split()} | set(WAKE_WORDS)) + ["[unk]"]


def parse_voice(text, needs_wake=False):
    """'go back' -> 'short_back'.  Anything that isn't EXACTLY a command -> None."""
    words = (text or "").lower().split()
    if not words or "[unk]" in words:        # any unrecognised word = probably not for us
        return None
    woke = False
    while words and words[0] in WAKE_WORDS:
        words = words[1:]
        woke = True
    if needs_wake and not woke:
        return None
    return PHRASES.get(" ".join(words))


def accept_result(result_json, min_conf=None, needs_wake=False):
    """Vosk's final-result JSON -> action name, or None if it's not a confident, exact command."""
    min_conf = settings.VOICE_MIN_CONF if min_conf is None else min_conf
    try:
        data = json.loads(result_json)
    except Exception:
        return None
    action = parse_voice(data.get("text", ""), needs_wake)
    if not action:
        return None
    confs = [w.get("conf", 1.0) for w in data.get("result", []) if isinstance(w, dict)]
    if confs and sum(confs) / len(confs) < min_conf:
        return None
    return action


class VoiceSetupError(Exception):
    pass


class VoiceListener(threading.Thread):
    """Background thread. on_command(action) / on_status(message, fatal) are called FROM THIS THREAD:
    the caller must hand them to the UI thread (main.py does that through its Bridge)."""

    def __init__(self, on_command, on_status=None, model_dir=MODEL_DIR):
        super().__init__(daemon=True, name="voice")
        self.on_command = on_command
        self.on_status = on_status or (lambda message, fatal=False: None)
        self.model_dir = Path(model_dir)
        self._model = None
        self._halt = threading.Event()
        self._last = 0.0

    def stop(self):
        self._halt.set()

    def run(self):
        while not self._halt.is_set():
            if not SETTINGS.get("voice"):               # mic stays CLOSED unless you turned it on
                self._halt.wait(0.4)
                continue
            try:
                self._listen()
            except VoiceSetupError as e:
                SETTINGS["voice"] = False
                self.on_status(str(e), True)
            except Exception as e:                      # no mic, device busy, ...
                SETTINGS["voice"] = False
                self.on_status(f"Voice stopped: {e}", True)

    def _listen(self):
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model, SetLogLevel
        except ImportError:
            raise VoiceSetupError("Voice needs: pip install vosk sounddevice")
        if self._model is None:
            if not self.model_dir.exists():
                raise VoiceSetupError(
                    f"Voice model missing. Unzip vosk-model-small-en-us-0.15 into {self.model_dir.parent}")
            SetLogLevel(-1)
            self.on_status("Putting my ears on...", False)
            self._model = Model(str(self.model_dir))
        rec = KaldiRecognizer(self._model, RATE, json.dumps(GRAMMAR))
        rec.SetWords(True)
        audio = queue.Queue(maxsize=64)

        def callback(indata, frames, time_info, status):
            try:
                audio.put_nowait(bytes(indata))
            except queue.Full:                          # we fell behind: drop audio rather than lag
                pass

        with sd.RawInputStream(samplerate=RATE, blocksize=4000, dtype="int16",
                               channels=1, device=mic_device(), callback=callback):
            self.on_status("I'm listening! Say 'up' or 'go back'.", False)
            while SETTINGS.get("voice") and not self._halt.is_set():
                try:
                    data = audio.get(timeout=0.3)
                except queue.Empty:
                    continue
                if rec.AcceptWaveform(data):
                    self._handle(rec.Result())

    def _handle(self, result_json):
        action = accept_result(result_json, needs_wake=SETTINGS.get("voice_needs_name", False))
        now = time.monotonic()
        if action and now - self._last > 1.0:           # cool-down: one command per second at most
            self._last = now
            self.on_command(action)
