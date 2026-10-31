"""Frame pacing, a tiny performance meter, an always-on LAG RECORDER (lag_log.txt) and start-up tuning."""
import functools
import gc
import sys
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "lag_log.txt"


class FrameGovernor:
    """60 fps while anything moves, 30 fps when he's calm. Needs `calm_after` seconds of calm to
    drop down (so it never flaps), and goes back to smooth instantly when something starts."""

    def __init__(self, active_ms=16, calm_ms=33, calm_after=0.6):
        self.active_ms, self.calm_ms, self.calm_after = active_ms, calm_ms, calm_after
        self.interval = active_ms
        self._calm_since = None

    def update(self, calm, now):
        """Returns the new interval in ms if it should change, else None."""
        if not calm:
            self._calm_since = None
            want = self.active_ms
        else:
            if self._calm_since is None:
                self._calm_since = now
            want = self.calm_ms if now - self._calm_since >= self.calm_after else self.interval
        if want != self.interval:
            self.interval = want
            return want
        return None


class PerfMeter:
    """Collects per-frame cost (ms). report() gives a one-line summary every `every` seconds."""

    def __init__(self, every=5.0):
        self.every, self._t0 = every, None
        self._n, self._sum, self._max, self._slow = 0, 0.0, 0.0, 0

    def add(self, ms, now):
        if self._t0 is None:
            self._t0 = now
        self._n += 1
        self._sum += ms
        self._max = max(self._max, ms)
        self._slow += ms > 16
        if now - self._t0 >= self.every:
            line = (f"[perf] {self._n / (now - self._t0):.0f} fps, frame cost avg {self._sum / self._n:.1f} ms, "
                    f"worst {self._max:.0f} ms, {self._slow} frames over 16 ms")
            self._t0, self._n, self._sum, self._max, self._slow = now, 0, 0.0, 0.0, 0
            return line
        return None


class SpikeLog:
    """Always on, almost free. Whenever a frame stalls it appends ONE line to lag_log.txt saying WHERE the time went:
      inputs / logic / physics / anim / sfx / frame-end = parts of our own frame, paint = drawing, and
      'outside' = time that wasn't ours (another timer handler, a background thread holding Python, the CPU
      being used up by another program such as the AI model, or Windows compositing)."""

    def __init__(self, path=LOG):
        self.path, self._last, self._burst = Path(path), -9.0, 0

    def frame(self, gap_ms, interval_ms, parts, paint_ms, now):
        ours = sum(parts.values()) + paint_ms
        late = gap_ms - interval_ms
        if late < 35 and ours < 25:
            return None
        outside = max(0.0, gap_ms - ours)
        if ours >= 25:
            top = max(list(parts.items()) + [("paint", paint_ms)], key=lambda kv: kv[1])
            why = f"OUR FRAME was slow: mostly '{top[0]}' ({top[1]:.0f} ms)"
        else:
            why = "stall OUTSIDE our frame (other timer handler / background thread / CPU starved by another program)"
        detail = " ".join(f"{k} {v:.1f}" for k, v in parts.items())
        return self._write(f"frame gap {gap_ms:.0f} ms (wanted {interval_ms}) | ours {ours:.0f} ms, outside {outside:.0f} ms"
                           f" | {detail} paint {paint_ms:.1f} | {why}", now)

    def note(self, label, ms):
        if ms >= 15:
            return self._write(f"slow handler '{label}' took {ms:.0f} ms on the UI thread", time.monotonic())
        return None

    def _write(self, text, now):
        if now - self._last > 2.0:
            self._burst = 0
        self._last = now
        self._burst += 1
        if self._burst > 8:                       # a long stutter shouldn't flood the file
            return None
        line = time.strftime("%H:%M:%S  ") + text
        try:
            if self.path.exists() and self.path.stat().st_size > 200_000:
                text = self.path.read_text(encoding="utf-8", errors="ignore")[-100_000:]
                text = text[text.find("\n") + 1:] if "\n" in text else ""      # drop the cut-off first line
                self.path.write_text(text, encoding="utf-8")
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        return line


SPIKES = SpikeLog()


def timed(label):
    """Decorator: report a UI-thread handler to the lag recorder if it takes >= 15 ms."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                SPIKES.note(label, (time.perf_counter() - t0) * 1000)
        return wrapper
    return deco


def tune_runtime():
    """Once, at start-up: make the animation win against CPU hogs (the local AI model, background threads)."""
    sys.setswitchinterval(0.001)                  # background threads hand Python back to the UI within 1 ms, not 5
    try:
        from platforms import boost_priority
        boost_priority()                          # 'above normal' priority: the UI thread beats Ollama for the CPU
    except Exception:
        pass


def settle_memory():
    """After start-up: stop Python's garbage collector re-scanning everything we just loaded (Qt, numpy, the AI
    libraries). Those full scans were a source of random 20-60 ms freezes."""
    gc.collect()
    gc.freeze()
    gc.set_threshold(5000, 20, 20)
