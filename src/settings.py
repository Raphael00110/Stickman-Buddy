"""Live switches (the tray menu flips these) and the stickman's look."""
SETTINGS = {
    "scared": True,         # reacts to the cursor at all
    "fighting": True,       # allowed to fight back when he snaps
    "chatty": True,         # speech bubbles
    "music_react": True,    # dances when a song is playing
    "mischief": True,       # harmless pranks: pause-and-resume your music, peek at the next tab and come back
    "skip_songs": False,    # may actually skip your song (off by default, he's cheeky not rude)
    "shove_cursor": False,  # CHAOS MODE: his hits nudge your real cursor a few pixels
    "sounds": True,         # cartoon sound effects (footsteps, boings, whooshes...)
    "sfx_volume": 0.6,      # 0.0 - 1.0 (tray menu: Quiet / Normal / Loud)
    "ai_director": False,    # the AI chooses what he does next (from a safe list)
    "interact": True,       # petting, tag, follow-me
    "sleepy": True,         # naps when you've been away, wakes up when you're back
    "break_reminders": True,  # nudges you to stretch after a long stretch of work
    "app_reactions": False,  # comments when you open an editor / chat / game / doc
    "fast_chat_mode": True,  # hackathon demo: no decorative AI requests competing with live conversations
    "remember_me": True,    # keeps friendship level + scores in stickman_memory.json
    "share_titles": True,   # send window titles to the AI so he can comment on what you're doing
    "shorts_watch": True,   # watches Shorts / Reels / TikTok with you and scrolls on command
    "shorts_mode": False,   # force Shorts mode on (needed for YouTube Shorts: its window title gives no hint)
    "voice": False,         # voice commands ("up", "go back"). Off until YOU turn the mic on.
    "draggable": True,      # you can pick him up with the mouse and throw him
    "recording_mode": False,  # 30 fps, no decorative ghost smears; useful with OBS
    "clean_repaint": False,   # redraw the whole overlay if Windows leaves transparency artifacts (slower)
    "perf_log": False,      # print frame-time stats to the console every 5 s (debugging lag)
    "speak": True,          # he talks OUT LOUD (Windows text-to-speech)
    "chat_level": 1,        # normal by default: 0 quiet, 1 normal, 2 chatty, 3 very chatty
    "tts_rate": 2,         # slower, clearer Windows speech; -10..10
    "tts_volume": 90,       # voice volume 0..100
    "tts_voice": "",        # voice name ('' = the Windows default). Pick one in the control panel.
    "voice_needs_name": False,  # if True, say "buddy up" / "hey go back" instead of just "up"
}

# ---- WHICH brain? "llama" = a local model through Ollama (free, private, works offline)  <- default
#                       (the name is historical: the model is LLAMA_MODEL below, Qwen2.5 0.5B by default)
# ----              "claude" = the Claude API (smarter, paid, needs an API key; chat text + window titles leave your PC)
BRAIN = "llama"
LLAMA_KEEP_ALIVE = "30m"            # keep the model in memory: reloading it every few minutes freezes everything for seconds
LLAMA_THREADS = None                # Let Ollama pick its own threads for best responsiveness
LLAMA_MODEL = "qwen2.5:0.5b"         # needs:  ollama pull qwen2.5:0.5b   (and Ollama running)

# ---- Claude settings (only used when BRAIN = "claude") The key is read from the ANTHROPIC_API_KEY environment variable,
# ---- or from a file called anthropic_api_key.txt next to the src/ folder. NEVER paste it in code.
AI_MODELS = dict(
    director="claude-haiku-5-5",    # picks his next action: fastest + cheapest
    quip="claude-haiku-5-5",        # one-liners (app reactions, events)
    chat="claude-sonnet-5-5",       # real conversations: smarter
)
AI_EFFORT = "low"                   # how hard the model thinks before answering (low = fast + cheap)
AI_MAX_CALLS_PER_HOUR = 400         # safety valve for your bill: past this he falls back to random moves

# ---- shorts / reels / tiktok scrolling
# "next" is what swiping UP does (next video); "back" is the previous one.
# These are the keys sent to the browser: YouTube Shorts, TikTok and Instagram Reels all use Down = next, Up = previous.
SHORTS_KEYS = {"next": "down", "back": "up"}

# ---- voice commands (offline, see voice.py)
VOICE_MIN_CONF = 0.70               # 0..1: how sure the recogniser must be. Raise it if it triggers by accident.

DIRECTOR_INTERVAL = 20      # seconds between AI "what should I do next?" calls (a local 1B model eats CPU
                            # while it answers, so asking every few seconds makes everything stutter)
BREAK_AFTER_MIN = 50        # minutes of continuous activity before the stretch reminder


# Match this to your GIF pack (flat colours + thick dark outline looks closest to the series)
STYLE = {
    "body": "#ff9f1c",
    "outline": "#1b1b1b",
}
