
"""
Talks to the OS: window rectangles (so he can stand on your windows), mouse
button state (so he flinches when you click) and the panic hotkey.
Everything here is Windows-only and fails soft: on other systems he just walks
along the bottom of the screen.
"""
import sys
import threading

IS_WIN = sys.platform == "win32"

if IS_WIN:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    dwm = ctypes.windll.dwmapi
    ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def mouse_down():
    return IS_WIN and bool(user32.GetAsyncKeyState(0x01) & 0x8000)


def boost_priority():
    """Run at 'above normal' priority: the animation then wins the CPU while the local AI model is busy."""
    if not IS_WIN:
        return False
    try:
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x00008000))     # ABOVE_NORMAL_PRIORITY_CLASS
    except Exception:
        return False


WS_EX_TRANSPARENT, WS_EX_LAYERED, WS_EX_NOACTIVATE, GWL_EXSTYLE = 0x20, 0x80000, 0x08000000, -20


def set_input_transparent(hwnd, transparent):
    """True  = clicks pass straight through the overlay (normal).
    False = the overlay catches clicks, but ONLY on pixels that are actually drawn (a layered window's
            fully transparent pixels still let clicks through). It never takes keyboard focus."""
    if not (IS_WIN and hwnd):
        return False
    try:
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new = ex | WS_EX_LAYERED | WS_EX_NOACTIVATE
        new = (new | WS_EX_TRANSPARENT) if transparent else (new & ~WS_EX_TRANSPARENT)
        if new != ex:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new)
        return True
    except Exception:
        return False


def is_input_transparent(hwnd):
    if not (IS_WIN and hwnd):
        return False
    try:
        return bool(user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TRANSPARENT)
    except Exception:
        return False


class WindowWatcher(threading.Thread):
    """Scans your windows on a background thread. EnumWindows makes hundreds of Python callbacks, and doing
    that inside the animation frame was a major source of stutter. The UI just reads `.latest`."""

    def __init__(self, provider, interval=0.5):
        super().__init__(daemon=True, name="windows")
        self.provider, self.interval, self.latest = provider, interval, []
        self._halt = threading.Event()

    def run(self):
        while not self._halt.is_set():
            try:
                self.latest = list(self.provider())
            except Exception:
                pass
            self._halt.wait(self.interval)

    def stop(self):
        self._halt.set()


def foreground_hwnd():
    """Handle of the window you're using right now (0 if unknown)."""
    if not IS_WIN:
        return 0
    try:
        return int(user32.GetForegroundWindow())
    except Exception:
        return 0


def restore_foreground(hwnd):
    """Give focus back to a window (used after the typing box closes, so keys land in the right place)."""
    if not (IS_WIN and hwnd):
        return False
    try:
        return bool(user32.SetForegroundWindow(hwnd))
    except Exception:
        return False


def mini_combo():
    """Ctrl+Alt+M shows/hides the tiny recording remote."""
    if not IS_WIN:
        return False
    return all(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x11, 0x12, 0x4D))


def voice_chat_combo():
    """Ctrl+Alt+V starts a one-shot spoken conversation."""
    if not IS_WIN:
        return False
    return all(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x11, 0x12, 0x56))


def panel_combo():
    """Ctrl + Alt + P held together = show/hide the control panel."""
    if not IS_WIN:
        return False
    return all(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x11, 0x12, 0x50))


def talk_combo():
    """Ctrl + Alt + T held together = open the 'talk to him' box."""
    if not IS_WIN:
        return False
    return all(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x11, 0x12, 0x54))


def idle_seconds():
    """Seconds since your last mouse/keyboard input. Only the TIME, never which keys."""
    if not IS_WIN:
        return 0.0
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
        li = LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(li)
        if not user32.GetLastInputInfo(ctypes.byref(li)):
            return 0.0
        now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        return max(0.0, ((now - li.dwTime) & 0xFFFFFFFF) / 1000.0)
    except Exception:
        return 0.0


def panic_combo():
    """Ctrl + Alt + Q held together = instantly quit the app."""
    if not IS_WIN:
        return False
    return all(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x11, 0x12, 0x51))


class WindowPlatforms:
    """Top edges of visible windows as (id, x1, x2, y) in overlay coordinates."""

    def __init__(self, dpr=1.0, origin=(0, 0), min_top=80, max_y=None):
        self.dpr, self.origin = dpr, origin
        self.min_top, self.max_y = min_top, max_y
        self.broken = False

    def get(self):
        if not IS_WIN or self.broken:
            return []
        try:
            return self._enum()
        except Exception:
            self.broken = True
            return []

    def _enum(self):
        out, dpr = [], self.dpr
        ox, oy = self.origin

        def cb(hwnd, _):
            try:
                if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                    return True
                if user32.GetWindowTextLengthW(hwnd) == 0:
                    return True
                if user32.GetWindowLongW(hwnd, -20) & 0x80:      # tool window
                    return True
                cloaked = wintypes.DWORD(0)
                dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)
                if cloaked.value:
                    return True
                r = wintypes.RECT()
                if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
                    user32.GetWindowRect(hwnd, ctypes.byref(r))
                x1, x2, y = r.left / dpr - ox, r.right / dpr - ox, r.top / dpr - oy
                if y < self.min_top or x2 - x1 < 160:
                    return True
                if self.max_y is not None and y > self.max_y:
                    return True
                out.append((int(hwnd), x1, x2, y))
            except Exception:
                pass
            return True

        user32.EnumWindows(ENUMPROC(cb), 0)
        return out


def foreground_rect(dpr=1.0, origin=(0, 0)):
    """Rect of the window you're using, as {'x1','x2','top'} in overlay coordinates (or None)."""
    if not IS_WIN:
        return None
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        r = wintypes.RECT()
        if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
            user32.GetWindowRect(hwnd, ctypes.byref(r))
        return dict(x1=r.left / dpr - origin[0], x2=r.right / dpr - origin[0],
                    top=r.top / dpr - origin[1])
    except Exception:
        return None
