"""
He remembers you: friendship level, how long you were away, game scores.

Stored in stickman_memory.json next to the project folder. It is a few numbers
and counters, nothing you type and no window titles, and it never leaves your PC.
Untick "Remember me" in the tray menu and nothing is written to disk.
"""
import json
import os
import time
from pathlib import Path

from settings import SETTINGS

PATH = Path(__file__).resolve().parent.parent / "stickman_memory.json"

# (threshold, name) highest first
LEVELS = ((0.7, "best buddy"), (0.4, "friend"), (0.15, "acquaintance"), (0.0, "stranger"))

DEFAULTS = dict(affection=0.1, last_seen=None, sessions=0, pets=0, chats=0,
                tag_games=0, tag_caught=0, best_tag=0)


def level_for(affection):
    for threshold, name in LEVELS:
        if affection >= threshold:
            return name
    return "stranger"


class Memory:
    def __init__(self, path=PATH, persist=True, now=None):
        self.path = Path(path)
        self.persist = persist
        self.data = dict(DEFAULTS)
        self.away_hours = None
        now = time.time() if now is None else now
        if persist:
            self._load()
        last = self.data["last_seen"]
        if isinstance(last, (int, float)):
            self.away_hours = max(0.0, (now - last) / 3600.0)
            days = self.away_hours / 24.0
            a = self.data["affection"]
            if a > 0.1:                                   # being ignored cools things off a little
                self.data["affection"] = max(0.1, a - 0.01 * days)
        self.data["sessions"] += 1
        self.data["last_seen"] = now

    # ---------------------------------------------------------------- disk
    def _load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return                                         # missing or corrupt: start fresh
        if not isinstance(raw, dict):
            return
        for key, default in DEFAULTS.items():
            v = raw.get(key, default)
            if default is None:
                self.data[key] = v if isinstance(v, (int, float)) else None
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                self.data[key] = float(v) if isinstance(default, float) else int(v)
        self.data["affection"] = min(1.0, max(0.0, self.data["affection"]))

    def save(self):
        if not (self.persist and SETTINGS.get("remember_me", True)):
            return
        try:
            self.data["last_seen"] = time.time()
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)                     # atomic: never a half-written file
        except Exception as e:
            print(f"[memory] couldn't save: {e}")

    # ---------------------------------------------------------------- friendship
    @property
    def level(self):
        return level_for(self.data["affection"])

    def add_affection(self, amount):
        """Returns the new level name if this pushed him up a level, else None."""
        before = self.level
        self.data["affection"] = min(1.0, max(0.0, self.data["affection"] + amount))
        after = self.level
        return after if (amount > 0 and after != before) else None

    def bump(self, key, n=1):
        self.data[key] = self.data.get(key, 0) + n

    # ---------------------------------------------------------------- hello
    def greeting(self):
        h = self.away_hours
        if h is None:
            return "Hey! I'm your stickman. Be nice~"
        if h < 1:
            return "Back already? Hi!"
        if h < 20:
            return "Welcome back!"
        days = max(1, int(h // 24))
        if self.level in ("friend", "best buddy"):
            return "I missed you!" if days == 1 else f"{days} days?! I missed you!"
        return "Oh, it's you again."
