"""The control panel window: every move, pose, effect and sound on a button, a 'say anything' box, a script
runner for your demo video, and the talk / voice settings. All the logic lives in demo.py."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QPlainTextEdit, QPushButton, QScrollArea, QSlider, QTabWidget, QVBoxLayout, QWidget)

from fun import DEFAULT_SCRIPT, SAY_PRESETS, SCENES
from settings import SETTINGS

STYLE = """
QWidget { background: #1e1f26; color: #eceff4; font-size: 13px; }
QPushButton { background: #31334a; border: 1px solid #454866; border-radius: 6px; padding: 6px 10px; }
QPushButton:hover { background: #4a4d73; }
QPushButton#big { background: #ff9f1c; color: #1b1b1b; font-weight: bold; }
QPushButton#stop { background: #d64545; font-weight: bold; }
QGroupBox { border: 1px solid #3a3d55; border-radius: 6px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #ff9f1c; }
QLineEdit, QPlainTextEdit, QComboBox { background: #2a2c3d; border: 1px solid #454866; border-radius: 4px; padding: 4px; }
QTabBar::tab { padding: 7px 12px; }
"""
LEVELS = ["Quiet", "Normal", "Chatty", "Nonstop"]


class DemoPanel(QWidget):
    def __init__(self, demo):
        super().__init__()
        self.demo = demo
        self.setWindowTitle("Stickman Control Panel")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setStyleSheet(STYLE)
        self.resize(600, 680)

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        for name in SCENES:
            b = QPushButton(name)
            b.setObjectName("big")
            b.clicked.connect(lambda checked=False, n=name: self._scene(n))
            top.addWidget(b)
        stop = QPushButton("STOP")
        stop.setObjectName("stop")
        stop.clicked.connect(self._stop)
        top.addWidget(stop)
        root.addLayout(top)
        auto = QCheckBox("Auto-show mode (showcase moves; speech follows your settings)")
        auto.toggled.connect(lambda on: self._note("Auto-show " + ("ON" if on else "off")) or self.demo.set_demo_mode(on))
        root.addWidget(auto)

        tabs = QTabWidget()
        tabs.addTab(self._buttons([(g, ns, self.demo.run_move) for g, ns in self.demo.moves().items() if ns]), "Moves")
        tabs.addTab(self._buttons([("Poses (3 s)", self.demo.poses(), self.demo.run_pose),
                                   ("Effects", self.demo.fx_names(), self.demo.run_fx),
                                   ("Sounds", self.demo.sound_names(), self.demo.run_sound)]), "Poses / FX / Sounds")
        tabs.addTab(self._say_tab(), "Talk")
        tabs.addTab(self._script_tab(), "Script")
        tabs.addTab(self._settings_tab(), "Settings")
        root.addWidget(tabs)
        self.status = QLabel("Ready. Press a button, or Ctrl+Alt+P to hide this panel.")
        root.addWidget(self.status)

    # ---------------------------------------------------------------- helpers
    def _note(self, text):
        self.status.setText(text)

    def _buttons(self, sections, cols=3):
        """sections = [(title, [names], callback)]"""
        inner = QWidget()
        lay = QVBoxLayout(inner)
        for title, names, fn in sections:
            box = QGroupBox(title)
            grid = QGridLayout(box)
            for i, name in enumerate(names):
                btn = QPushButton(name.replace("_", " "))
                btn.clicked.connect(lambda checked=False, n=name, f=fn: self._press(f, n))
                grid.addWidget(btn, i // cols, i % cols)
            lay.addWidget(box)
        lay.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        return scroll

    def _press(self, fn, name):
        ok = fn(name)
        self._note(f"{name}: " + ("started" if ok else "couldn't do that right now"))

    def _stop(self):
        self.demo.stop()
        self._note("Stopped.")

    def _scene(self, name):
        n, errors = self.demo.run_scene(name)
        self._note(f"{name}: {n} steps" if not errors else "; ".join(errors))

    # ---------------------------------------------------------------- talk
    def _say_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.say_box = QLineEdit()
        self.say_box.setPlaceholderText("Type something for him to say (or to ask the AI)...")
        self.say_box.returnPressed.connect(self._say)
        lay.addWidget(self.say_box)
        row = QHBoxLayout()
        b1 = QPushButton("Say it")
        b1.clicked.connect(self._say)
        b2 = QPushButton("Ask the AI")
        b2.clicked.connect(self._ask)
        row.addWidget(b1)
        row.addWidget(b2)
        lay.addLayout(row)
        box = QGroupBox("Quick lines")
        v = QVBoxLayout(box)
        for text in SAY_PRESETS:
            b = QPushButton(text)
            b.clicked.connect(lambda checked=False, t=text: self._note("Said it" if self.demo.say_text(t) else "Nothing to say"))
            v.addWidget(b)
        lay.addWidget(box)

        vbox = QGroupBox("His voice")
        vl = QVBoxLayout(vbox)
        spk = QCheckBox("Speak out loud")
        spk.setChecked(bool(SETTINGS.get("speak", True)))
        spk.toggled.connect(lambda on: self.demo.set_setting("speak", on))
        vl.addWidget(spk)
        self.voice_combo = QComboBox()
        self.voice_combo.currentIndexChanged.connect(self._voice_picked)
        vl.addWidget(self.voice_combo)
        for label, key, lo, hi in (("Speed", "tts_rate", -10, 10), ("Volume", "tts_volume", 0, 100)):
            vl.addWidget(QLabel(label))
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(lo, hi)
            s.setValue(int(SETTINGS.get(key, 0)))
            s.valueChanged.connect(lambda v, k=key: self.demo.set_setting(k, v))
            vl.addWidget(s)
        test = QPushButton("Test voice")
        test.clicked.connect(lambda: self._note("Testing the voice..." if self.demo.test_voice() else "Voice isn't available"))
        vl.addWidget(test)
        lay.addWidget(vbox)
        lay.addStretch()
        return w

    def _say(self):
        self._note("Said it" if self.demo.say_text(self.say_box.text()) else "Type something first")

    def _ask(self):
        self._note("Asking the AI..." if self.demo.ask_ai(self.say_box.text()) else "Type something first")

    def _voice_picked(self, index):
        self.demo.set_setting("tts_voice", "" if index <= 0 else self.voice_combo.itemText(index))

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(700, self._refresh_voices)

    def _refresh_voices(self):
        names = self.demo.voices()
        self.voice_combo.clear()
        self.voice_combo.addItems(["(Windows default)"] + names)

    # ---------------------------------------------------------------- script
    def _script_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("One command per line: say, do, pose, fx, sound, emote, wait.  Lines starting with # are notes."))
        self.script_box = QPlainTextEdit()
        self.script_box.setPlainText(self.demo.default_script())
        lay.addWidget(self.script_box)
        row = QHBoxLayout()
        for label, fn in (("Run", self._run_script), ("Stop", self._stop), ("Reset to example", self._reset_script),
                          ("Save to demo_script.txt", self._save_script)):
            b = QPushButton(label)
            b.setObjectName("big" if label == "Run" else "")
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        return w

    def _run_script(self):
        n, errors = self.demo.run_script(self.script_box.toPlainText())
        self._note(f"Running {n} steps" if not errors else "Fix this first: " + " | ".join(errors[:3]))

    def _reset_script(self):
        self.script_box.setPlainText(DEFAULT_SCRIPT)

    def _save_script(self):
        self._note("Saved to " + self.demo.save_script(self.script_box.toPlainText()))

    # ---------------------------------------------------------------- settings
    def _settings_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("How talkative is he?"))
        level = QComboBox()
        level.addItems(LEVELS)
        level.setCurrentIndex(max(0, min(3, int(SETTINGS.get("chat_level", 2)))))
        level.currentIndexChanged.connect(lambda i: self.demo.set_setting("chat_level", i))
        lay.addWidget(level)
        box = QGroupBox("Behaviours")
        v = QVBoxLayout(box)
        for key, label in self.demo.toggles():
            c = QCheckBox(label)
            c.setChecked(bool(SETTINGS.get(key)))
            c.toggled.connect(lambda on, k=key: self.demo.set_setting(k, on))
            v.addWidget(c)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        lay.addWidget(scroll)
        return w
