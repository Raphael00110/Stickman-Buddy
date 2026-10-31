import random
import sys
import threading
import time

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QInputDialog
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction, QActionGroup
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, Qt

from mascot import Mascot
from settings import SETTINGS, BREAK_AFTER_MIN
from focus import FocusPreset
import routines
from perception import ScreenMonitor
from brain import MascotBrain
from action import ActionEngine
from context import classify, is_short_form, shorts_capable
from perf import timed, tune_runtime, settle_memory
from demo import DemoController
from panel import DemoPanel
from mini_panel import MiniDemoBar
from voice_chat import VoiceChat
from platforms import (panic_combo, talk_combo, panel_combo, mini_combo, voice_chat_combo, idle_seconds, foreground_hwnd,
                       restore_foreground)
from memory import Memory
from voice import VoiceListener
from behavior import match_command, ACKS
from media import MediaWatcher, MediaControl, classify_media


# what he says (and does) when you open certain kinds of apps
APP_PROMPTS = dict(
    code="I just opened my code editor. In one short, playful sentence, say something supportive or funny about coding.",
    chat="I just opened a chat app. In one short, playful sentence, say something about chatting with friends.",
    game="I just opened a game. In one short, hype sentence, cheer me on.",
    docs="I just opened a document editor. In one short, playful sentence, say something encouraging about writing.",
)
APP_MOVES = dict(code="think", chat="wave", game="cheer", docs="think")


class Bridge(QObject):
    """Hands AI replies from a background thread back to the UI thread safely."""
    reply = pyqtSignal(object, str)
    decision = pyqtSignal(object, object)

    def __init__(self):
        super().__init__()
        self.reply.connect(self._dispatch)
        self.decision.connect(self._dispatch_decision)

    def _dispatch(self, callback, text):
        callback(text)

    def _dispatch_decision(self, callback, result):
        callback(result)


class AppController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        screen = self.app.primaryScreen()
        g, dpr = screen.geometry(), screen.devicePixelRatio()
        self.center_ui = (g.width() // 2, g.height() // 2)             # where the stickman smashes
        self.center_click = (int((g.x() + g.width() / 2) * dpr),       # where pyautogui really clicks
                             int((g.y() + g.height() / 2) * dpr))
        self.stickman_ui = Mascot()
        self.screen_monitor = ScreenMonitor()
        self.brain = MascotBrain()
        self.action = ActionEngine()
        self.focus = FocusPreset(SETTINGS)
        self.bridge = Bridge()
        self._chat_in_flight = False  # only one direct user question at once

        self.last_seen_window = ""
        self.cooldowns = {}
        self.last_quip = 0.0
        self.window_is_video = False
        self.media_key, self.media_was_playing = None, False
        self.stickman_ui.behavior.hook = self.on_quip
        self.stickman_ui.behavior.ai = self.ask_director

        # he remembers you between sessions (see memory.py; toggle in the tray menu)
        self.memory = Memory(persist=True)
        self.stickman_ui.behavior.mem = self.memory
        self.app.aboutToQuit.connect(self.memory.save)
        self.active_since = time.monotonic()
        self._talk_down, self._talking = False, False
        self._pre_ctx = ("", 0)            # (title, hwnd) of the window you were in before the typing box opened
        self._capable_ctx = ("", 0)        # last window that could scroll a feed
        self._hint_t = 0.0

        # offline voice commands: the thread idles and the mic stays CLOSED until you tick "Voice commands"
        self.voice = VoiceListener(self.on_voice_command, self.on_voice_status)
        self.voice.start()
        self.app.aboutToQuit.connect(self.voice.stop)
        self.voice_chat = VoiceChat(self.on_voice_chat_text, self.on_voice_chat_status)
        self.demo = DemoController(self)          # the control panel's brain (demo.py)
        self.panel, self._panel_down = None, False
        self.mini_bar, self._mini_down, self._voice_chat_down = None, False, False

        # what's playing, and what he's allowed to do about it
        self.media = MediaWatcher()
        self.media.start()
        self.stickman_ui.behavior.actions = MediaControl()

        self._build_tray()

        # Regular jobs are grouped here so a reader can see the app's rhythm.
        self._start_timers()

    def _start_timer(self, interval_ms, callback):
        """Call `callback` repeatedly on the Qt GUI event loop."""
        timer = QTimer(self.app)
        timer.timeout.connect(callback)
        timer.start(interval_ms)
        return timer

    def _start_timers(self):
        """Polling schedules in milliseconds; no extra thread per timer."""
        self.timer = self._start_timer(1000, self.check_screen_heartbeat)
        self.media_timer = self._start_timer(1000, self.check_media)
        self.panic_timer = self._start_timer(100, self.check_panic_hotkey)
        self.social_timer = self._start_timer(1000, self.check_social)
        self.hotkey_timer = self._start_timer(100, self.check_hotkeys)
        self.save_timer = self._start_timer(60000, self.autosave)

    def check_panic_hotkey(self):
        """Ctrl+Alt+Q always closes the companion quickly."""
        if panic_combo():
            self.app.quit()

    # ---- tray icon: the always-available off switch ---------------------------
    def _build_tray(self):
        pm = QPixmap(32, 32)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setBrush(QColor("#ff9f1c"))
        p.drawEllipse(6, 2, 20, 20)
        p.drawRect(14, 20, 4, 10)
        p.end()
        self.tray = QSystemTrayIcon(QIcon(pm), self.app)
        menu = QMenu()
        mini_act = QAction("Compact demo remote   (Ctrl+Alt+M)", menu)
        mini_act.triggered.connect(self.toggle_mini_bar)
        menu.addAction(mini_act)
        mic_act = QAction("Talk with microphone   (Ctrl+Alt+V)", menu)
        mic_act.triggered.connect(self.start_voice_chat)
        menu.addAction(mic_act)
        panel_act = QAction("Open control panel...   (Ctrl+Alt+P)", menu)
        panel_act.triggered.connect(self.toggle_panel)
        menu.addAction(panel_act)
        talk_act = QAction("Talk to him...   (Ctrl+Alt+T)", menu)
        talk_act.triggered.connect(self.talk)
        menu.addAction(talk_act)
        play_menu = menu.addMenu("Play with him")
        for label, cmd in (("Play tag", "tag"), ("Come here", "follow"), ("Dance!", "dance"),
                           ("Do a flip", "flip"), ("Take a nap", "nap")):
            act = QAction(label, play_menu)
            act.triggered.connect(lambda _c=False, c=cmd: self.stickman_ui.behavior.command(c, force=True))
            play_menu.addAction(act)
        menu.addSeparator()
        self.focus_action = QAction("Focus mode (quiet, reversible)", menu, checkable=True)
        self.focus_action.toggled.connect(self.toggle_focus_mode)
        menu.addAction(self.focus_action)
        menu.addSeparator()
        for key, label in (("scared", "Scared of the cursor"),
                           ("fighting", "Allowed to fight back"),
                           ("chatty", "Speech bubbles"),
                           ("music_react", "Dance when music plays"),
                           ("mischief", "Pranks (pause music briefly, peek at next tab)"),
                           ("skip_songs", "Allowed to skip my songs"),
                           ("shove_cursor", "CHAOS: his hits nudge my real cursor"),
                           ("sounds", "Sound effects"),
                           ("ai_director", "AI chooses what he does"),
                           ("interact", "Play: pet him, tag, follow me"),
                           ("sleepy", "Naps when I'm away"),
                           ("break_reminders", "Break reminders"),
                           ("app_reactions", "React to the apps I open"),
                           ("remember_me", "Remember me between sessions"),
                           ("share_titles", "Share window titles with the AI"),
                           ("shorts_watch", "Watch Shorts / Reels / TikTok with me"),
                           ("shorts_mode", "Shorts mode ON (needed for YouTube Shorts)"),
                           ("voice", "Voice commands (microphone)"),
                           ("voice_needs_name", "Voice: say 'buddy' first"),
                           ("draggable", "Let me pick him up and throw him"),
                           ("recording_mode", "Recording mode (30 fps, no motion smear)"),
                           ("clean_repaint", "Clean repaint (if trails persist; uses more CPU)"),
                           ("perf_log", "Print performance stats (debugging lag)"),
                           ("speak", "Speak out loud (text-to-speech)")):
            act = QAction(label, menu, checkable=True)
            act.setChecked(SETTINGS[key])
            act.toggled.connect(lambda on, k=key: SETTINGS.__setitem__(k, on))
            menu.addAction(act)
            setattr(self, "act_" + key, act)
        vol_menu = menu.addMenu("Sound volume")
        self._vol_group = QActionGroup(vol_menu)
        for label, v in (("Quiet", 0.3), ("Normal", 0.6), ("Loud", 0.9)):
            act = QAction(label, vol_menu, checkable=True)
            act.setChecked(abs(SETTINGS["sfx_volume"] - v) < 0.01)
            act.triggered.connect(lambda _checked=False, v=v: SETTINGS.__setitem__("sfx_volume", v))
            self._vol_group.addAction(act)
            vol_menu.addAction(act)
        menu.addSeparator()
        quit_act = QAction("Quit", menu)
        quit_act.triggered.connect(self.app.quit)
        menu.addAction(quit_act)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Stickman (Ctrl+Alt+Q to quit)")
        self.tray.show()

    def toggle_focus_mode(self, on):
        """Silence interruptions without losing the user's previous preferences."""
        if not self.focus.set_active(on):
            return
        if on:
            self.demo.stop()
            self.demo.set_demo_mode(False)
            self.stickman_ui.speaker.stop()
        for key in self.focus.settings:
            action = getattr(self, "act_" + key, None)
            if action is not None and action.isChecked() != bool(SETTINGS[key]):
                action.blockSignals(True)
                action.setChecked(bool(SETTINGS[key]))
                action.blockSignals(False)

    # ---- helpers --------------------------------------------------------------
    def _ready(self, key, cooldown_seconds):
        now = time.monotonic()
        if now - self.cooldowns.get(key, -1e9) < cooldown_seconds:
            return False
        self.cooldowns[key] = now
        return True

    def ask_brain(self, message, context, callback):
        """Decorative quips are optional; user conversations have priority."""
        # Background AI costs CPU and competes with direct chats. Respect the
        # App reactions setting for every background quip, not just app opens.
        if SETTINGS.get("fast_chat_mode", True) or not SETTINGS.get("app_reactions", False) or self._chat_in_flight:
            return
        def job():
            try:
                text = self.brain.generate_reply(user_message=message, screen_context=context)
            except Exception as e:
                print(f"Brain error: {e}")
                text = self.brain.explain(e)
            if text and text != "..." and not self._chat_in_flight:
                self.bridge.reply.emit(callback, text)
        threading.Thread(target=job, daemon=True).start()

    def ask_director(self, state, options, recent, callback):
        """The AI picks an idle move, but never gets priority over a chat."""
        if SETTINGS.get("fast_chat_mode", True) or self._chat_in_flight:
            self.bridge.decision.emit(callback, None)
            return
        def job():
            try:
                result = self.brain.choose_action(state, options, recent)
            except Exception as e:
                print(f"Director error: {e}")
                result = None
            self.bridge.decision.emit(callback, result)
        threading.Thread(target=job, daemon=True).start()

    def on_quip(self, kind):
        """Occasionally let the AI write his reaction instead of a canned line."""
        if SETTINGS.get("fast_chat_mode", True) or not SETTINGS.get("app_reactions", False):
            return False
        if time.monotonic() - self.last_quip < (999, 40, 20, 10)[max(0, min(3, int(SETTINGS.get("chat_level", 2))))]:
            return False
        self.last_quip = time.monotonic()
        self.ask_brain(
            f"You're a chaotic little stickman living on my screen. Event: {kind}. "
            "React in 8 words or fewer.", "", lambda t: self.stickman_ui.say(t, 3))
        return True

    # ---- privacy ----------------------------------------------------------------
    def _ctx(self, title):
        """Window titles go to the cloud AI only while 'Share window titles with the AI' is ticked."""
        return title if SETTINGS["share_titles"] else ""

    # ---- watching Shorts / Reels / TikTok together --------------------------------
    def shorts_active(self, title=None):
        """True when a feed is in front: TikTok / Instagram / Reels spotted from the window title, or
        Shorts mode switched on by you. It ALWAYS also needs a window that can scroll (a browser or
        the app), so he never sends arrow keys to your editor or a game."""
        t = self.last_seen_window if title is None else title
        if not SETTINGS["shorts_watch"]:
            return False
        return (SETTINGS["shorts_mode"] or is_short_form(t)) and shorts_capable(t)

    def on_shorts_detected(self):
        how = ("Say 'up' or 'go back'." if SETTINGS["voice"]
               else "Press Ctrl+Alt+T and type 'up' or 'go back'.")
        if SETTINGS["chatty"]:
            self.stickman_ui.say(f"Ooh, shorts! I'll watch with you. {how}", 6)

    def run_short_command(self, action, title=None, hwnd=0):
        """'up' / 'go back', from your voice or the typing box. Only acts when a feed is in front."""
        b = self.stickman_ui.behavior
        if not self.shorts_active(title):
            self._shorts_hint(title)
            return False
        b.shorts = True
        if hwnd:
            restore_foreground(hwnd)                      # the typing box had focus: hand it back first
        return b.command(action, force=True)

    def _shorts_hint(self, title=None):
        now = time.monotonic()
        if now - self._hint_t < 8 or not SETTINGS["chatty"]:
            return
        self._hint_t = now
        t = self.last_seen_window if title is None else title
        if not SETTINGS["shorts_watch"]:
            msg = "Shorts watching is off in my tray menu."
        elif not shorts_capable(t):
            msg = "I don't see any shorts open."
        else:
            msg = "Is this a Short? Tick 'Shorts mode' in my tray menu (or type: shorts on)."
        self.stickman_ui.say(msg, 4)

    # ---- voice: runs on its own thread, so everything is handed to the UI thread ---
    def on_voice_command(self, action):
        self.bridge.reply.emit(lambda _t, a=action: self.run_short_command(a), "")

    def on_voice_status(self, message, fatal):
        self.bridge.reply.emit(lambda _t, mm=message, f=fatal: self._voice_status_ui(mm, f), "")

    def _voice_status_ui(self, message, fatal):
        self.stickman_ui.say(message, 5)
        if fatal:
            self.act_voice.setChecked(False)              # keep the tray tick honest

    def _check_brain(self):
        """Background start-up check. If the AI isn't reachable he tells you once how to fix it."""
        try:
            hint = self.brain.setup_hint()
        except Exception as e:
            hint = self.brain.explain(e)
        if hint:
            time.sleep(5)                                 # let the greeting finish first
            self.bridge.reply.emit(lambda _t: self.stickman_ui.say(hint, 8), "")

    # ---- control panel -------------------------------------------------------------
    def toggle_panel(self):
        if self.panel is None:
            self.panel = DemoPanel(self.demo)
        if self.panel.isVisible():
            self.panel.hide()
        else:
            self.panel.show()
            self.panel.raise_()

    def toggle_mini_bar(self):
        """Compact buttons for recording; hide with Ctrl+Alt+M or its Hide button."""
        if self.mini_bar is None:
            self.mini_bar = MiniDemoBar(self.demo)
        if self.mini_bar.isVisible():
            self.mini_bar.hide()
        else:
            self.mini_bar.show_near_corner()

    def start_voice_chat(self):
        """Record one spoken sentence. Unlike voice commands, this accepts natural questions."""
        if self.voice_chat.busy:
            return
        # The other Vosk listener uses the same mic for Shorts commands.
        # Close it first so two simultaneous streams don't fight over the device.
        was_listening_for_shorts = SETTINGS.get("voice", False)
        if was_listening_for_shorts:
            self.act_voice.setChecked(False)
        self.stickman_ui.speaker.stop()   # don't transcribe the stickman's own voice
        self.stickman_ui.say("I'm listening...", 2, voice=None)
        self.voice_chat.listen_once(delay=0.7 if was_listening_for_shorts else 0.0)

    def on_voice_chat_text(self, text):
        self.bridge.reply.emit(self._handle_voice_chat_text, text)

    def _handle_voice_chat_text(self, text):
        print(f"[voice chat] Heard: {text}")
        self.stickman_ui.say(f"You said: {text}", 2, voice=None)
        self.handle_user_text(text)  # reuse typed commands and AI chat handling

    def on_voice_chat_status(self, message):
        self.bridge.reply.emit(self._show_voice_chat_status, message)

    def _show_voice_chat_status(self, message):
        print(f"[voice chat] {message}")
        if "unavailable" in message or "didn't catch" in message or "missing" in message:
            self.stickman_ui.say(message, 4.5, voice=None)

    # ---- talking to him -------------------------------------------------------
    def talk(self):
        """A tiny always-on-top box. Short commands ('play tag', 'come here', 'dance',
        'go to sleep', 'up', 'go back') act instantly; anything else is a real chat with the AI."""
        if self._talking:
            return
        self._talking = True
        self._pre_ctx = (self.last_seen_window, foreground_hwnd())   # so scroll keys land in the right window
        try:
            dlg = QInputDialog()
            dlg.setWindowTitle("Talk to your stickman")
            dlg.setLabelText("Say something  (try: play tag, come here, dance, up, go back)")
            dlg.setInputMode(QInputDialog.InputMode.TextInput)
            dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            ok = dlg.exec()
            text = dlg.textValue().strip() if ok else ""
        finally:
            self._talking = False
        if text:
            self.handle_user_text(text)

    def handle_user_text(self, text):
        m, b = self.stickman_ui, self.stickman_ui.behavior
        self.memory.bump("chats")
        b._gain(0.01)
        cmd = match_command(text)
        if cmd in ("short_next", "short_back"):           # scroll the feed in front of the typing box
            title, hwnd = self._pre_ctx
            if not shorts_capable(title):                 # opened from the tray menu? use the last feed window
                title, hwnd = self._capable_ctx
            self.run_short_command(cmd, title, hwnd)
            return
        if cmd in ("shorts_on", "shorts_off"):
            self.act_shorts_watch.setChecked(True)
            self.act_shorts_mode.setChecked(cmd == "shorts_on")
            m.say(random.choice(ACKS[cmd]), 2.5, voice="force")
            return
        if cmd:                                           # instant + reliable (no AI needed)
            if b.command(cmd, force=True):
                m.say(random.choice(ACKS[cmd]), 2.5, voice="force")
            return
        self.chat_with_ai(text)

    def chat_with_ai(self, text):
        """A real conversation, with a bounded Ollama request and terminal diagnostics."""
        if self._chat_in_flight:
            self.stickman_ui.say("One moment, I'm still answering!", 3, voice=None)
            return
        self._chat_in_flight = True
        self.stickman_ui.behavior.command("think", force=True)
        self.stickman_ui.say("Hmm, let me think...", 8, voice=None)
        context = self._ctx(self.last_seen_window)
        relationship = self.memory.level

        def job():
            start = time.monotonic()
            print(f"[chat] Sending to local AI: {text[:100]!r}", flush=True)
            try:
                reply = self.brain.chat(text, context, relationship)
            except Exception as e:
                print(f"[chat] AI error ({type(e).__name__}): {e}", flush=True)
                reply = self.brain.explain(e)
            print(f"[chat] Response in {time.monotonic() - start:.1f}s: {reply!r}", flush=True)
            self.bridge.reply.emit(self._say_long, str(reply or "I couldn't get a reply. Please try again."))
        threading.Thread(target=job, daemon=True, name="user-ai-chat").start()

    def _say_long(self, text):
        self._chat_in_flight = False
        text = text.strip().strip('"') or "I couldn't get a reply. Please try again."
        if len(text) > 140:
            text = text[:137].rstrip() + "..."
        self.stickman_ui.say(text, max(3.5, len(text) / 14), voice="force")

    @timed("hotkeys")
    def check_hotkeys(self):
        down = talk_combo()
        if down and not self._talk_down:
            self.talk()
        self._talk_down = down
        pdown = panel_combo()
        if pdown and not self._panel_down:
            self.toggle_panel()
        self._panel_down = pdown
        mdown = mini_combo()
        if mdown and not self._mini_down:
            self.toggle_mini_bar()
        self._mini_down = mdown
        vdown = voice_chat_combo()
        if vdown and not self._voice_chat_down:
            self.start_voice_chat()
        self._voice_chat_down = vdown

    # ---- presence: idle, naps, break reminders, slow bonding -------------------
    @timed("social")
    def check_social(self):
        b = self.stickman_ui.behavior
        idle = idle_seconds()
        b.idle_for = idle
        now = time.monotonic()
        if idle > 300:                                    # you took a real break: the clock restarts
            self.active_since = now
        if (SETTINGS["break_reminders"] and idle < 30
                and now - self.active_since > BREAK_AFTER_MIN * 60):
            if b.command("stretch"):                      # (waits politely if you're watching a video)
                self.active_since = now

    @timed("autosave")
    def autosave(self):
        b = self.stickman_ui.behavior
        if b.idle_for < 60:
            b._gain(0.002)
        self.memory.save()

    def on_app(self, kind, title):
        m, b = self.stickman_ui, self.stickman_ui.behavior
        b.command(APP_MOVES[kind])
        self.ask_brain(APP_PROMPTS[kind], self._ctx(title),
                       lambda t: SETTINGS["chatty"] and m.say(t, 5))

    # ---- companion reactions --------------------------------------------------
    def on_network(self, title):
        m = self.stickman_ui
        box = {}
        m.run_routine(routines.smash_when_ready(
            m, box, *self.center_ui,
            on_hit=lambda: self.action.smash_button(target_x=self.center_click[0],
                                                    target_y=self.center_click[1])))

        def got_reply(text):
            print(f"Stickman says: {text}")
            box["text"] = text

        self.ask_brain("Look at what I opened!", self._ctx(title), got_reply)

    def on_video(self, title):
        m = self.stickman_ui
        self.ask_brain(
            "I just opened a video. In one short, casual sentence, ask me what I'm watching.",
            self._ctx(title), lambda text: m.say(text, 6))

    # ---- heartbeat ------------------------------------------------------------
    @timed("window heartbeat")
    def check_screen_heartbeat(self):
        title = self.screen_monitor.get_active_window_title()
        if title == self.last_seen_window:
            return
        self.last_seen_window = title

        kind = classify(title)
        self.window_is_video = kind == "video"
        self.stickman_ui.behavior.window = self._ctx(title)   # goes to the cloud AI only if you allow it
        self.stickman_ui.behavior.window_kind = kind
        self.stickman_ui.behavior.browser_active = any(b in title.lower() for b in (
            "chrome", "edge", "firefox", "brave", "opera", "vivaldi"))
        if shorts_capable(title):
            self._capable_ctx = (title, foreground_hwnd())
        self._update_mode()
        if kind == "network" and SETTINGS.get("app_reactions", False) and self._ready("network", 30):
            self.on_network(title)
        elif kind == "video" and SETTINGS.get("app_reactions", False) and self._ready("video", 120):
            self.on_video(title)
        elif kind in APP_PROMPTS and SETTINGS["app_reactions"] and self._ready(kind, 300):
            self.on_app(kind, title)
        elif kind == "shorts" and self.shorts_active() and self._ready("shorts", 600):
            self.on_shorts_detected()

    # ---- media ----------------------------------------------------------------
    def _current_media(self):
        """Real now-playing info if winsdk is installed, otherwise guess from a YouTube title."""
        if self.media.available:
            return self.media.state
        t = self.last_seen_window
        if " - YouTube" in t:
            title = t.replace(" - YouTube", "")
            return dict(title=title, artist="", app="chrome", playing=True,
                        kind=classify_media("chrome", title))
        return None

    def _update_mode(self):
        st = self.media_state
        # a video playing in a BACKGROUND tab doesn't count: only when it's the window you're looking at
        in_front = bool(st and st.get("title")) and st["title"][:30].lower() in self.last_seen_window.lower()
        video_playing = bool(st and st["playing"] and st["kind"] == "video" and in_front)
        b = self.stickman_ui.behavior
        b.shorts = self.shorts_active()
        b.mode = "watch" if (video_playing or self.window_is_video or b.shorts) else None

    media_state = None

    @timed("media")
    def check_media(self):
        st = self._current_media()
        playing = bool(st and st["playing"])
        self.media_state = st if playing else None
        b = self.stickman_ui.behavior
        b.media = self.media_state
        key = (st["title"], st["artist"]) if st else None
        if playing and (key != self.media_key or not self.media_was_playing):
            b.song_changed(st)
        self.media_key, self.media_was_playing = key, playing
        self._update_mode()

    def run(self):
        self.stickman_ui.show()
        self.stickman_ui.run_routine(routines.greet(self.stickman_ui, self.memory.greeting()))
        threading.Thread(target=self._check_brain, daemon=True).start()   # is the AI actually reachable?
        settle_memory()                                   # freeze start-up objects out of the garbage collector
        sys.exit(self.app.exec())


if __name__ == "__main__":
    tune_runtime()
    controller = AppController()
    controller.run()
