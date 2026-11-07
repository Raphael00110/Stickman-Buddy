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

Download the `vosk-model-small-en-us-0.15` model from:

https://alphacephei.com/vosk/models

Extract it into:

```text
models/
└── vosk-model-small-en-us-0.15/
```

Make sure Windows allows desktop applications to access your microphone.

By default, voice input can use your system's default recording device. If your version supports the `STICKMAN_MIC_DEVICE` environment variable, you can select a specific device in PowerShell:

```powershell
$env:STICKMAN_MIC_DEVICE = "15"
```

Replace `15` with the appropriate microphone index on your computer.

### 5. Launch Stickman Buddy

From the project directory:

```bash
python src/main.py
```

Buddy should appear on your desktop!

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

---

**Created by Raphael John (Code with RJ)**

Built for **Next Byte Hacks V5**.