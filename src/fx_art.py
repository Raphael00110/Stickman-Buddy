"""
Built-in effect art, drawn with QPainter at startup: smooth alpha, no image files needed, and
always in the stickman's own colours (STYLE in settings.py). gifs.py uses this whenever there is no
GIF with the effect's name in assets/gifs/, so a fresh clone always has every effect. Each effect is a
list of (QPixmap, seconds_per_frame). To restyle one, edit its draw function.
"""
import math
import random

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QPainterPath, QPolygonF

from settings import STYLE

S = 256
YELLOW, ORANGE, RED = QColor("#ffd60a"), QColor("#ff9f1c"), QColor("#ff453a")
CREAM, BLUE, PINK, CYAN = QColor("#fff4a3"), QColor("#6ec6ff"), QColor("#ff6fb5"), QColor("#52c7ff")
CONFETTI = [QColor(c) for c in ("#ff453a", "#30d158", "#0a84ff", "#ffd60a", "#ff2d96", "#bf5af2")]


def ink():
    return QColor(STYLE["outline"])


def pen(w=8, color=None):
    return QPen(color or ink(), w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


def star(cx, cy, r_out, r_in, n, rot=0.0):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / n
        pts.append(QPointF(cx + math.cos(a) * r, cy + math.sin(a) * r))
    return QPolygonF(pts)


def ease_out(k):
    return 1 - (1 - k) ** 3


def fade(k, start=0.7):
    return 1.0 if k < start else max(0.0, 1 - (k - start) / (1 - start))


# ------------------------------------------------------------------ effects
def impact(p, k, i):
    s = 0.35 + 0.7 * ease_out(min(1, k / 0.45))
    p.setOpacity(fade(k, 0.65))
    c = S / 2
    p.setPen(pen(8))
    for a in range(10):                                   # speed lines
        ang = a * math.tau / 10 + 0.15
        r1, r2 = 100 * s, (100 + 24 * s) * s + 10
        p.drawLine(QPointF(c + math.cos(ang) * r1, c + math.sin(ang) * r1),
                   QPointF(c + math.cos(ang) * r2, c + math.sin(ang) * r2))
    p.setBrush(YELLOW)
    p.drawPolygon(star(c, c, 96 * s, 50 * s, 10, k * 0.35))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(CREAM)
    p.drawPolygon(star(c, c, 58 * s, 30 * s, 10, k * 0.35 + 0.15))


def explosion(p, k, i):
    s = 0.25 + 0.95 * ease_out(min(1, k / 0.5))
    p.setOpacity(fade(k, 0.7))
    c = S / 2
    rnd = random.Random(5)
    for _ in range(7):                                    # flying debris
        ang, dist = rnd.uniform(0, math.tau), rnd.uniform(70, 118)
        r = rnd.uniform(7, 13) * (1 - k * 0.5)
        x, y = c + math.cos(ang) * dist * s, c + math.sin(ang) * dist * s + k * 22
        p.setPen(pen(5))
        p.setBrush(ORANGE)
        p.drawEllipse(QPointF(x, y), r, r)
    for r_out, r_in, col, w, rot in ((118, 66, RED, 9, 0.0), (90, 50, ORANGE, 7, 0.2), (58, 32, YELLOW, 5, 0.4)):
        p.setPen(pen(w))
        p.setBrush(col)
        p.drawPolygon(star(c, c, r_out * s, r_in * s, 12, rot + k * 0.5 * (1 if r_out != 90 else -1)))


def poof(p, k, i):
    s = 0.5 + 0.6 * ease_out(k)
    p.setOpacity(fade(k, 0.45))
    p.setPen(pen(7))
    p.setBrush(QColor("#f4f4f4"))
    for dx, dy, r in ((-62, 0, 34), (0, -10, 44), (62, 0, 34), (-30, 14, 28), (32, 14, 28), (0, 10, 30)):
        x = S / 2 + dx * s * 1.2
        y = S - 56 + dy * s - k * 28
        p.drawEllipse(QPointF(x, y), r * s, r * s)


def _note(p, x, y, col, sz):
    p.save()
    p.translate(x, y)
    p.scale(sz, sz)
    stem = QPainterPath()
    stem.moveTo(19, -4)
    stem.lineTo(19, -84)
    stem.cubicTo(19, -84, 54, -70, 48, -38)
    stem.cubicTo(44, -58, 30, -62, 19, -62)
    p.setPen(pen(9))
    p.setBrush(col)
    p.drawPath(stem)
    p.save()
    p.rotate(-22)
    p.drawEllipse(QPointF(0, 0), 23, 16)
    p.restore()
    p.restore()


def music_notes(p, k, i):
    pop = min(1.0, k / 0.15)
    p.setOpacity(fade(k, 0.75))
    _note(p, 80 + math.sin(k * 7) * 12, 190 - k * 70, PINK, 0.95 * pop)
    _note(p, 168 + math.cos(k * 7) * 12, 168 - k * 70, CYAN, 0.8 * pop)


def sparkle(p, k, i):
    for cx, cy, ph, sz in ((70, 80, 0.0, 54), (178, 64, 0.35, 40), (140, 170, 0.7, 48), (60, 190, 0.2, 28)):
        t = abs(math.sin((k + ph) * math.pi * 1.5))
        p.setPen(pen(6))
        p.setBrush(CREAM)
        p.drawPolygon(star(cx, cy, sz * t, sz * 0.26 * t, 4, 0.0))


def confetti(p, k, i):
    rnd = random.Random(9)
    p.setOpacity(fade(k, 0.8))
    for _ in range(30):
        x, y0 = rnd.uniform(12, S - 12), rnd.uniform(-S * 0.9, -10)
        speed, spin, col = rnd.uniform(0.9, 1.3), rnd.uniform(-9, 9), rnd.choice(CONFETTI)
        y = y0 + k * (S + 120) * speed
        if -20 < y < S + 20:
            p.save()
            p.translate(x + math.sin(k * 6 + y0) * 8, y)
            p.rotate(spin * k * 40)
            p.setPen(pen(3))
            p.setBrush(col)
            p.drawRect(-9, -5, 18, 10)
            p.restore()


def sweat(p, k, i):
    p.setOpacity(fade(k, 0.6))
    for dx, ph in ((-1, 0.0), (1, 0.15), (0.2, 0.3)):
        t = max(0.0, k - ph) / (1 - ph)
        x = S / 2 + dx * (30 + 70 * t)
        y = 70 + 120 * t * t + 10 * t
        d = QPainterPath()
        d.moveTo(x, y - 34)
        d.quadTo(x - 24, y + 4, x, y + 14)
        d.quadTo(x + 24, y + 4, x, y - 34)
        p.setPen(pen(6))
        p.setBrush(BLUE)
        p.drawPath(d)


def zzz(p, k, i):
    p.setOpacity(fade(k, 0.7))
    for j, (sz, ph) in enumerate(((20, 0.0), (28, 0.25), (38, 0.5))):
        t = (k + ph) % 1.0
        x, y = 70 + j * 44 + t * 30, 210 - t * 150 - j * 8
        s = sz * (0.5 + t)
        pts = [QPointF(x - s, y - s), QPointF(x + s, y - s), QPointF(x - s, y + s), QPointF(x + s, y + s)]
        path = QPainterPath(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
        p.setOpacity(fade(k, 0.7) * (1 - abs(t - 0.5) * 0.6))
        p.setPen(pen(18))
        p.drawPath(path)
        p.setPen(pen(8, QColor("white")))
        p.drawPath(path)


def lightbulb(p, k, i):
    pop = 1 + 0.18 * math.sin(min(1, k * 3) * math.pi)
    on = (i % 2 == 0)
    c = S / 2
    p.save()
    p.translate(c, 130)
    p.scale(pop, pop)
    if on:
        p.setPen(pen(9))
        for a in range(9):
            ang = math.pi + a * math.pi / 8
            p.drawLine(QPointF(math.cos(ang) * 82, math.sin(ang) * 82 - 4),
                       QPointF(math.cos(ang) * 108, math.sin(ang) * 108 - 4))
    p.setPen(pen(9))
    p.setBrush(YELLOW if on else QColor("#e8e8e8"))
    p.drawEllipse(QPointF(0, -8), 56, 56)
    p.setBrush(QColor("#a8a8a8"))
    p.drawRoundedRect(-24, 44, 48, 30, 8, 8)
    p.setPen(pen(6))
    p.drawLine(QPointF(-12, 10), QPointF(-4, -14))
    p.drawLine(QPointF(-4, -14), QPointF(4, 10))
    p.drawLine(QPointF(4, 10), QPointF(12, -14))
    p.restore()


def dizzy(p, k, i):
    p.setOpacity(fade(k, 0.85))
    for j in range(3):
        a = k * math.tau * 1.5 + j * math.tau / 3
        x, y = S / 2 + math.cos(a) * 78, 150 + math.sin(a) * 26
        p.setPen(pen(6))
        p.setBrush(YELLOW)
        p.drawPolygon(star(x, y, 30, 13, 5, a))


def heart(p, k, i):
    """Little hearts floating up (when you pet him)."""
    p.setOpacity(fade(k, 0.6))
    for j, (dx, ph, sz) in enumerate(((-34, 0.0, 30), (30, 0.3, 24), (0, 0.55, 34))):
        t = max(0.0, k - ph * 0.6) / (1 - ph * 0.6)
        x, y = S / 2 + dx + math.sin(t * 6 + j) * 10, 200 - t * 150
        s = sz * (0.5 + 0.6 * min(1.0, t * 3))
        path = QPainterPath()
        path.moveTo(x, y + s * 0.9)
        path.cubicTo(x - s * 1.5, y - s * 0.2, x - s * 0.5, y - s * 1.3, x, y - s * 0.35)
        path.cubicTo(x + s * 0.5, y - s * 1.3, x + s * 1.5, y - s * 0.2, x, y + s * 0.9)
        p.setPen(pen(6))
        p.setBrush(PINK)
        p.drawPath(path)


BUILDERS = {  # name: (draw function, frames, seconds per frame)
    "impact": (impact, 9, 0.04), "explosion": (explosion, 12, 0.05), "poof": (poof, 9, 0.055),
    "music_notes": (music_notes, 16, 0.07), "sparkle": (sparkle, 12, 0.07),
    "confetti": (confetti, 20, 0.055), "sweat": (sweat, 10, 0.07), "zzz": (zzz, 16, 0.075),
    "lightbulb": (lightbulb, 8, 0.11), "dizzy": (dizzy, 14, 0.065), "heart": (heart, 14, 0.07),
}


def build(name):
    if name not in BUILDERS:
        return None
    draw, n, delay = BUILDERS[name]
    frames = []
    for i in range(n):
        pm = QPixmap(S, S)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw(p, i / (n - 1), i)
        p.end()
        frames.append((pm, delay))
    return frames
