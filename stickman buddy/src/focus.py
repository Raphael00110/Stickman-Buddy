"""A reversible quiet/focus preset for Stickman Buddy.

This module has no GUI dependency, so its behaviour can be unit-tested.
"""

FOCUS_OVERRIDES = {
    "ai_director": False,
    "app_reactions": False,
    "music_react": False,
    "mischief": False,
    "skip_songs": False,
    "shove_cursor": False,
    "break_reminders": False,
    "shorts_watch": False,
    "voice": False,
    "chatty": False,
    "speak": False,
    "sounds": False,
    "scared": False,
    "fighting": False,
    "interact": False,
    "chat_level": 0,
}


class FocusPreset:
    """Remember preferences when focus starts, and restore them when it ends."""

    def __init__(self, settings):
        self.settings = settings
        self._before = None

    @property
    def active(self):
        return self._before is not None

    def set_active(self, enabled):
        enabled = bool(enabled)
        if enabled == self.active:
            return False
        if enabled:
            self._before = {key: self.settings[key] for key in FOCUS_OVERRIDES}
            self.settings.update(FOCUS_OVERRIDES)
        else:
            self.settings.update(self._before)
            self._before = None
        return True
