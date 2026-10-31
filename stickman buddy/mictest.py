import sounddevice as sd
import numpy as np

# Select the laptop's internal microphone
MIC_DEVICE = 1

print("Recording for 5 seconds. Speak now!")

audio = sd.rec(
    int(5 * 16000),
    samplerate=16000,
    channels=1,
    dtype="float32",
    device=MIC_DEVICE
)

sd.wait()

print("Audio level:", np.max(np.abs(audio)))