"""
Cartoon sound layer for the stickman.

 * Every sound is SYNTHESISED the first time you run (squishy rubber steps,
   boings, whooshes, comic thumps...). Nothing to download, nothing copyrighted.
   They are written to assets/sfx/ as small WAV files.
 * Want different sounds? Drop your own WAVs in assets/sfx/ using the same names
   (e.g. step_walk_0.wav, step_walk_1.wav ... or just step_walk.wav). Existing
   files are never overwritten. Delete a file to get the built-in one back.
 * "Smart" parts (see SoundEngine):
     - footsteps are locked to his real gait: one sound per foot plant, left/right
       alternate in pitch, louder + squeakier when he runs, tiny when he sneaks
     - different surface sounds for the floor vs. the top of one of your windows
     - landings scale with how hard he fell; long falls get a cartoon whistle
     - he stays SILENT while you watch a video, is quieter while your music plays
       (and never dances "over" your song), and quieter late at night
     - random variants, never the same variant twice in a row, rate-limited so
       it can't turn into machine-gun noise

Needs:  pip install numpy      (PyQt6 already includes QtMultimedia)
Regenerate everything:  python sound.py --force
"""
import hashlib
import json
import math
import random
import shutil
import sys
import time
import wave
from pathlib import Path

import numpy as np

from settings import SETTINGS

SFX_DIR = Path(__file__).resolve().parent.parent / "assets" / "sfx"
SR = 22050


# =============================================================== synthesis kit
def _t(d):
    return np.arange(int(SR * d)) / SR


def _decay(d, rate):
    return np.exp(-rate * _t(d) / d)


def _phase(f):
    return 2 * np.pi * np.cumsum(f) / SR


def _sweep(f0, f1, d, curve=3.0, wobble=0.0, wob_hz=0.0, harm=0.0):
    """Pitch glides f0 -> f1 (exponential), optional wobble = the cartoon 'boing'."""
    t = _t(d)
    f = f1 + (f0 - f1) * np.exp(-curve * t / d)
    if wobble:
        f = f * (1 + wobble * np.sin(2 * np.pi * wob_hz * t))
    ph = _phase(f)
    out = np.sin(ph)
    if harm:
        out = out + harm * np.sin(2 * ph) + harm * 0.5 * np.sin(3 * ph)
    return out


def _noise(d, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, int(SR * d))


def _vlp(x, widths):
    """Low-pass with a per-sample width (variable box filter). Bigger width = duller."""
    n = len(x)
    c = np.concatenate([[0.0], np.cumsum(x)])
    i = np.arange(n)
    w = np.maximum(1, widths).astype(int)
    lo, hi = np.clip(i - w, 0, n), np.clip(i + w + 1, 0, n)
    return (c[hi] - c[lo]) / np.maximum(hi - lo, 1)


def _mix(buf, x, at=0.0, gain=1.0):
    s = int(at * SR)
    e = min(len(buf), s + len(x))
    if e > s:
        buf[s:e] += x[: e - s] * gain
    return buf


LOWPASS_HZ = 2800        # everything above this is rolled off: nothing can get shrill
PITCH_SCALE = 1.0        # overall tone: 0.85 = deeper/mellower, 1.15 = brighter. Then run: python sound.py --force


def _lowpass(x, cutoff=LOWPASS_HZ):
    """Smooth FFT roll-off (4th-order-ish) so squeaky highs are tamed."""
    if len(x) < 8:
        return x
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec *= 1.0 / (1.0 + (f / cutoff) ** 4)
    return np.fft.irfft(spec, n=len(x))


def _finish(x, peak=0.8):
    x = _lowpass(np.asarray(x, dtype=float))
    m = float(np.max(np.abs(x))) or 1.0
    x = x / m * peak
    n = min(len(x) // 2, int(SR * 0.0015))         # 1.5 ms fades: no clicks
    if n > 0:
        x[:n] *= np.linspace(0, 1, n)
        x[-n:] *= np.linspace(1, 0, n)
    return x


def _buf(d):
    return np.zeros(int(SR * d))


# =============================================================== the sounds
# Each builder takes a pitch multiplier and returns a float array.
# v2 "soft": warm and low. No high squeak layers, gentler pitch glides, and _finish()
# rolls off everything above ~2.8 kHz so nothing can turn shrill.

def _soft_tick(d, seed, width=7):
    """A tiny dull click (noise, low-passed) instead of a bright one."""
    n = _noise(d, seed)
    return _vlp(n, np.full(len(n), width)) * _decay(d, 6)


def _step_walk(p):
    """Soft, rubbery 'thup'."""
    b = _buf(0.12)
    _mix(b, _sweep(310 * p, 150 * p, 0.10, 4) * _decay(0.10, 6), 0, 1.0)
    _mix(b, _soft_tick(0.02, int(p * 1000)), 0, 1.2)
    return b


def _step_run(p):
    """Quicker, still soft."""
    b = _buf(0.08)
    _mix(b, _sweep(380 * p, 190 * p, 0.06, 4) * _decay(0.06, 6), 0, 0.9)
    _mix(b, _soft_tick(0.015, int(p * 555)), 0, 1.0)
    return b


def _step_tiptoe(p):
    """Sneaking: barely-there padded taps."""
    b = _buf(0.07)
    _mix(b, _sweep(440 * p, 260 * p, 0.045, 3) * _decay(0.045, 6), 0, 0.5)
    _mix(b, _soft_tick(0.02, int(p * 333), 9), 0, 0.8)
    return b


def _step_tap(p):
    """Walking on top of a window: a muted wooden 'tok'."""
    b = _buf(0.07)
    _mix(b, _sweep(560 * p, 380 * p, 0.05, 4) * _decay(0.05, 7), 0, 0.9)
    _mix(b, _soft_tick(0.012, int(p * 777), 5), 0, 0.5)
    return b


def _jump(p):
    """Low, soft spring 'boing' going up."""
    d = 0.24
    return _sweep(150 * p, 400 * p, d, 5, 0.04, 16, harm=0.12) * _decay(d, 2.8)


def _land(p):
    """Squishy thud + a gentle little bounce."""
    b = _buf(0.22)
    _mix(b, _sweep(170 * p, 60 * p, 0.15, 4) * _decay(0.15, 4), 0, 1.0)
    n = _noise(0.04, int(p * 99))
    _mix(b, _vlp(n, np.full(len(n), 8)) * _decay(0.04, 5), 0, 0.9)
    _mix(b, _sweep(220 * p, 140 * p, 0.18, 3, 0.1, 24) * _decay(0.18, 4), 0.01, 0.22)
    return b


def _whoosh(p):
    """Airy but dull: a soft 'fwoomp', not a hiss."""
    d = 0.24
    n = _noise(d, int(p * 4242))
    k = np.linspace(0, 1, len(n))
    w = (9 + 22 * (1 - np.sin(np.pi * k)) ** 2) / p
    out = _vlp(n, w) - _vlp(n, np.full(len(n), 60))
    return out * np.sin(np.pi * k) ** 1.5


def _hit(p, snap):
    b = _buf(0.2)
    _mix(b, _sweep(230 * p, 70 * p, 0.13, 4) * _decay(0.13, 5), 0, 1.0)
    _mix(b, _soft_tick(0.035, int(p * 31), 5), 0, snap)
    _mix(b, _sweep(430 * p, 210 * p, 0.07, 3) * _decay(0.07, 5), 0, 0.22)   # the comic "POW", warmer
    return b


def _punch(p):
    return _hit(p, 1.4)


def _kick(p):
    return _hit(p * 1.18, 2.0)


def _explosion(p):
    d = 0.9
    n = _noise(d, 5)
    k = np.linspace(0, 1, len(n))
    boom = _vlp(n, 3 + 60 * k) * _decay(d, 4)
    b = _buf(d)
    _mix(b, boom, 0, 1.0)
    _mix(b, _sweep(130, 32, d, 3) * _decay(d, 3.5), 0, 0.9)
    _mix(b, _soft_tick(0.03, 8, 4), 0, 1.5)
    return b


def _alert(p):
    """'!' sting: two soft rising notes."""
    b = _buf(0.2)
    _mix(b, _sweep(330 * p, 520 * p, 0.06, 3, harm=0.08) * _decay(0.06, 3), 0, 0.9)
    _mix(b, _sweep(400 * p, 700 * p, 0.09, 3, harm=0.08) * _decay(0.09, 3), 0.075, 1.0)
    return b


def _question(p):
    return _sweep(260 * p, 500 * p, 0.17, 2, 0.03, 9, harm=0.1) * _decay(0.17, 2)


def _pop(p):
    return _sweep(560 * p, 250 * p, 0.07, 4) * _decay(0.07, 5)


def _boop(p):
    return _sweep(320 * p, 460 * p, 0.08, 3) * _decay(0.08, 4)


def _hmm(p):
    return _sweep(260 * p, 235 * p, 0.22, 2, 0.03, 5, harm=0.1) * np.sin(np.pi * _t(0.22) / 0.22)


def _victory(p):
    """Little warm arpeggio (C4 E4 G4 C5)."""
    notes = (261.63, 329.63, 392.0, 523.25)
    b = _buf(0.62)
    for i, f in enumerate(notes):
        d = 0.09 if i < 3 else 0.3
        t = _t(d)
        tone = np.sin(2 * np.pi * f * p * t) + 0.15 * np.sin(4 * np.pi * f * p * t)
        _mix(b, tone * _decay(d, 4), i * 0.085, 1.0)
    return b


def _tired(p):
    """Sad, mellow slide 'wah wah'."""
    d = 0.55
    return _sweep(280 * p, 120 * p, d, 1.5, 0.05, 6, harm=0.2) * _decay(d, 1.5)


def _taunt(p):
    """Gentle 'nyah nyah' wobble."""
    b = _buf(0.34)
    _mix(b, _sweep(360 * p, 290 * p, 0.15, 2, 0.08, 14, harm=0.15) * _decay(0.15, 2.5), 0, 1.0)
    _mix(b, _sweep(390 * p, 310 * p, 0.15, 2, 0.08, 14, harm=0.15) * _decay(0.15, 2.5), 0.17, 1.0)
    return b


def _tinker(p):
    """Soft little taps."""
    b = _buf(0.05)
    _mix(b, _soft_tick(0.012, int(p * 17), 6), 0, 1.0)
    _mix(b, np.sin(2 * np.pi * 700 * p * _t(0.02)) * _decay(0.02, 5), 0, 0.3)
    return b


def _bop(p):
    return _sweep(320 * p, 170 * p, 0.07, 4) * _decay(0.07, 5)


def _whistle(p):
    """Falling 'whee', much lower and softer than a real whistle (only for LONG falls)."""
    d = 0.7
    return _sweep(640 * p, 260 * p, d, 1.2, 0.012, 9) * np.sin(np.pi * _t(d) / d) ** 0.5


def _aww(p):
    """Soft two-note 'aww' for petting."""
    b = _buf(0.42)
    for i, (f, d) in enumerate(((392.0, 0.16), (493.88, 0.26))):
        t = _t(d)
        tone = np.sin(2 * np.pi * f * p * t) + 0.15 * np.sin(4 * np.pi * f * p * t)
        _mix(b, tone * _decay(d, 3) * np.minimum(1, t / 0.02), i * 0.15, 1.0)
    return b


def _snore(p):
    """Breathy rumble that swells and fades."""
    d = 0.8
    n = _noise(d, 3)
    k = np.linspace(0, 1, len(n))
    swell = np.sin(np.pi * k) ** 2
    breath = _vlp(n, np.full(len(n), 14)) * swell * 3
    rumble = np.sin(2 * np.pi * 70 * p * _t(d)) * (1 + 0.5 * np.sin(2 * np.pi * 28 * _t(d))) * swell * 0.5
    return breath + rumble


def _ding(p):
    """Soft little bell for reminders."""
    d = 0.6
    t = _t(d)
    return (np.sin(2 * np.pi * 784 * p * t) + 0.4 * np.sin(2 * np.pi * 1176 * p * t) * np.exp(-t * 8)) * np.exp(-t * 6)


def _rimshot(p):
    """Ba-dum-TSS."""
    b = _buf(0.75)
    _mix(b, _sweep(210 * p, 95 * p, 0.12, 4) * _decay(0.12, 5), 0.0, 1.0)
    _mix(b, _sweep(210 * p, 95 * p, 0.12, 4) * _decay(0.12, 5), 0.15, 1.0)
    n = _noise(0.45, 71)
    _mix(b, (_vlp(n, np.full(len(n), 3)) - _vlp(n, np.full(len(n), 30))) * _decay(0.45, 4), 0.3, 1.6)
    return b


def _tada(p):
    """Fanfare: a chord that builds up."""
    b = _buf(0.95)
    for i, f in enumerate((261.63, 329.63, 392.0, 523.25)):
        t = _t(0.8)
        tone = np.sin(2 * np.pi * f * p * t) + 0.3 * np.sin(4 * np.pi * f * p * t) + 0.15 * np.sin(6 * np.pi * f * p * t)
        _mix(b, tone * _decay(0.8, 3.2) * np.minimum(1, t / 0.01), i * 0.09, 1.0)
    return b


def _applause(p):
    """A room full of claps."""
    d = 1.6
    rng = np.random.default_rng(5)
    b = _buf(d)
    for _ in range(170):
        at = float(rng.uniform(0, d - 0.1))
        swell = math.sin(math.pi * at / d) ** 0.7
        clap = _vlp(_noise(0.04, int(rng.integers(1_000_000))), np.full(int(SR * 0.04), 4)) * _decay(0.04, 6)
        _mix(b, clap, at, float(rng.uniform(0.4, 1.0)) * swell)
    return b


def _drumroll(p):
    """Snare-style build-up: alternating taps grow louder and closer together."""
    duration = 1.15
    out = _buf(duration)
    rng = np.random.default_rng(901)
    at = 0.0
    while at < duration - 0.045:
        progress = at / duration
        tap_length = 0.060
        t = _t(tap_length)
        # A snare has both a low drum body and noisy rattling wires.
        body = np.sin(2 * np.pi * (155 * p) * t) * np.exp(-43 * t)
        noise = rng.uniform(-1, 1, len(t))
        rattle = _vlp(noise, np.full(len(t), 2)) * np.exp(-52 * t)
        hit = body * 0.50 + rattle * 0.80
        strength = 0.22 + 0.80 * progress * progress
        _mix(out, hit, at, strength)
        # Accelerate from 12 taps/s to about 30 taps/s.
        at += 1.0 / (12 + 18 * progress)
    return out


def _laugh(p):
    """A playful, original three-'ha' cartoon chuckle (not a sampled voice)."""
    duration = 0.82
    out = _buf(duration)
    for i, start in enumerate((0.03, 0.23, 0.43)):
        d = 0.18 if i < 2 else 0.28
        t = _t(d)
        pitch = p * (190 + i * 17 - 25 * t / d)
        phase = _phase(pitch)
        # Voiced 'ah' shape plus a small breathy edge.
        voiced = np.sin(phase) + 0.38 * np.sin(2 * phase) + 0.18 * np.sin(3 * phase)
        breath = _vlp(_noise(d, 770 + i), np.full(len(t), 4))
        envelope = np.minimum(1, t / 0.018) * np.exp(-3.7 * t / d)
        _mix(out, (0.8 * voiced + 0.20 * breath) * envelope, start, 0.85)
    return out


# name -> (builder, pitch multipliers). One WAV per pitch: <name>_<i>.wav
BANKS = {
    "step_walk": (_step_walk, (0.90, 0.97, 1.05, 1.12)),
    "step_run": (_step_run, (0.92, 0.98, 1.05, 1.11)),
    "step_tiptoe": (_step_tiptoe, (0.92, 0.98, 1.04, 1.09)),
    "step_tap": (_step_tap, (0.92, 0.98, 1.05, 1.11)),
    "jump": (_jump, (0.94, 1.06)),
    "land": (_land, (0.9, 1.1)),
    "whoosh": (_whoosh, (0.92, 1.08)),
    "punch": (_punch, (0.92, 1.08)),
    "kick": (_kick, (0.92, 1.08)),
    "explosion": (_explosion, (1.0,)),
    "alert": (_alert, (1.0,)),
    "question": (_question, (1.0,)),
    "pop": (_pop, (0.95, 1.08)),
    "boop": (_boop, (1.0,)),
    "hmm": (_hmm, (1.0,)),
    "victory": (_victory, (1.0,)),
    "tired": (_tired, (1.0,)),
    "taunt": (_taunt, (1.0,)),
    "tinker": (_tinker, (0.95, 1.08)),
    "bop": (_bop, (0.95, 1.1)),
    "whistle": (_whistle, (1.0,)),
    "aww": (_aww, (1.0,)),
    "snore": (_snore, (1.0,)),
    "ding": (_ding, (1.0,)),
    "rimshot": (_rimshot, (1.0,)),
    "tada": (_tada, (1.0,)),
    "applause": (_applause, (1.0,)),
    "drumroll": (_drumroll, (1.0,)),
    "laugh": (_laugh, (0.96, 1.04)),
}


def _write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


SFX_VERSION = 3          # bump when the built-in sounds change
MANIFEST = "sfx_manifest.json"


def _sha(path):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


def _variants(folder, name):
    files = sorted(Path(folder).glob(f"{name}_[0-9]*.wav"))
    single = Path(folder) / f"{name}.wav"
    return files + ([single] if single.exists() else [])


def generate_all(folder=SFX_DIR, force=False):
    """Create missing sounds and upgrade outdated built-in ones.
    Safe by design: a sound YOU replaced is never touched (unless force=True), and anything we
    overwrite is first copied to _old_sounds/. Returns how many files were written."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    mf_path = folder / MANIFEST
    legacy = not mf_path.exists()          # sounds from a build that predates versioning
    try:
        manifest = json.loads(mf_path.read_text())
        tracked = dict(manifest.get("files", {}))
        version = int(manifest.get("version", 0))
    except Exception:
        tracked, version = {}, 0
    outdated = version < SFX_VERSION
    made, backup = 0, folder / "_old_sounds"

    for name, (fn, pitches) in BANKS.items():
        existing = _variants(folder, name)
        if existing and not (force or outdated):
            continue
        if existing and not force:
            custom = False
            for f in existing:
                if f.name == f"{name}.wav":                       # a single-file sound is always yours
                    custom = True
                elif f.name in tracked:
                    custom = custom or _sha(f) != tracked[f.name]  # edited since we made it
                elif not legacy:
                    custom = True                                  # unknown file in a versioned folder
            if custom:
                continue
        for f in existing:                                         # keep a copy of whatever we replace
            backup.mkdir(exist_ok=True)
            shutil.copy2(f, backup / f.name)
            f.unlink()
        for i, p in enumerate(pitches):
            path = folder / f"{name}_{i}.wav"
            _write_wav(path, _finish(fn(p * PITCH_SCALE)))
            tracked[path.name] = _sha(path)
            made += 1
    if made or outdated or legacy:
        mf_path.write_text(json.dumps({"version": SFX_VERSION, "files": tracked}, indent=1))
    return made


# =============================================================== the engine
DANCE_POSES = {"dance", "headbang", "air_guitar", "dj"}
WALK_POSES = {"walk", "sneak", "flee"}


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


class SoundEngine:
    """Owns the sound effects and decides WHEN and HOW LOUD to play them."""

    def __init__(self, folder=SFX_DIR):
        self.ok = False
        self.m = None
        self.bank, self.last, self.gate = {}, {}, {}
        self._pose = "idle"
        self._step_idx = None
        self._last_step_var = {}
        self._prev_vy, self._prev_ground = 0.0, True
        self._fall_since, self._whistled = 0.0, False
        self._smash_done = False
        self._beat_sign = 0
        self._tinker_t = 0.0
        try:
            from PyQt6.QtMultimedia import QSoundEffect
            from PyQt6.QtCore import QUrl
            generate_all(folder)
            for name in BANKS:
                files = sorted(Path(folder).glob(f"{name}_[0-9]*.wav"))
                single = Path(folder) / f"{name}.wav"
                if not files and single.exists():
                    files = [single]
                effects = []
                for f in files:
                    e = QSoundEffect()
                    e.setSource(QUrl.fromLocalFile(str(f)))
                    e.setVolume(0.5)
                    effects.append(e)
                if effects:
                    self.bank[name] = effects
            self.ok = bool(self.bank)
        except Exception as e:            # no numpy / no QtMultimedia: stay silent, never crash
            print(f"[sound] disabled: {e}")

    def attach(self, mascot):
        self.m = mascot

    # ---------------------------------------------------------- context
    def context_volume(self):
        """How loud he is allowed to be right now (0 = silent)."""
        if not SETTINGS.get("sounds", True) or self.m is None:
            return 0.0
        b = self.m.behavior
        if b.mode == "watch":                         # you're watching a video: shhh
            return 0.0
        v = float(SETTINGS.get("sfx_volume", 0.6))
        if b.music_on:                                # your music is the star
            v *= 0.35
        hour = time.localtime().tm_hour
        if hour >= 23 or hour < 7:                    # late night: whisper
            v *= 0.5
        sp = getattr(self.m, "speaker", None)
        if sp is not None and sp.speaking:            # he's talking: keep the effects out of the way
            v *= 0.5
        return v

    # ---------------------------------------------------------- playing
    def play(self, name, volume=1.0, min_gap=0.0, variant=None, force=False):
        if not self.ok or name not in self.bank:
            return False
        now = time.monotonic()
        if now < self.gate.get(name, 0.0):
            return False
        ctx = self.context_volume()
        if force:
            # Deliberate demo sound effects must not disappear just because Buddy
            # is speaking, watching a video, or it is late at night.
            # Still respect the user's master sound-effects switch and volume.
            if not SETTINGS.get("sounds", True):
                return False
            ctx = float(SETTINGS.get("sfx_volume", 0.6))
        vol = ctx * volume
        if vol <= 0.01:
            return False
        effects = self.bank[name]
        if variant is None:
            choices = [i for i in range(len(effects)) if i != self.last.get(name)] or [0]
            variant = random.choice(choices)
        variant %= len(effects)
        self.last[name] = variant
        self.gate[name] = now + min_gap
        e = effects[variant]
        # QSoundEffect loads its WAV asynchronously. If the audio backend failed
        # to load the file, print a useful diagnostic instead of silently playing.
        if e.status() == e.Status.Error:
            print(f"[sound] could not load {name}: {e.source().toLocalFile()}")
            return False
        e.setVolume(_clamp(vol * random.uniform(0.92, 1.05)))
        e.play()
        return True

    # ---------------------------------------------------------- per-frame brain
    def update(self, m):
        """Called once per frame by the mascot. Watches what he's doing, makes noise."""
        if not self.ok:
            return
        b = m.body
        pose = m._pose_name()

        if pose != self._pose:
            self._on_pose(self._pose, pose, m)
            self._pose = pose

        self._footsteps(m, pose)
        self._landing(m)
        self._extras(m, pose)

        self._prev_vy, self._prev_ground = b.vy, b.on_ground

    def _on_pose(self, old, new, m):
        b = m.body
        if new == "jump":
            self.play("jump", 0.8, 0.15)
        elif new == "land" and not b.physics:         # scripted leap landing (physics handles its own)
            self.play("land", 0.7, 0.15)
        elif new == "victory":
            self.play("victory", 0.8, 1.0)
        elif new == "tired":
            self.play("tired", 0.8, 1.0)
        elif new == "taunt":
            self.play("taunt", 0.8, 1.0)
        elif new == "wave":
            self.play("boop", 0.7, 0.5)
        elif new == "thinking":
            self.play("hmm", 0.5, 1.0)
        if new == "fall":
            self._fall_since, self._whistled = m.t, False
        if new == "smash":
            self._smash_done = False
        self._step_idx = None

    def _footsteps(self, m, pose):
        b = m.body
        if not (b.on_ground and pose in WALK_POSES and m.speed > 25):
            self._step_idx = None
            return
        # in the walk cycle a foot plants every time cos(phase) changes sign
        idx = math.floor((m.phase - math.pi / 2) / math.pi)
        if self._step_idx is None:
            self._step_idx = idx
            return
        if idx == self._step_idx:
            return
        self._step_idx = idx
        side = idx % 2
        speed = m.speed
        on_window = bool(b.support) and b.support[0] != "floor"
        if pose == "sneak":
            bank, vol = "step_tiptoe", 0.45
        elif on_window:
            bank, vol = "step_tap", 0.35 + 0.4 * _clamp(speed / 450)
        elif speed > 260:
            bank, vol = "step_run", 0.6 + 0.4 * _clamp(speed / 450)
        else:
            bank, vol = "step_walk", 0.5 + 0.4 * _clamp(speed / 260)
        n = len(self.bank.get(bank, ()))
        if n < 2:
            self.play(bank, vol, 0.03)
            return
        half = max(1, n // 2)                          # left foot = lower pitches, right = higher
        pool = list(range(half)) if side == 0 else list(range(half, n))
        prev = self._last_step_var.get(bank)
        pool = [i for i in pool if i != prev] or pool
        v = random.choice(pool)
        self._last_step_var[bank] = v
        self.play(bank, vol, 0.03, variant=v)

    def _landing(self, m):
        b = m.body
        if b.physics and b.on_ground and not self._prev_ground and self._prev_vy > 300:
            self.play("land", 0.3 + 0.7 * _clamp(self._prev_vy / 1800), 0.1)

    def _extras(self, m, pose):
        b = m.body
        if pose == "fall" and not self._whistled and m.t - self._fall_since > 0.55:
            self._whistled = True
            self.play("whistle", 0.6, 1.0)
        if pose == "smash" and not self._smash_done and m.pose_t > 0.45:
            self._smash_done = True
            self.play("whoosh", 1.0, 0.2)
        if pose == "tinker" and m.t >= self._tinker_t:
            self._tinker_t = m.t + random.uniform(0.2, 0.34)
            self.play("tinker", 0.5, 0.05)
        if pose in DANCE_POSES and not m.behavior.music_on:
            # bop on the beat of his own dance (but never fight with your real music)
            s = math.sin(m.t * m.tempo * 9)
            sign = 1 if s >= 0 else -1
            if sign != self._beat_sign:
                if self._beat_sign != 0:
                    self.play("bop", 0.4, 0.1)
                self._beat_sign = sign


if __name__ == "__main__":
    n = generate_all(SFX_DIR, force="--force" in sys.argv)
    print(f"wrote {n} sound files to {SFX_DIR}")
