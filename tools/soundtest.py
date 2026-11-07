"""Sound check.   Run from the project folder:   python tools/soundtest.py

Plays the three cues of Buddy's joke (drum roll, rimshot, laugh) through the SAME sound system he uses, and
reports what it found. You should HEAR three sounds, one after another. If you don't, copy everything this
prints and send it along: it says which step is failing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import sound
from settings import SETTINGS

CUES = ("drumroll", "rimshot", "laugh")

app = QApplication(sys.argv)
print(f"Sound folder : {sound.SFX_DIR}  ({'exists' if sound.SFX_DIR.exists() else 'MISSING, it is created on first run'})")
print(f"Settings     : sounds={SETTINGS.get('sounds')}  sfx_volume={SETTINGS.get('sfx_volume')}")
engine = sound.SoundEngine()                 # this also (re)creates any sound files that are missing
print(f"Sound system : {'OK' if engine.ok else 'DISABLED (see the [sound] message above, usually Qt audio or numpy)'}")
print(f"Sounds loaded: {len(engine.bank)} of {len(sound.BANKS)}")
if not engine.ok:
    sys.exit(1)

for name in CUES:
    if name not in engine.bank:
        print(f"  {name:9s}: NOT LOADED  (no {name}.wav or {name}_N.wav in {sound.SFX_DIR})")


def report_status():
    for name in CUES:
        for e in engine.bank.get(name, []):
            st = e.status()
            print(f"  {name:9s}: {Path(e.source().toLocalFile()).name:16s} status = {getattr(st, 'name', st)}")


def play(name):
    ok = engine.play(name, 1.0, force=True)
    print(f"  playing {name:9s} -> {'played' if ok else 'NOT PLAYED (see any [sound] line above)'}")


print("\nFile status (should all be Ready):")
QTimer.singleShot(1200, report_status)
print("Listen for three sounds...")
for i, name in enumerate(CUES):
    QTimer.singleShot(2000 + i * 2500, lambda n=name: play(n))
QTimer.singleShot(2000 + len(CUES) * 2500 + 1500, app.quit)
app.exec()
print("\nIf all three said 'played' but you heard nothing: check your Windows volume mixer for python.exe.")
