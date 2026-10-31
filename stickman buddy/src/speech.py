"""
Text-to-speech: he can talk OUT LOUD. Uses Windows' built-in voices (SAPI) through pywin32, so there is nothing
extra to install and it works offline. It runs on its own thread: the animation never waits for speech.
Settings: speak (on/off), tts_rate (-10..10), tts_volume (0..100), tts_voice (name, '' = default).
"""
import queue
import re
import threading

from settings import SETTINGS


def clean(text, limit=220):
    """Drop emoji / symbols the voice would read out loud, collapse spaces, cap the length."""
    t = re.sub(r"[^\w\s.,!?'\-:;%&()]", " ", text or "")
    return re.sub(r"\s+", " ", t).strip()[:limit]


class Speaker:
    def __init__(self):
        self.speaking = False
        self.available = None            # None = not tried yet, False = no SAPI (not Windows / no pywin32)
        self.voices = []
        self._q = queue.Queue()
        self._thread = None
        self._purge = threading.Event()
        self._lock = threading.Lock()

    @property
    def busy(self):
        return self.available is not False and (self.speaking or not self._q.empty())

    def ensure_started(self):
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, daemon=True, name="tts")
                self._thread.start()

    def say(self, text, interrupt=False):
        """Queue speech. Explicit user/demo lines replace stale background chatter."""
        if not SETTINGS.get("speak", True) or self.available is False:
            return False
        text = clean(text)
        if not text:
            return False
        self.ensure_started()
        if interrupt and self.busy:
            self.stop()
        while self._q.qsize() >= 2:      # never build a backlog: he should talk about NOW
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self._q.put(text)
        return True

    def stop(self):
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self._purge.set()

    def _apply(self, voice):
        voice.Rate = int(max(-10, min(10, SETTINGS.get("tts_rate", 1))))
        voice.Volume = int(max(0, min(100, SETTINGS.get("tts_volume", 90))))
        want = SETTINGS.get("tts_voice", "")
        if want and want in self.voices:
            voice.Voice = voice.GetVoices().Item(self.voices.index(want))

    def _run(self):
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            found = voice.GetVoices()
            self.voices = [found.Item(i).GetDescription() for i in range(found.Count)]
        except Exception as e:
            self.available = False
            # Drop lines queued before a failed Windows voice initialization.
            while not self._q.empty():
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break
            print(f"[speech] text-to-speech unavailable: {e}")
            return
        self.available = True
        while True:
            text = self._q.get()
            try:
                self._apply(voice)
                self._purge.clear()
                self.speaking = True
                voice.Speak(text, 1)                         # 1 = asynchronous, so we can interrupt it
                while not voice.WaitUntilDone(80):
                    if self._purge.is_set():
                        voice.Speak("", 3)                   # 3 = async + purge what's playing
                        break
            except Exception as e:
                print(f"[speech] {e}")
            finally:
                self.speaking = False
