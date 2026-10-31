"""
Knows what's playing (Spotify, YouTube in a browser, any player Windows can
see) and can poke it: pause, resume, skip, and flip browser tabs.

Needs (Windows):  pip install winsdk pyautogui
 - winsdk gives real "now playing + paused?" info through the same system API
   that powers the Windows volume flyout.
 - Without it we fall back to window-title guessing (YouTube only) and media keys.
"""
import asyncio
import threading
import time

from settings import SHORTS_KEYS

BROWSERS = ("chrome", "msedge", "edge", "firefox", "brave", "opera", "vivaldi", "zen")
MUSIC_APPS = ("spotify", "music", "tidal", "deezer", "soundcloud", "amazon", "itunes")
MUSIC_HINTS = ("official audio", "lyrics", "lyric video", "music video", "(audio)", "remix",
               "- topic", "visualizer", "full album", "official video", "youtube music", " feat.", " ft.")


def classify_media(app, title="", artist=""):
    """'music' or 'video'. Spotify & friends are music; in a browser we guess from the title."""
    a = (app or "").lower()
    if any(k in a for k in MUSIC_APPS) and not any(b in a for b in BROWSERS):
        return "music"
    text = f"{title} {artist}".lower()
    if any(h in text for h in MUSIC_HINTS):
        return "music"
    return "video"


def _sdk():
    for mod in ("winsdk", "winrt"):
        try:
            m = __import__(f"{mod}.windows.media.control", fromlist=["x"])
            return m.GlobalSystemMediaTransportControlsSessionManager
        except Exception:
            continue
    return None


async def _read_state(M):
    mgr = await M.request_async()
    s = mgr.get_current_session()
    if s is None:
        return None
    info = await s.try_get_media_properties_async()
    playing = int(s.get_playback_info().playback_status) == 4      # 4 = PLAYING
    app = s.source_app_user_model_id or ""
    return dict(title=info.title or "", artist=info.artist or "", app=app, playing=playing,
                kind=classify_media(app, info.title or "", info.artist or ""))


class MediaWatcher(threading.Thread):
    """Polls the system media session every ~1.5s on a background thread."""

    def __init__(self, interval=1.5):
        super().__init__(daemon=True)
        self.interval = interval
        self.state = None
        self.available = False

    def run(self):
        M = _sdk()
        if M is None:
            return
        self.available = True
        while True:
            try:
                self.state = asyncio.run(_read_state(M))
            except Exception:
                self.state = None
            time.sleep(self.interval)


class MediaControl:
    """What the stickman is allowed to do to your media / browser."""

    def __init__(self):
        self.M = _sdk()

    def _session_call(self, method):
        async def go():
            mgr = await self.M.request_async()
            s = mgr.get_current_session()
            if s is not None:
                await getattr(s, method)()
        threading.Thread(target=lambda: asyncio.run(go()), daemon=True).start()

    @staticmethod
    def _key(*keys):
        try:
            import pyautogui
            pyautogui.hotkey(*keys) if len(keys) > 1 else pyautogui.press(keys[0])
        except Exception as e:
            print(f"[media] key press failed: {e}")

    def pause(self):
        self._session_call("try_pause_async") if self.M else self._key("playpause")

    def resume(self):
        self._session_call("try_play_async") if self.M else self._key("playpause")

    def next(self):
        self._session_call("try_skip_next_async") if self.M else self._key("nexttrack")

    def short(self, direction):
        """Scroll a Shorts / Reels / TikTok feed. 'next' = what swiping UP does, 'back' = previous video.
        Sends a plain Up/Down arrow key to the window in front (the overlay never takes focus)."""
        key = SHORTS_KEYS.get(direction)
        if key:
            self._key(key)

    def tab_next(self):
        self._key("ctrl", "tab")

    def tab_prev(self):
        self._key("ctrl", "shift", "tab")
