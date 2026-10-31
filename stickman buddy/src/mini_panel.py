"""Small on-screen demo remote: optional alternative to the large control panel."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class MiniDemoBar(QWidget):
    def __init__(self, demo):
        super().__init__()
        self.demo = demo
        self.setWindowTitle("Stickman demo remote")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setStyleSheet("""
            QWidget { background: #20212a; }
            QPushButton { background: #35374b; color: white; border-radius: 5px;
                          padding: 5px 8px; font-size: 11px; }
            QPushButton:hover { background: #535879; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        for label, action in (
            ("Hi Judges", lambda: demo.run_scene("Hi Judges")),
            ("Dance", lambda: demo.run_move("dance")),
            ("Code", lambda: demo.run_scene("Coding moment")),
            ("Joke", lambda: demo.run_move("joke")),
            ("Bye Judges", lambda: demo.run_scene("Goodbye Judges")),
            ("Stop", demo.stop),
            ("Hide", self.hide),
        ):
            button = QPushButton(label)
            button.clicked.connect(action)
            layout.addWidget(button)
        self.adjustSize()

    def show_near_corner(self):
        """Park at the top-right edge to avoid covering the demo character."""
        screen = self.screen().availableGeometry()
        self.move(screen.right() - self.width() - 18, screen.top() + 18)
        self.show()
        self.raise_()
