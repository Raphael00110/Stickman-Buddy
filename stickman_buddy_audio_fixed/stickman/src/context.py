"""Turns a raw window title into a simple category the companion can react to."""

VIDEO_SITES = ("youtube", "netflix", "prime video", "twitch", "disney+", "crunchyroll")


CODE_APPS = ("visual studio", "vs code", "pycharm", "intellij", "sublime text", "jupyter",
             "android studio", "windows terminal", "powershell", "command prompt")
CHAT_APPS = ("discord", "whatsapp", "telegram", "slack", "microsoft teams", "messenger", "signal")
GAME_APPS = ("steam", "epic games", "roblox", "minecraft", "valorant", "fortnite", "genshin",
             "league of legends")
DOC_APPS = (" - word", " - excel", " - powerpoint", "notepad", "onenote", "libreoffice")


# Short-form feeds. TikTok / Instagram / Reels announce themselves in the window title; YouTube Shorts
# usually does NOT, so for those turn on "Shorts mode" in the tray menu (or type "shorts on").
SHORTS_HINTS = ("tiktok", "instagram", "reels", "shorts")
BROWSER_NAMES = ("chrome", "msedge", "edge", "firefox", "brave", "opera", "vivaldi", "zen")


def is_short_form(title: str) -> bool:
    t = title.lower()
    return any(h in t for h in SHORTS_HINTS)


def shorts_capable(title: str) -> bool:
    """Is the window in front something that scrolls with Up/Down (a browser or the TikTok/Instagram app)?
    This is the safety check before he ever presses a key."""
    t = title.lower()
    return any(b in t for b in BROWSER_NAMES) or is_short_form(t)


def classify(title: str) -> str:
    t = title.lower()
    if "wi-fi" in t or "network" in t:
        return "network"
    if is_short_form(t):
        return "shorts"
    if any(site in t for site in VIDEO_SITES):
        return "video"
    if any(a in t for a in CODE_APPS):
        return "code"
    if any(a in t for a in CHAT_APPS):
        return "chat"
    if any(a in t for a in GAME_APPS):
        return "game"
    if any(a in t for a in DOC_APPS):
        return "docs"
    return "other"
