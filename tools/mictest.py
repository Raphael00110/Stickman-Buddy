"""Microphone check. Run it from the project folder:   python tools/mictest.py

It lists your recording devices, records 3 seconds from the SAME device Stickman Buddy uses, and tells you
how loud it was. If you see "no sound", pick another device and set it before launching, e.g. in PowerShell:
    $env:STICKMAN_MIC_DEVICE = "15"        (a device number from the list, or part of its name)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import sounddevice as sd

from voice import RATE, mic_device

device = mic_device()
print(sd.query_devices())
print()
print("Using:", "the Windows default recording device" if device is None else f"device {device!r}")
print("Recording for 3 seconds. Speak now!")

audio = sd.rec(int(3 * RATE), samplerate=RATE, channels=1, dtype="float32", device=device)
sd.wait()

level = float(np.max(np.abs(audio)))
print(f"Audio level: {level:.4f}")
print("Mic works!" if level >= 0.003 else "No sound heard: check the mic isn't muted, or try another device.")
