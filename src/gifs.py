"""
GIF effects layer. Every effect in FX below is drawn by fx_art.py, so nothing needs downloading. To
replace one with your own transparent GIF, drop it into assets/gifs/ using the effect's name
(impact.gif, poof.gif...). Effects without a GIF file use the built-in art.
"""
from pathlib import Path

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QMovie

GIF_DIR = Path(__file__).resolve().parent.parent / "assets" / "gifs"

# name -> (width in "stickman units" (multiplied by SCALE), anchor)
FX = {
    "impact":      (90, "center"),    # comic POW on every hit
    "poof":        (100, "bottom"),   # hard landings
    "explosion":   (230, "center"),   # the Wi-Fi smash finale
    "music_notes": (80, "center"),    # while dancing to a song
    "sparkle":     (80, "center"),    # victory / taunts
    "confetti":    (280, "center"),   # big victory
    "sweat":       (40, "center"),    # when scared
    "zzz":         (60, "center"),    # napping
    "lightbulb":   (52, "center"),    # before a prank
    "dizzy":       (70, "center"),    # exhausted
    "heart":       (60, "center"),    # floating hearts when you pet him
}


class GifLayer:
    def __init__(self, folder=GIF_DIR):
        self.folder = Path(folder)
        self.cache = {}
        self.items = []

    def frames(self, name):
        if name in self.cache:
            return self.cache[name]
        frames = None
        path = self.folder / f"{name}.gif"
        if not path.exists():
            from fx_art import build              # drawn in code, so a fresh clone has every effect
            frames = build(name)
        else:                                      # your own GIF in assets/gifs/ overrides the built-in art
            mv = QMovie(str(path))
            if mv.isValid() and mv.frameCount() > 0:
                frames = []
                for i in range(mv.frameCount()):
                    mv.jumpToFrame(i)
                    delay = (mv.nextFrameDelay() or 100) / 1000.0
                    frames.append((mv.currentPixmap(), max(0.02, delay)))
        self.cache[name] = frames
        return frames

    def has(self, name):
        return self.frames(name) is not None

    def spawn(self, name, x, y, width, anchor="center", loops=1, duration=None,
              follow=None, offset=(0, 0)):
        frames = self.frames(name)
        if not frames:
            return False
        self.items.append(dict(frames=frames, i=0, t=0.0, age=0.0, loops=loops, done=0,
                               duration=duration, x=x, y=y, width=width, anchor=anchor,
                               follow=follow, offset=offset))
        return True

    def update(self, dt, anchors):
        alive = []
        for g in self.items:
            g["age"] += dt
            g["t"] += dt
            while g["t"] >= g["frames"][g["i"]][1]:
                g["t"] -= g["frames"][g["i"]][1]
                g["i"] += 1
                if g["i"] >= len(g["frames"]):
                    g["i"] = 0
                    g["done"] += 1
            finished = (g["loops"] > 0 and g["done"] >= g["loops"]) or \
                       (g["duration"] is not None and g["age"] >= g["duration"])
            if g["follow"] in anchors:
                ax, ay = anchors[g["follow"]]
                g["x"], g["y"] = ax + g["offset"][0], ay + g["offset"][1]
            if not finished:
                alive.append(g)
        self.items = alive

    def _rect(self, g):
        pm = g["frames"][g["i"]][0]
        w = g["width"]
        h = w * pm.height() / max(1, pm.width())
        top = g["y"] - h if g["anchor"] == "bottom" else g["y"] - h / 2
        return QRectF(g["x"] - w / 2, top, w, h)

    def rects(self):
        return [self._rect(g) for g in self.items]

    def paint(self, p):
        for g in self.items:
            pm = g["frames"][g["i"]][0]
            p.drawPixmap(self._rect(g), pm, QRectF(pm.rect()))
