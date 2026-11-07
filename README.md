# Stickman Buddy

**An AI-powered animated desktop companion built with Python and PyQt6.**

Stickman Buddy is a little animated character that lives on your Windows desktop. Instead of being another chatbot inside a window, he can walk around your screen, jump onto windows, react to your cursor, perform animations, and actually talk to you.

This project was built for **Next Byte Hacks V5**.

## Demo

**Watch Stickman Buddy in action:**  
https://youtu.be/ZlGp9RLPiK4

## Features

- **Desktop companion:** Walks, jumps, sits, and interacts with your open windows.
- **Animations:** Parkour, karate, dancing, superhero poses, magic tricks, and more.
- **Cursor interactions:** Reacts to your mouse, plays tag, and can be picked up and thrown around.
- **Local AI conversations:** Uses Ollama with Qwen2.5 to generate conversational responses without relying on a cloud API.
- **Offline voice recognition:** Uses Vosk to turn your spoken questions into text.
- **Text-to-speech:** Speaks using Windows' built-in voices.
- **Desktop awareness:** Detects the active application and can respond to different activities.
- **Media interactions:** Can react to music and support optional Shorts/Reels controls.
- **Focus Mode:** Temporarily disables distractions when you need to concentrate.
- **Memory:** Remembers friendship progress and interactions locally.
- **Control panel:** Trigger animations, sound effects, scenes, and custom demo scripts.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| PyQt6 | Desktop interface, rendering, animations, and event handling |
| Ollama | Local AI runtime |
| Qwen2.5:0.5b | AI conversations |
| Vosk | Offline speech recognition |
| sounddevice | Microphone input |
| pywin32 | Windows text-to-speech and system integration |
| NumPy | Numerical processing and sound synthesis |
| PyAutoGUI | Optional desktop and media interactions |

## Installation

### Requirements

- Windows 10 or 11
- Python 3.12 or 3.13
- Ollama installed
- A microphone for voice chat (optional)

### 1. Clone the repository

```bash
git clone https://github.com/Raphael00110/Stickman-Buddy.git
cd Stickman-Buddy
```

### 2. Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Install the local AI model

Download and install Ollama from https://ollama.com/.

Then run:

```bash
ollama pull qwen2.5:0.5b
```

Make sure Ollama is running before launching Stickman Buddy.

In `src/settings.py`, the default AI backend uses:

```python
BRAIN = "llama"
LLAMA_MODEL = "qwen2.5:0.5b"
```

The name `llama` is the project's internal backend setting for Ollama. The actual model is Qwen2.5.

### 4. Set up offline voice recognition (optional)

The quick way: run `python tools/get_vosk_model.py` and it downloads and installs the model for you.

Or do it by hand: download the `vosk-model-small-en-us-0.15` model from:

https://alphacephei.com/vosk/models

Extract it into:

```text
models/
└── vosk-model-small-en-us-0.15/
```

Make sure Windows allows desktop applications to access your microphone.

Both voice features use your **Windows default recording device**, so they work without any setup. To check
that your microphone works, run `python tools/mictest.py`: it lists your devices and records three seconds.

If you want a different microphone, list your devices with `python -m sounddevice`, then set
`STICKMAN_MIC_DEVICE` to its number (or part of its name) before launching. In PowerShell:

```powershell
$env:STICKMAN_MIC_DEVICE = "15"
python src/main.py
```

Replace `15` with the number from your own list.

### 5. Launch Stickman Buddy

From the project directory:

```bash
python src/main.py
```

Buddy should appear on your desktop!

## Troubleshooting

- **No sound effects, or the joke is silent:** run `python tools/soundtest.py`. It plays the drum roll, rimshot and laugh and tells you which step is failing. The sound files are generated automatically into `assets/sfx/` the first time you run the app.
- **"Voice model missing":** run `python tools/get_vosk_model.py`.
- **Voice can't hear you, or uses the wrong microphone:** run `python tools/mictest.py` (see step 4).
- **Starting over with a fresh copy of the project:** some files are deliberately *not* stored in git, so copy them across by hand if you want to keep them: `models/` (the speech model), `assets/sfx/` (only if you added your own sounds), `stickman_memory.json` (your friendship level) and `anthropic_api_key.txt` (only if you use the Claude brain). Copy the new files *over* the old folder instead of deleting it first.

## Controls

| Shortcut | Action |
|---|---|
| `Ctrl + Alt + P` | Open or close the full control panel |
| `Ctrl + Alt + M` | Show or hide the compact demo bar |
| `Ctrl + Alt + V` | Talk to Buddy using your microphone |
| `Ctrl + Alt + T` | Type a message or command |
| `Ctrl + Alt + Q` | Emergency quit |

You can also right-click Buddy's system tray icon to access settings, animations, voice options, and Focus Mode.

## How It Works

Stickman Buddy uses PyQt6's event loop to update his animations and process interactions.

His behavior system decides how he should respond to events, while the procedural animation system controls his movements and poses. The animation rig uses inverse kinematics to calculate arm and leg positions.

Visual effects (impacts, confetti, hearts, music notes and more) are drawn in code by `src/fx_art.py`, so nothing needs downloading. To replace one, put a transparent GIF named after the effect (for example `impact.gif`) in `assets/gifs/`.

For AI conversations, Ollama runs the language model locally. AI requests are handled on background threads so the desktop interface can remain responsive.

The AI can also suggest actions, but those actions are checked against a list of permitted behaviors before execution.

Vosk processes microphone audio locally and converts recognized speech into text, which is then passed to the configured AI backend.

## Privacy

The default Ollama backend processes AI conversations locally. Vosk also performs speech recognition offline.

Buddy's memory is saved locally in `stickman_memory.json`, which should not be included in the public repository.

An optional Claude API backend is supported. If enabled, text and, depending on your settings, active window titles may be sent to the external AI provider.

Some optional desktop interactions can send keyboard or mouse input to other applications.

## Testing

The project includes unit-test support:

```bash
python -m unittest discover -s tests -v
```

Because Stickman Buddy relies on Windows desktop APIs, its transparent overlay, microphone input, text-to-speech, and multimedia features should also be tested on a Windows computer.

## Challenges and What I Learned

One of the biggest challenges was making an animated desktop character feel alive without making the application unresponsive.

I worked on integrating animation, desktop interaction, local AI conversations, and offline voice recognition into a single application. I also explored Qt's event loop, background threads, performance monitoring, and the trade-offs of running language models locally on limited hardware.

## Development and AI Assistance

I started Stickman Buddy by writing its initial project structure and Python code.

As the project became more complex, I used Claude extensively to help implement the animation system and additional features. I worked on integrating the components, testing functionality, troubleshooting problems, and refining the final experience.

The project was inspired in part by Alan Becker's *Animator vs. Animation*, but Stickman Buddy is an independent project and is not affiliated with that series.

## Future Improvements

- More animations and interactive behaviors
- Improvements to local AI response speed
- Better microphone and device configuration
- More customization options
- Boss fight (???)
- more performance optimization

## License

Stickman Buddy is released under the **GNU General Public License v3.0** (see [LICENSE](LICENSE)). It uses PyQt6, which is available under the GPL (or a commercial license), and the GPL is the straightforward way to stay compliant while sharing the source code.

The AI model and the speech model are downloaded separately and keep their own licenses: Qwen2.5 0.5B (through Ollama) and the Vosk small English model are both Apache 2.0. Other Python packages are installed from PyPI under their own licenses.

Copyright (C) 2026 Raphael John.

---

**Created by Raphael John (Code with RJ)**

Built for **Next Byte Hacks V5**.
