"""Read the title of the currently active Windows window."""

import win32gui


class ScreenMonitor:
    def get_active_window_title(self):
        """Return the foreground window's title, or an empty string."""
        window_handle = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(window_handle)
