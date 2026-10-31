"""
The stickman himself: a full-screen, click-through, transparent overlay with a
physics body, a procedural rig, particles and a brain (see behavior.py).
Because the overlay covers the whole screen he can run, jump, flip, perch on
your windows and throw effects anywhere. Your clicks pass straight through.
"""
import math
import random
import time
from collections import deque

from PyQt6.QtCore import Qt, QRect, QRectF, QPointF, QTimer
from PyQt6.QtGui import (QPainter, QPen, QColor, QFont, QFontMetrics,
                         QGuiApplication, QCursor, QPolygonF)
from PyQt6.QtWidgets import QWidget

from rig import Rig, SCALE, HEAD_R, draw_figure
from poses import POSES
from behavior import Behavior
from settings import SETTINGS, STYLE
from gifs import GifLayer, FX
from platforms import (WindowPlatforms, WindowWatcher, mouse_down, foreground_rect, IS_WIN,
                       set_input_transparent, is_input_transparent)
from drag import Dragger
from perf import FrameGovernor, PerfMeter, SPIKES
from sound import SoundEngine
from speech import Speaker

GRAV = 2400.0
AIR_OK = {"smash", "tinker", "thinking", "wave", "dangle"}   # poses that may play mid-air


def approach(v, target, step):
    return min(target, v + step) if v < target else max(target, v - step)


class Body:
    def __init__(self):
        self.x = self.y = self.vx = self.vy = 0.0
        self.facing = -1
        self.on_ground = False
        self.support = None          # [platform_id, last_x1]
        self.physics = True
        self.desired_vx = 0.0


class Mascot(QWidget):
    def __init__(self):
        super().__init__()
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.drag_ok = IS_WIN              # dragging needs the Windows click-through switch (platforms.py)
        self._hwnd, self._cap, self._near_t = None, None, -9.0
        self.dragging, self.drag_swing = False, 0.0
        if not self.drag_ok:               # elsewhere: plain click-through, no dragging
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        if not self.drag_ok:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setCursor(Qt.CursorShape.OpenHandCursor)      # (only ever visible while he can be grabbed)

        screen = QGuiApplication.primaryScreen()
        geo, avail = screen.geometry(), screen.availableGeometry()
        self.origin = (geo.x(), geo.y())
        self.W, self.H = geo.width(), geo.height()
        self.setGeometry(geo.x(), geo.y(), self.W, self.H - 1)   # -1: stay out of "fullscreen" mode
        self.floor_y = avail.bottom() + 1 - geo.y()
        self.home_x = avail.right() - 140 - geo.x()

        self.body_color = QColor(STYLE["body"])
        self.outline_color = QColor(STYLE["outline"])
        self.gifs = GifLayer()
        self.sfx = SoundEngine()
        self.sfx.attach(self)
        self.speaker = Speaker()
        self.speaker.ensure_started()   # warm SAPI on a worker thread, before the first spoken line
        self.opacity, self.body_scale = 1.0, 1.0        # for vanish / giant / tiny
        self._say_queue = deque()
        self._last_ambient_speech = float("-inf")  # avoid constant unsolicited chatter
        self.aim_point = None            # make him aim at something other than the cursor
        self.tempo = 1.0                 # per-song dance speed
        self._pending = None

        self.rig = Rig()
        self.body = Body()
        self.body.x, self.body.y = self.home_x, self.floor_y
        self.body.on_ground, self.body.support = True, ["floor", 0.0]

        self.t, self.dt = 0.0, 1 / 60
        self.phase, self.speed = 0.0, 0.0
        self.rot, self.squash, self.land_t = 0.0, 0.0, 0.0
        self.action_pose, self.pose_t = None, 0.0
        self.aim_s = self.aim_h = (50.0, 0.0)
        self.skel = self.rig.skeleton(self.body.x, self.body.y, self.body.facing)
        self.ghosts = deque(maxlen=5)
        self.particles = []
        self._dust_t = self._sweat_t = 0.0
        self.routine = None
        self._bubble = None
        self._bubble_voiced = False
        self._emote = None
        self._last_rect = QRect()

        # inputs (swappable for tests)
        self.cursor_provider = lambda: (QCursor.pos().x() - self.origin[0],
                                        QCursor.pos().y() - self.origin[1])
        self.mouse_provider = mouse_down
        self.window_provider = WindowPlatforms(screen.devicePixelRatio(), self.origin,
                                               max_y=self.floor_y - 60).get
        self.foreground_provider = lambda: foreground_rect(screen.devicePixelRatio(), self.origin)
        self.cursor = self.cursor_provider()
        self.cursor_vel, self.cursor_speed = (0.0, 0.0), 0.0
        self._mouse_was = False
        self.platforms = [("floor", 0, self.W, self.floor_y)]
        self._plat_t = 0.0
        self.dragger = Dragger()
        # window scanning runs on its own thread: doing it inside the frame caused periodic stutter
        self.window_watcher = WindowWatcher(lambda: self.window_provider(), 0.5)
        self.window_watcher.start()
        self.governor, self.meter = FrameGovernor(), PerfMeter()
        self._parts, self._paint_ms = {}, 0.0

        self.behavior = Behavior(self)

        from PyQt6.QtCore import QTimer, QElapsedTimer
        self.clock = QElapsedTimer()
        self.clock.start()
        self._last_clock = 0.0
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)   # default coarse timers tick at ~15.6 ms steps on Windows
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(self.governor.interval)

    # ============================================================ public API
    def say(self, text, seconds=3.0, queue=False, voice="auto"):
        """Speech bubble (and out loud if text-to-speech is on). queue=True waits its turn instead of replacing
        the current bubble. voice: 'auto' = speak unless you're watching a video, 'force' = always, None = silent."""
        if voice != "force" and (int(SETTINGS.get("chat_level", 1)) <= 0 or not SETTINGS.get("chatty", True)):
            return                                      # Quiet / bubbles off: explicit requests still speak
        if voice == "auto":
            # Autonomous comments need breathing room. Manual demo lines use voice="force".
            level = max(0, min(3, int(SETTINGS.get("chat_level", 1))))
            min_gap = (float("inf"), 35.0, 20.0, 12.0)[level]
            if time.monotonic() - self._last_ambient_speech < min_gap:
                return
            self._last_ambient_speech = time.monotonic()
        if queue and self._bubble and self.t < self._bubble[1]:
            if len(self._say_queue) < 3:
                self._say_queue.append((text, seconds, voice))
            return
        seconds = max(seconds, min(9.0, len(text) / 11.0))      # long lines stay up long enough to read
        font = QFont("Segoe UI", 10)
        flags = int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter)
        r = QFontMetrics(font).boundingRect(0, 0, 200, 200, flags, text)
        self._bubble = (text, self.t + seconds, r.width() + 24, min(r.height() + 16, 130))
        self._bubble_voiced = bool(voice and SETTINGS.get("speak", True))
        # Schedule drawing immediately, rather than waiting for the next animation tick.
        bubble_rect = self._bubble_rect()
        if bubble_rect:
            self.update(bubble_rect.toAlignedRect().adjusted(-8, -8, 8, 18))
        self.sfx.play("pop", 0.45, 0.3)
        self._voice(text, voice)

    def _voice(self, text, voice):
        if voice and SETTINGS.get("speak", True) and (voice == "force" or self.behavior.mode != "watch"):
            self.speaker.say(text, interrupt=(voice == "force"))

    def _pump_say(self):
        """Keep a spoken line visible until the voice finishes, then advance the queue."""
        if self._bubble and self._bubble_voiced and self.speaker.busy:
            text, deadline, width, height = self._bubble
            if deadline < self.t + 0.4:
                self._bubble = (text, self.t + 0.4, width, height)
        if self._say_queue and (not self._bubble or self.t >= self._bubble[1]):
            text, seconds, voice = self._say_queue.popleft()
            self.say(text, seconds, voice=voice)

    def talking(self):
        return bool(self.speaker.speaking or (self._bubble and self.t < self._bubble[1]))

    def speaker_busy(self):
        return bool(self.speaker.busy)

    def emote(self, text, seconds=1.0):
        self._emote = (text, self.t, self.t + seconds)
        if "!" in text:
            self.sfx.play("alert", 0.9, 0.4)
        elif "?" in text:
            self.sfx.play("question", 0.7, 0.4)

    def set_pose(self, name):
        self.action_pose, self.pose_t = name, 0.0

    def clear_pose(self):
        self.action_pose = None

    animation = set_pose            # compatibility with the old API

    def run_routine(self, gen):
        """Take manual control (kinematic) for a scripted task, then drop him back to physics."""
        self.stop_routine()
        self.behavior.cancel()
        self.routine = gen
        self.body.physics = False
        self.body.vx = self.body.vy = self.body.desired_vx = 0.0

    def request_routine(self, gen):
        """Safe to call from inside a behaviour: starts the routine on the next frame."""
        self._pending = gen

    def fx(self, name, at="head", offset=(0, 0), loops=1, duration=None, follow=False):
        """Spawn a GIF effect. at = 'head' | 'feet' | 'body' | (x, y). False if the GIF is missing."""
        width, anchor = FX.get(name, (80, "center"))
        anchors = self._anchors()
        if isinstance(at, str):
            x, y = anchors[at]
            key = at if follow else None
        else:
            (x, y), key = at, None
        return self.gifs.spawn(name, x + offset[0], y + offset[1], width * SCALE, anchor,
                               loops, duration, key, offset)

    def _anchors(self):
        hx, hy = self.skel["head"]
        b = self.body
        return {"head": (hx, hy - HEAD_R * SCALE - 14 * SCALE),
                "feet": (b.x, b.y), "body": (b.x, b.y - 45 * SCALE)}

    def stop_routine(self):
        if self.routine:
            self.routine.close()
            self.routine = None
            self._end_routine()

    def _end_routine(self):
        b = self.body
        b.physics, b.on_ground, b.support = True, False, None
        self.rot = 0.0
        self.aim_point = None
        self.clear_pose()

    # --- geometry helpers used by behaviours
    def cursor_dist(self):
        return math.hypot(self.cursor[0] - self.body.x,
                          self.cursor[1] - (self.body.y - 45 * SCALE))

    def face_cursor(self):
        self.body.facing = 1 if self.cursor[0] >= self.body.x else -1

    def find_platform(self, pid):
        for p in self.platforms:
            if p[0] == pid:
                return p
        return None

    def support_range(self):
        s = self.body.support
        p = self.find_platform(s[0]) if s else None
        return (p[1], p[2]) if p else (0, self.W)

    # --- effects
    def puff(self, x, y, n=4):
        for _ in range(n):
            self.particles.append(dict(kind="dust", x=x + random.uniform(-10, 10), y=y - 2,
                                       vx=random.uniform(-70, 70), vy=-random.uniform(15, 70),
                                       life=random.uniform(0.35, 0.6), max=0.6,
                                       size=random.uniform(5, 9)))

    def burst(self, x, y):
        self.particles.append(dict(kind="burst", x=x, y=y, vx=0, vy=0, life=0.28, max=0.28, size=0))

    # --- building blocks for scripts: use with `yield from`
    def wait(self, seconds):
        t = 0.0
        while t < seconds:
            t += self.dt
            yield

    def walk_to(self, x, speed=140, timeout=None):
        b = self.body
        timeout = timeout or (abs(x - b.x) / max(speed, 1) * 2 + 1.5)
        t = 0.0
        while abs(b.x - x) > 4 and t < timeout:
            b.facing = 1 if x > b.x else -1
            b.desired_vx = b.facing * speed
            t += self.dt
            yield
        b.desired_vx = 0.0

    def jump(self, vx, vy, flip=0, air_time=None):
        """Launch and wait for the landing. flip=+1 front flip, -1 back flip."""
        b = self.body
        b.vx, b.vy, b.on_ground, b.support, b.desired_vx = vx, vy, False, None, 0.0
        if abs(vx) > 5:
            b.facing = 1 if vx > 0 else -1
        self.puff(b.x, b.y, 4)
        T = air_time or max(0.3, 2 * abs(vy) / GRAV)
        t = 0.0
        while True:
            t += self.dt
            if flip:
                self.rot = flip * 2 * math.pi * min(1.0, t / (T * 0.9))
            yield
            if b.on_ground or t > 4:
                break
        self.rot = 0.0

    def hop_to(self, x, y, flip=0, margin=70):
        """Ballistic jump that lands with the feet at (x, y)."""
        b = self.body
        vy = -math.sqrt(2 * GRAV * max(max(0, b.y - y) + margin, 60))
        T = (-vy + math.sqrt(max(vy * vy + 2 * GRAV * (y - b.y), 0))) / GRAV
        yield from self.jump((x - b.x) / T, vy, flip, air_time=T)

    def arc_to(self, x, y, duration=0.55, height=90):
        """Scripted leap (no physics) - used by routines to reach any point on screen."""
        b = self.body
        sx, sy = b.x, b.y
        if abs(x - sx) > 4:
            b.facing = 1 if x > sx else -1
        self.set_pose("jump")
        t = 0.0
        while t < duration:
            t += self.dt
            k = min(1.0, t / duration)
            b.x = sx + (x - sx) * k
            b.y = sy + (y - sy) * k - 4 * height * k * (1 - k)
            yield
        self.squash = 0.3
        self.puff(b.x, b.y, 4)
        self.set_pose("land")
        yield from self.wait(0.15)
        self.clear_pose()

    def strike(self, kind="punch", on_hit=None):
        """Wind up, hit toward the cursor (or aim_point), recover."""
        self.set_pose(kind)
        self.sfx.play("whoosh", 0.8, 0.15)
        yield from self.wait(0.16 if kind == "punch" else 0.2)
        self.impact(kind)
        if on_hit:
            on_hit()
        yield from self.wait(0.22)
        self.set_pose("stance")

    def impact(self, kind):
        sk = self.skel
        hx, hy = sk["arm_b"][2] if kind == "punch" else sk["leg_b"][2]
        self.sfx.play("punch" if kind == "punch" else "kick", 1.0, 0.1)
        if not self.fx("impact", at=(hx, hy)):
            self.burst(hx, hy)
        if SETTINGS["shove_cursor"]:
            cx, cy = self.cursor
            dx, dy = cx - hx, cy - hy
            d = math.hypot(dx, dy)
            if d < 90:
                n = d or 1.0
                QCursor.setPos(int(cx + dx / n * 28 + self.origin[0]),
                               int(cy + dy / n * 28 + self.origin[1]))

    def impact_at(self, x, y):
        self.sfx.play("explosion", 1.0, 0.5)
        if not self.fx("explosion", at=(x, y)):
            self.burst(x, y)

    # ============================================================ engine
    def _on_timer(self):
        t0 = time.perf_counter()
        now = self.clock.elapsed() / 1000.0
        gap = (now - self._last_clock) * 1000
        dt = min(0.05, now - self._last_clock)
        self._last_clock = now
        self.step(dt)
        SPIKES.frame(gap, self.governor.interval, self._parts, self._paint_ms, now)
        if SETTINGS.get("perf_log"):
            line = self.meter.add((time.perf_counter() - t0) * 1000, now)
            if line:
                print(line)

    def step(self, dt):
        self.dt = dt
        self.t += dt
        self.pose_t += dt
        if self._pending:
            gen, self._pending = self._pending, None
            self.run_routine(gen)
        self._pump_say()
        pc = time.perf_counter
        t0 = pc()
        self._read_inputs(dt)
        t1 = pc()
        if self.dragging:
            self._drag_step(dt)
        elif self.routine:
            try:
                next(self.routine)
            except StopIteration:
                self.routine = None
                self._end_routine()
            except Exception:                             # a buggy routine must never take the whole app down
                import traceback
                traceback.print_exc()
                self.routine = None
                self._end_routine()
        else:
            self.behavior.update(dt)
        t2 = pc()
        self._physics(dt)
        self._animate(dt)
        t3 = pc()
        self.sfx.update(self)
        t4 = pc()
        self._tune_framerate()
        self._request_repaint()
        t5 = pc()
        self._parts = {"inputs": (t1 - t0) * 1000, "logic": (t2 - t1) * 1000, "physics+anim": (t3 - t2) * 1000,
                       "sfx": (t4 - t3) * 1000, "frame-end": (t5 - t4) * 1000}

    def _read_inputs(self, dt):
        cx, cy = self.cursor_provider()
        px, py = self.cursor
        k = 1 - math.exp(-10 * dt)
        vx = (cx - px) / max(dt, 1e-3)
        vy = (cy - py) / max(dt, 1e-3)
        self.cursor_vel = (self.cursor_vel[0] + (vx - self.cursor_vel[0]) * k,
                           self.cursor_vel[1] + (vy - self.cursor_vel[1]) * k)
        self.cursor_speed = math.hypot(*self.cursor_vel)
        self.cursor = (cx, cy)
        down = self.mouse_provider()
        self._update_drag(down, cx, cy)
        if down and not self._mouse_was and not self.dragging:
            self.behavior.on_click()
        self._mouse_was = down
        self._plat_t -= dt
        if self._plat_t <= 0:
            self._plat_t = 0.2                  # cheap: just picks up the list the watcher thread made
            self.platforms = [("floor", 0, self.W, self.floor_y)] + list(self.window_watcher.latest)

    # ============================================================ dragging
    def showEvent(self, event):
        super().showEvent(event)
        if IS_WIN and self._hwnd is None and self.drag_ok:
            self._hwnd = int(self.winId())
            self._set_capture(False)                              # start fully click-through
            if not is_input_transparent(self._hwnd):              # couldn't: NEVER risk blocking the screen
                self.drag_ok = False
                QTimer.singleShot(0, self._fallback_click_through)

    def _fallback_click_through(self):
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
        self.show()

    def _set_capture(self, on):
        """on=True: clicks on his drawn pixels land on HIM. Off: clicks pass through to your apps."""
        if not (self.drag_ok and self._hwnd) or on == self._cap:
            return
        if set_input_transparent(self._hwnd, not on):
            self._cap = on
            self.setCursor(Qt.CursorShape.ClosedHandCursor if self.dragging else Qt.CursorShape.OpenHandCursor)
            self.update(self._last_rect)                          # show/hide the faint grab area

    def _update_drag(self, down, cx, cy):
        if not (self.drag_ok and SETTINGS.get("draggable", True)):
            if self.dragging:
                self._end_drag()
            return
        if self.dragging:
            if not down:
                self._end_drag()
            return
        near = self.dragger.near(self.skel, cx, cy)
        if near:
            self._near_t = self.t
        self._set_capture(self.t - self._near_t < 0.3)            # small hysteresis: no flicker at the edge
        if near and down and not self._mouse_was:                 # a fresh press ON him
            self._start_drag(cx, cy)

    def _start_drag(self, cx, cy):
        self.stop_routine()
        self.behavior.cancel()
        b = self.body
        b.physics, b.on_ground, b.support = True, False, None
        b.vx = b.vy = b.desired_vx = 0.0
        self.rot, self.aim_point, self.dragging = 0.0, None, True
        self.dragger.start(self.t, (cx, cy), (b.x, b.y))
        self.set_pose("dangle")
        self._set_capture(True)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.behavior.on_grabbed()

    def _drag_step(self, dt):
        self.drag_swing = self.dragger.follow(self.t, dt, self.cursor, self.body,
                                              (24, self.W - 24, 170, self.floor_y))
        if self.action_pose != "dangle":
            self.set_pose("dangle")

    def _end_drag(self):
        vx, vy = self.dragger.release(self.t)
        b = self.body
        b.vx, b.vy, b.on_ground, b.support, b.physics = vx, vy, False, None, True
        self.dragging, self.drag_swing = False, 0.0
        self.clear_pose()
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.behavior.on_dropped(math.hypot(vx, vy))

    def _tune_framerate(self):
        """30 fps while he's just standing around, 60 fps the moment anything moves."""
        b = self.body
        busy = (self.dragging or not b.on_ground or self.speed >= 8 or self.particles or self.gifs.items
                or self.ghosts or self.rot != 0.0 or self.cursor_speed > 60 or self.opacity < 1.0
                or self.body_scale != 1.0 or self.talking()
                or (self._emote and self.t < self._emote[2]) or (self._bubble and self.t < self._bubble[1]))
        if SETTINGS.get("recording_mode"):
            # Match 30-fps OBS recording. Do not reconfigure the Qt timer every frame.
            self.governor.interval = 33
            self.governor._calm_since = None
            if self.timer.interval() != 33:
                self.timer.setInterval(33)
            return
        ms = self.governor.update(not busy, self.t)
        if ms:
            self.timer.setInterval(ms)

    def _physics(self, dt):
        b = self.body
        if not b.physics or self.dragging:
            return
        if b.on_ground:                     # ride the platform (windows can move!)
            p = self.find_platform(b.support[0]) if b.support else None
            if p is None or b.x < p[1] - 8 or b.x > p[2] + 8:
                b.on_ground, b.support = False, None
            else:
                b.x += p[1] - b.support[1]
                b.support[1], b.y = p[1], p[3]
        if b.on_ground:
            b.vx = approach(b.vx, b.desired_vx, 3200 * dt)
            b.x += b.vx * dt
        else:
            prev = b.y
            b.vy += GRAV * dt
            b.x += b.vx * dt
            b.y += b.vy * dt
            if b.vy > 0:
                best = None
                for p in self.platforms:
                    if p[1] <= b.x <= p[2] and prev <= p[3] + 1 and b.y >= p[3]:
                        if best is None or p[3] < best[3]:
                            best = p
                if best:
                    impact = b.vy
                    b.y, b.vy, b.on_ground = best[3], 0.0, True
                    b.support = [best[0], best[1]]
                    if impact > 1300:
                        self.fx("dizzy", at="head", loops=0, duration=1.3, follow=True)
                        self.behavior.on_hard_landing()
                    if impact > 450:
                        self.squash = min(0.35, impact / 3200)
                        self.land_t = 0.1
                        if not (impact > 750 and self.fx("poof", at="feet")):
                            self.puff(b.x, b.y, 5)
        if b.x < 24:
            b.x, b.vx = 24, max(0.0, b.vx)
        elif b.x > self.W - 24:
            b.x, b.vx = self.W - 24, min(0.0, b.vx)

    def _pose_name(self):
        b = self.body
        if self.action_pose and (not b.physics or b.on_ground or self.action_pose in AIR_OK):
            return self.action_pose
        if not b.physics:
            return "idle"
        if not b.on_ground:
            return "jump" if b.vy < 0 else "fall"
        if self.land_t > 0:
            return "land"
        return "walk" if abs(b.vx) > 8 else "idle"

    def _animate(self, dt):
        b = self.body
        self.speed = abs(b.vx)
        if b.on_ground:
            self.phase += self.speed * dt / (22 + 10 * min(1.0, self.speed / 450))
        self.land_t = max(0.0, self.land_t - dt)

        sh, hip, f = self.skel["sh"], self.skel["hip"], b.facing
        cx, cy = self.aim_point or self.cursor
        self.aim_s = ((cx - sh[0]) * f / SCALE, (cy - sh[1]) / SCALE)
        self.aim_h = ((cx - hip[0]) * f / SCALE, (cy - hip[1]) / SCALE)

        pn = self._pose_name()
        if pn == "idle" and self.talking():
            pn = "talk"                                    # he gestures while he speaks
        target, speed = POSES[pn](self, self.t, self.pose_t)
        self.rig.blend(target, speed, dt)

        self.squash *= math.exp(-10 * dt)
        if not b.on_ground and b.physics:
            s = min(0.22, abs(b.vy) / 5000)
            sx, sy = 1 - s * 0.6, 1 + s
        else:
            sx, sy = 1 + self.squash * 0.8, 1 - self.squash
        self.skel = self.rig.skeleton(b.x, b.y, b.facing, self.rot, sx * self.body_scale, sy * self.body_scale)

        smear = (self.speed > 380 or abs(b.vy) > 900 or self.rot != 0
                 or self.action_pose in ("punch", "kick"))
        if SETTINGS.get("recording_mode"):
            # Motion ghosts are artistic effects, not cached frames. Disable for clean videos.
            self.ghosts.clear()
        elif smear:
            self.ghosts.append(self.skel)
        elif self.ghosts:
            self.ghosts.popleft()

        if b.on_ground and self.speed > 260:
            self._dust_t -= dt
            if self._dust_t <= 0:
                self._dust_t = 0.07
                self.puff(b.x - b.facing * 12, b.y, 1)
        if self.behavior.fear > 0.6:
            self._sweat_t -= dt
            if self._sweat_t <= 0 and self.gifs.has("sweat"):
                self._sweat_t = 1.3
                self.fx("sweat", at="head", offset=(-b.facing * 14 * SCALE, 10 * SCALE), follow=True)
            elif self._sweat_t <= 0:
                self._sweat_t = 0.22
                hx, hy = self.skel["head"]
                self.particles.append(dict(kind="sweat", x=hx - b.facing * 10, y=hy - 6,
                                           vx=-b.facing * random.uniform(30, 80), vy=-random.uniform(60, 130),
                                           life=0.5, max=0.5, size=3))
        for q in self.particles:
            q["life"] -= dt
            q["x"] += q["vx"] * dt
            q["y"] += q["vy"] * dt
            if q["kind"] == "sweat":
                q["vy"] += 700 * dt
        self.particles = [q for q in self.particles if q["life"] > 0]
        self.gifs.update(dt, self._anchors())

    # ============================================================ drawing
    def _bubble_rect(self):
        if not self._bubble or self.t >= self._bubble[1]:
            return None
        _, _, bw, bh = self._bubble
        hx, hy = self.skel["head"]
        cx = min(max(hx, bw / 2 + 8), self.W - bw / 2 - 8)
        bottom = hy - HEAD_R * SCALE - 26
        top = max(4.0, bottom - bh)
        return QRectF(cx - bw / 2, top, bw, bh)

    def _request_repaint(self):
        sk = self.skel
        pts = [sk["hip"], sk["neck"], sk["head"]] + sk["arm_a"] + sk["arm_b"] + sk["leg_a"] + sk["leg_b"]
        xs = [p[0] for p in pts] + [q["x"] for q in self.particles]
        ys = [p[1] for p in pts] + [q["y"] for q in self.particles]
        m = int(70 * SCALE)
        # Old ghost poses also need repainting, or their pixels can remain on the desktop.
        for ghost in self.ghosts:
            for key in ("hip", "neck", "head", "arm_a", "arm_b", "leg_a", "leg_b"):
                point_or_points = ghost[key]
                entries = point_or_points if key in ("arm_a", "arm_b", "leg_a", "leg_b") else [point_or_points]
                xs.extend(point[0] for point in entries)
                ys.extend(point[1] for point in entries)
        r = QRect(int(min(xs)) - m, int(min(ys)) - m,
                  int(max(xs) - min(xs)) + 2 * m, int(max(ys) - min(ys)) + 2 * m)
        for gr in self.gifs.rects():
            r = r.united(gr.toAlignedRect().adjusted(-4, -4, 4, 4))
        br = self._bubble_rect()
        if br:
            r = r.united(br.toAlignedRect().adjusted(-6, -6, 6, 30))
        if self._emote and self.t < self._emote[2]:
            hx, hy = sk["head"]
            r = r.united(QRect(int(hx) - 50, int(hy) - 130, 100, 110))
        if SETTINGS.get("clean_repaint"):
            # Last resort for some Windows/driver transparent-overlay ghosting bugs.
            self.update()
        else:
            self.update(r.united(self._last_rect))
        self._last_rect = r

    def paintEvent(self, event):
        t0 = time.perf_counter()
        self._paint(event)
        self._paint_ms = (time.perf_counter() - t0) * 1000

    def _paint(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(event.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        if self._cap:        # near-invisible (alpha 3) so a click just beside a thin limb still lands on him
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 3))
            hx, hy = self.skel["hip"]
            p.drawEllipse(QPointF(hx, hy - 18 * SCALE), 72 * SCALE, 81 * SCALE)

        n = len(self.ghosts)
        for i, g in enumerate(self.ghosts):          # motion smear
            if i < n - 1:
                draw_figure(p, g, self.body_color, self.outline_color, 0.07 + 0.06 * i)
        draw_figure(p, self.skel, self.body_color, self.outline_color, self.opacity, self.body_scale)

        for q in self.particles:
            lf = q["life"] / q["max"]
            if q["kind"] == "dust":
                c = QColor(225, 225, 225, int(150 * lf))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c)
                p.drawEllipse(QPointF(q["x"], q["y"]), q["size"] * (2 - lf), q["size"] * (2 - lf))
            elif q["kind"] == "burst":
                r0 = 8 + (1 - lf) * 40
                p.setPen(QPen(QColor(255, 255, 255, int(255 * lf)), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                for pass_pen in (QPen(QColor(255, 255, 255, int(255 * lf)), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap),
                                 QPen(self.outline_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)):
                    p.setPen(pass_pen)
                    for i in range(8):
                        a = i * math.pi / 4
                        p.drawLine(QPointF(q["x"] + math.cos(a) * r0, q["y"] + math.sin(a) * r0),
                                   QPointF(q["x"] + math.cos(a) * (r0 + 11), q["y"] + math.sin(a) * (r0 + 11)))
            else:   # sweat
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(110, 198, 255, int(255 * lf)))
                p.drawEllipse(QPointF(q["x"], q["y"]), 2.5, 4)

        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.gifs.paint(p)

        if self._emote and self.t < self._emote[2]:
            text, t0, _ = self._emote
            age = self.t - t0
            pop = 0.6 + 0.4 * min(1.0, age / 0.12)
            font = QFont("Segoe UI", int(20 * pop), QFont.Weight.Black)
            p.setFont(font)
            hx, hy = self.skel["head"]
            y = hy - 38 * SCALE - age * 14
            rect = QRectF(hx - 60, y - 30, 120, 40)
            p.setPen(self.outline_color)
            p.drawText(rect.translated(1.5, 1.5), int(Qt.AlignmentFlag.AlignCenter), text)
            p.setPen(QColor("#ff3b30") if "!" in text else QColor("#ffffff"))
            p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)

        br = self._bubble_rect()
        if br:
            text = self._bubble[0]
            font = QFont("Segoe UI", 10)
            p.setFont(font)
            p.setPen(QPen(self.outline_color, 2))
            p.setBrush(QColor("white"))
            p.drawRoundedRect(br, 10, 10)
            hx = min(max(self.skel["head"][0], br.left() + 14), br.right() - 14)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(QPolygonF([QPointF(hx - 7, br.bottom() - 1), QPointF(hx + 7, br.bottom() - 1),
                                     QPointF(hx, br.bottom() + 10)]))
            p.setPen(self.outline_color)
            flags = int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter)
            p.drawText(br.adjusted(8, 4, -8, -4), flags, text)
        p.end()
