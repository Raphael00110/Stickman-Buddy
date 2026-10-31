"""
Generates simple placeholder GIFs into assets/gifs/ so every effect works
immediately. Replace any of them by dropping a real GIF with the same name.
Usage:  pip install pillow  &&  python tools/make_placeholder_gifs.py
"""
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "gifs"
S = 160
INK = (27, 27, 27, 255)


def canvas():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def star(d, cx, cy, r_out, r_in, n, fill, rot=0.0, width=5):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / n
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    d.polygon(pts, fill=fill, outline=INK, width=width)


def fade(img, k):
    a = img.getchannel("A").point(lambda v: int(v * k))
    img.putalpha(a)
    return img


def save(name, frames, ms):
    OUT.mkdir(parents=True, exist_ok=True)
    frames[0].save(OUT / f"{name}.gif", save_all=True, append_images=frames[1:],
                   duration=ms, loop=0, disposal=2, optimize=False)


def impact():
    fr = []
    for i, s in enumerate((0.35, 0.7, 1.0, 1.1, 1.0, 0.9)):
        im = canvas(); d = ImageDraw.Draw(im)
        star(d, S / 2, S / 2, 70 * s, 34 * s, 9, (255, 214, 10, 255), rot=i * 0.15)
        fr.append(fade(im, 1.0 if i < 4 else 0.6 - (i - 4) * 0.25))
    save("impact", fr, 45)


def poof():
    fr = []
    for i in range(7):
        im = canvas(); d = ImageDraw.Draw(im); k = 0.4 + i * 0.12
        for dx, r in ((-28, 22), (0, 30), (28, 22), (-12, 18), (14, 18)):
            cx, cy = S / 2 + dx * k * 1.5, S - 40 - abs(dx) * 0.2 - i * 3
            d.ellipse((cx - r * k, cy - r * k, cx + r * k, cy + r * k),
                      fill=(240, 240, 240, 255), outline=INK, width=4)
        fr.append(fade(im, 1.0 - i * 0.12))
    save("poof", fr, 60)


def explosion():
    fr = []
    for i, s in enumerate((0.3, 0.6, 0.9, 1.1, 1.2, 1.2, 1.1, 1.0)):
        im = canvas(); d = ImageDraw.Draw(im)
        star(d, S / 2, S / 2, 76 * s, 40 * s, 12, (255, 59, 48, 255), rot=i * 0.2)
        star(d, S / 2, S / 2, 56 * s, 30 * s, 12, (255, 159, 28, 255), rot=-i * 0.2, width=4)
        star(d, S / 2, S / 2, 34 * s, 18 * s, 10, (255, 230, 90, 255), rot=i * 0.3, width=3)
        fr.append(fade(im, 1.0 if i < 6 else 0.5))
    save("explosion", fr, 55)


def note(d, x, y, col):
    d.ellipse((x - 12, y - 8, x + 12, y + 8), fill=col, outline=INK, width=4)
    d.line((x + 11, y, x + 11, y - 42), fill=INK, width=5)
    d.line((x + 11, y - 42, x + 28, y - 34), fill=INK, width=5)


def music_notes():
    fr = []
    for i in range(12):
        im = canvas(); d = ImageDraw.Draw(im)
        note(d, 60 + math.sin(i * .6) * 8, S - 30 - i * 9, (120, 200, 255, 255))
        note(d, 100 + math.cos(i * .6) * 8, S - 10 - i * 9, (255, 130, 200, 255))
        fr.append(fade(im, 1.0 if i < 8 else 1.0 - (i - 7) * 0.2))
    save("music_notes", fr, 90)


def sparkle():
    fr = []
    for i in range(8):
        im = canvas(); d = ImageDraw.Draw(im)
        for cx, cy, ph in ((50, 60, 0), (110, 50, 2), (85, 110, 4)):
            s = 0.3 + 0.7 * abs(math.sin((i + ph) * 0.4))
            star(d, cx, cy, 30 * s, 8 * s, 4, (255, 240, 120, 255), width=3)
        fr.append(im)
    save("sparkle", fr, 70)


def confetti():
    random.seed(3)
    bits = [(random.randint(10, S - 10), random.randint(-S, 0), random.choice(
        [(255, 59, 48, 255), (52, 199, 89, 255), (10, 132, 255, 255), (255, 214, 10, 255), (255, 45, 150, 255)]),
        random.uniform(0, 3)) for _ in range(34)]
    fr = []
    for i in range(14):
        im = canvas(); d = ImageDraw.Draw(im)
        for x, y0, c, ph in bits:
            y = y0 + i * 18 + (i * 7) % 11
            if 0 <= y < S:
                w = 7 + 4 * math.sin(ph + i)
                d.rectangle((x - w, y - 4, x + w, y + 4), fill=c, outline=INK, width=2)
        fr.append(im)
    save("confetti", fr, 70)


def sweat():
    fr = []
    for i in range(8):
        im = canvas(); d = ImageDraw.Draw(im)
        for cx, ph in ((45, 0), (80, 3), (115, 5)):
            y = 30 + ((i + ph) % 8) * 14
            d.polygon([(cx, y - 18), (cx - 10, y + 4), (cx + 10, y + 4)], fill=(110, 198, 255, 255), outline=INK)
            d.ellipse((cx - 10, y - 6, cx + 10, y + 14), fill=(110, 198, 255, 255), outline=INK, width=3)
        fr.append(im)
    save("sweat", fr, 80)


def zzz():
    fr = []
    for i in range(10):
        im = canvas(); d = ImageDraw.Draw(im)
        for k, (s, ph) in enumerate(((16, 0), (24, 3), (32, 6))):
            t = (i + ph) % 10
            x, y = 40 + k * 28 + t * 2, S - 30 - t * 11 - k * 18
            d.line([(x - s, y - s), (x + s, y - s), (x - s, y + s), (x + s, y + s)], fill=INK, width=9)
            d.line([(x - s, y - s), (x + s, y - s), (x - s, y + s), (x + s, y + s)], fill=(255, 255, 255, 255), width=4)
        fr.append(im)
    save("zzz", fr, 90)


def lightbulb():
    fr = []
    for i in range(8):
        im = canvas(); d = ImageDraw.Draw(im); on = i % 2 == 0
        if on:
            for a in range(8):
                ang = a * math.pi / 4
                d.line((S / 2 + math.cos(ang) * 48, 66 + math.sin(ang) * 48,
                        S / 2 + math.cos(ang) * 68, 66 + math.sin(ang) * 68), fill=INK, width=6)
        d.ellipse((S / 2 - 32, 34, S / 2 + 32, 98), fill=(255, 230, 90, 255) if on else (230, 230, 230, 255),
                  outline=INK, width=5)
        d.rectangle((S / 2 - 14, 98, S / 2 + 14, 118), fill=(160, 160, 160, 255), outline=INK, width=4)
        fr.append(im)
    save("lightbulb", fr, 110)


def dizzy():
    fr = []
    for i in range(12):
        im = canvas(); d = ImageDraw.Draw(im)
        for k in range(3):
            a = i * 0.5 + k * 2.1
            star(d, S / 2 + math.cos(a) * 46, S / 2 + math.sin(a) * 16, 16, 7, 5, (255, 214, 10, 255), rot=a, width=3)
        fr.append(im)
    save("dizzy", fr, 70)


def _heart_shape(d, cx, cy, r, fill):
    for grow, col in ((3, INK), (0, fill)):      # outline pass, then fill pass
        rr = r + grow
        d.ellipse((cx - rr, cy - rr * 0.9, cx, cy + rr * 0.1), fill=col)
        d.ellipse((cx, cy - rr * 0.9, cx + rr, cy + rr * 0.1), fill=col)
        d.polygon([(cx - rr * 0.98, cy - rr * 0.25), (cx + rr * 0.98, cy - rr * 0.25), (cx, cy + rr * 1.05)], fill=col)


def heart():
    fr = []
    for i in range(12):
        im = canvas(); d = ImageDraw.Draw(im)
        for cx, ph, sz, col in ((52, 0, 17, (255, 70, 110, 255)), (104, 4, 14, (255, 120, 160, 255)),
                                (78, 7, 20, (255, 59, 90, 255))):
            t = (i + ph) % 12
            _heart_shape(d, cx + math.sin(t * 0.7) * 7, S - 26 - t * 11, sz, col)
        fr.append(fade(im, 1.0 if i < 9 else 1.0 - (i - 8) * 0.25))
    save("heart", fr, 85)


if __name__ == "__main__":
    for fn in (impact, poof, explosion, music_notes, sparkle, confetti, sweat, zzz, lightbulb, dizzy, heart):
        fn()
    print("wrote", len(list(OUT.glob("*.gif"))), "gifs to", OUT)
