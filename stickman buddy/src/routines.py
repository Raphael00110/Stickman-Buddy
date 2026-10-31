"""
Scripted tasks (take full control, ignore the cursor until they finish).
When a routine ends, physics resumes and he drops to whatever is below him,
which is why the tab prank ends with him tumbling back down.
"""
import time

from rig import SCALE


def greet(m, text="Hey! I'm here~"):
    m.set_pose("wave")
    m.say(text, 2.2)
    yield from m.wait(1.8)


def smash(m, target_x, target_y, on_hit=None, text=None):
    """Leap to the target, wind up, smash, then fall."""
    if text:
        m.say(text, 3)
    yield from m.arc_to(target_x - 36 * SCALE, target_y + 46 * SCALE)
    m.body.facing = 1
    m.set_pose("smash")
    yield from m.wait(0.45)
    if on_hit:
        on_hit()                       # the real click lands exactly on impact
    m.impact_at(target_x, target_y)
    yield from m.wait(0.7)


def smash_when_ready(m, box, target_x, target_y, on_hit=None, timeout=8):
    """Think while the AI is replying (box['text'] gets filled in), then smash."""
    m.set_pose("thinking")
    m.say("Ooh, what's this...?", timeout)
    t0 = time.monotonic()
    while "text" not in box and time.monotonic() - t0 < timeout:
        yield
    yield from smash(m, target_x, target_y, on_hit, box.get("text", "Nope. Smashing it."))


def tinker(m, target=None, on_done=None, text=None, duration=2.0):
    """Optionally leap to target (feet x, y), fiddle with something, run on_done mid-way."""
    if target:
        yield from m.arc_to(*target)
    if text:
        m.say(text, duration)
    m.set_pose("tinker")
    yield from m.wait(duration * 0.6)
    if on_done:
        on_done()
    yield from m.wait(duration * 0.4)
    yield from m.wait(0.1)


def pause_prank(m, actions):
    """Shh... pauses your song for a few seconds, then 'just kidding'."""
    m.fx("lightbulb", at="head", follow=True, duration=1.1, loops=0)
    m.say("Shhh... sneaky time", 2.5)
    m.set_pose("sneak")
    yield from m.wait(1.3)
    actions.pause()
    m.emote("...", 3.2)
    m.set_pose("look")
    yield from m.wait(3.2)
    actions.resume()
    m.say("Just kidding!", 2)
    m.fx("sparkle", at="head", follow=True, loops=2)
    m.set_pose("dance")
    yield from m.wait(2.0)


def skip_song(m, actions):
    """Judges your taste and kicks the song to the next one."""
    b = m.body
    m.say("Nah. NEXT!", 2)
    m.aim_point = (b.x + b.facing * 75 * SCALE, b.y - 35 * SCALE)
    yield from m.wait(0.5)
    yield from m.strike("kick", on_hit=actions.next)
    m.aim_point = None
    m.set_pose("victory")
    yield from m.wait(1.2)


def tab_peek(m, fg, actions):
    """Leaps up to your tab strip, smacks over to the next tab, peeks, and smacks back."""
    x = fg["x1"] + min(260.0, (fg["x2"] - fg["x1"]) * 0.3)
    top = fg["top"]
    m.fx("lightbulb", at="head", follow=True, duration=1.1, loops=0)
    m.say("Mind if I peek at your next tab?", 2.6)
    yield from m.wait(0.9)
    yield from m.arc_to(x - 18 * SCALE, top + 150, duration=0.7, height=150)
    m.body.facing = 1
    m.aim_point = (x + 12 * SCALE, top + 20)
    yield from m.strike("punch", on_hit=actions.tab_next)
    m.say("Ooh, what's over here?", 2.2)
    m.set_pose("look")
    yield from m.wait(2.4)
    m.set_pose("stance")
    yield from m.strike("punch", on_hit=actions.tab_prev)
    m.say("Okay okay, going back!", 1.6)
    yield from m.wait(1.0)
