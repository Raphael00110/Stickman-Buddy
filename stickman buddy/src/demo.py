"""Everything the control panel does (no Qt in here, so it can be tested)."""
from pathlib import Path

from fun import DEFAULT_SCRIPT, MOVE_GROUPS, SCENES, parse_script
from gifs import FX
from poses import POSES
from settings import SETTINGS
from sound import BANKS

SCRIPT_FILE = Path(__file__).resolve().parent.parent / "demo_script.txt"

LABELS = {
    "scared": "Scared of the cursor", "fighting": "Fights back", "chatty": "Speech bubbles", "speak": "Speak out loud",
    "music_react": "Dance to music", "mischief": "Pranks", "skip_songs": "May skip songs", "interact": "Pet / tag / follow",
    "sleepy": "Naps when I'm away", "break_reminders": "Break reminders", "app_reactions": "React to my apps",
    "ai_director": "AI picks his moves", "draggable": "Can be dragged", "shorts_watch": "Watch shorts with me",
    "sounds": "Sound effects", "share_titles": "Share window titles with the AI", "remember_me": "Remember me",
}


class DemoController:
    def __init__(self, app):
        self.app = app
        self._saved_level = None

    @property
    def m(self):
        return self.app.stickman_ui

    @property
    def b(self):
        return self.m.behavior

    # ---------------------------------------------------------------- what exists
    def moves(self):
        """{group: [moves]} but only moves he really has."""
        return {g: [n for n in names if hasattr(self.b, "a_" + n)] for g, names in MOVE_GROUPS.items()}

    def valid_moves(self):
        return {n for names in self.moves().values() for n in names}

    def poses(self):
        return sorted(POSES)

    def fx_names(self):
        return sorted(FX)

    def sound_names(self):
        return sorted(BANKS)

    def toggles(self):
        return [(k, LABELS.get(k, k.replace("_", " "))) for k, v in SETTINGS.items() if isinstance(v, bool)]

    # ---------------------------------------------------------------- do things
    def run_move(self, name):
        return self.b.command(name, True)

    def run_pose(self, name, secs=3.0):
        return self.b.command("pose", True, name, secs)

    def run_fx(self, name):
        return bool(self.m.fx(name, at="head", follow=True, loops=1))

    def run_sound(self, name):
        return bool(self.m.sfx.play(name, 1.0, 0.0, force=True))

    def say_text(self, text):
        text = (text or "").strip()
        if not text:
            return False
        self.m.say(text, max(2.5, len(text) / 11.0), voice="force")
        return True

    def ask_ai(self, text):
        text = (text or "").strip()
        if text:
            self.app.chat_with_ai(text)
        return bool(text)

    def run_script(self, text):
        """-> (number of steps, [errors]). Nothing runs if there are errors."""
        steps, errors = parse_script(text, self.valid_moves(), set(POSES), set(FX), set(BANKS))
        if errors:
            return 0, errors
        if not steps:
            return 0, ["The script is empty."]
        self.b.script = steps
        self.b.command("script", True)
        return len(steps), []

    def run_scene(self, name):
        return self.run_script(SCENES[name])

    def stop(self):
        """Stop whatever he's doing/saying and put everything back to normal."""
        b, m = self.b, self.m
        b.pending_cmd = None
        b.cancel()
        m.speaker.stop()
        m._say_queue.clear()
        m._bubble = None
        m._bubble_voiced = False
        m.opacity = m.body_scale = 1.0
        m.clear_pose()

    def set_setting(self, key, value):
        SETTINGS[key] = value
        act = getattr(self.app, "act_" + key, None)           # keep the tray tick in sync
        if act is not None and isinstance(value, bool):
            act.setChecked(value)

    def set_demo_mode(self, on):
        """Auto-show selects showcase moves; it does not override the user's speech preference."""
        self.b.demo_mode = bool(on)

    def voices(self):
        self.m.speaker.ensure_started()
        return list(self.m.speaker.voices)

    def test_voice(self):
        return self.m.speaker.say("Testing, one, two, three. Can you hear me?")

    def default_script(self):
        try:
            return SCRIPT_FILE.read_text(encoding="utf-8")
        except OSError:
            return DEFAULT_SCRIPT

    def save_script(self, text):
        SCRIPT_FILE.write_text(text, encoding="utf-8")
        return str(SCRIPT_FILE)
