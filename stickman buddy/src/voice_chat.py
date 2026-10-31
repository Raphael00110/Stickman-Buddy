
"""Push-to-talk offline speech-to-text for talking to the AI.

Records one short sentence when Ctrl+Alt+V or the tray action is used.
Audio stays local; only recognized text is forwarded to the configured AI.
"""
import json
import threading
import time

from voice import MODEL_DIR, RATE

MIC_DEVICE = 15  # Wave Pro Hands-Free microphone (DirectSound)


def extract_text(result_json):
    """Extract Vosk recognized words without exposing metadata."""
    try:
        return str(json.loads(result_json).get("text", "")).strip()
    except (TypeError, ValueError, AttributeError):
        return ""


class VoiceChat:
    """One-shot microphone worker; callbacks run on a background thread."""

    def __init__(self, on_text, on_status, model_dir=MODEL_DIR):
        self.on_text = on_text
        self.on_status = on_status
        self.model_dir = model_dir
        self.busy = False
        self._lock = threading.Lock()
        self._model = None

    def listen_once(self, delay=0.0):
        """Start recording; return False if a recording is in progress."""
        with self._lock:
            if self.busy:
                return False
            self.busy = True
        threading.Thread(
            target=self._listen, args=(delay,), daemon=True, name="voice-chat"
        ).start()
        return True

    def _listen(self, delay):
        try:
            if delay:
                time.sleep(delay)
            try:
                import sounddevice as sd
                import numpy as np
                from vosk import KaldiRecognizer, Model, SetLogLevel
            except ImportError as exc:
                raise RuntimeError(
                    "Install voice input: pip install vosk sounddevice numpy"
                ) from exc

            if not self.model_dir.exists():
                raise RuntimeError("Voice model missing. See models/README.txt")

            if self._model is None:
                self.on_status("Loading offline microphone model (first time only)...")
                SetLogLevel(-1)
                self._model = Model(str(self.model_dir))

            recognizer = KaldiRecognizer(self._model, RATE)
            self.on_status("Listening for up to 7 seconds. Say your question now...")
            parts = []
            deadline = time.monotonic() + 7.0
            peak = 0.0

            with sd.RawInputStream(
                samplerate=RATE,
                blocksize=3200,
                dtype="int16",
                channels=1,
                device=MIC_DEVICE,
            ) as stream:
                while time.monotonic() < deadline:
                    data, overflow = stream.read(3200)
                    samples = np.frombuffer(data, dtype=np.int16)
                    if samples.size:
                        volume = float(np.max(np.abs(samples.astype(np.float32)))) / 32768.0
                        peak = max(peak, volume)
                        print(f"[MIC DEBUG] Volume: {volume:.4f}")
                    if overflow:
                        print("[MIC DEBUG] Audio buffer overflow")

                    if recognizer.AcceptWaveform(bytes(data)):
                        phrase = extract_text(recognizer.Result())
                        if phrase:
                            parts.append(phrase)
                            break

                # FinalResult must be called AFTER recording, not inside the loop.
                print("[VOSK DEBUG] Partial:", recognizer.PartialResult())
                final = extract_text(recognizer.FinalResult())
                print("[VOSK DEBUG] Final:", repr(final))

                if final and not parts:
                    parts.append(final)

            print(f"[MIC DEBUG] Peak volume: {peak:.4f}")
            result = " ".join(parts).strip()
            if result:
                self.on_text(result)
            else:
                self.on_status("I didn't catch that. Try Ctrl+Alt+V again.")
        except Exception as exc:
            self.on_status(f"Microphone unavailable: {exc}")
        finally:
            with self._lock:
                self.busy = False