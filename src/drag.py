"""Pick him up, carry him, throw him. Pure maths (no Qt) so it's easy to test."""
import math
from collections import deque


def seg_dist(p, a, b):
    """Distance from point p to the segment a-b."""
    ax, ay, bx, by, px, py = a[0], a[1], b[0], b[1], p[0], p[1]
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class Dragger:
    LIMB_PAD = 22          # px: how close to a limb still counts as "on him"
    HEAD_PAD = 30          # px: around the head's centre
    HANG = 125             # px: where his FEET hang below the cursor while he's carried (by his hands)
    EASE = 0.18            # s: how long he takes to swing from where you grabbed to hanging

    def __init__(self):
        self.active = False
        self.hist = deque(maxlen=10)
        self.grab_t, self.off = 0.0, (0.0, 0.0)

    def near(self, skel, x, y, pad=None):
        pad = self.LIMB_PAD if pad is None else pad
        p = (x, y)
        if math.hypot(x - skel["head"][0], y - skel["head"][1]) < self.HEAD_PAD:
            return True
        chains = [[skel["hip"], skel["neck"], skel["head"]], skel["arm_a"], skel["arm_b"], skel["leg_a"], skel["leg_b"]]
        return any(seg_dist(p, c[i], c[i + 1]) < pad for c in chains for i in range(len(c) - 1))

    def start(self, now, cursor, body_xy):
        self.active, self.grab_t = True, now
        self.off = (body_xy[0] - cursor[0], body_xy[1] - cursor[1])
        self.hist.clear()
        self.hist.append((now, cursor[0], cursor[1]))

    def follow(self, now, dt, cursor, body, bounds):
        """Moves `body` toward the carry position. bounds = (xmin, xmax, ymin, ymax) for his FEET.
        Returns the cursor's sideways speed (px/s) so the pose can make him swing."""
        k = min(1.0, (now - self.grab_t) / self.EASE)
        tx = cursor[0] + self.off[0] * (1 - k)
        ty = cursor[1] + self.off[1] * (1 - k) + self.HANG * k
        a = 1 - math.exp(-28 * dt)
        body.x += (tx - body.x) * a
        body.y += (ty - body.y) * a
        body.x = max(bounds[0], min(bounds[1], body.x))
        body.y = max(bounds[2], min(bounds[3], body.y))
        self.hist.append((now, cursor[0], cursor[1]))
        old = next((h for h in self.hist if now - h[0] <= 0.15), self.hist[0])
        span = now - old[0]
        return (cursor[0] - old[1]) / span if span > 1e-3 else 0.0

    def release(self, now, max_speed=1600.0, gain=0.75):
        """Throw velocity (vx, vy) from the last ~0.12 s of cursor movement."""
        self.active = False
        if len(self.hist) < 2:
            return 0.0, 0.0
        last = self.hist[-1]
        old = next((h for h in self.hist if last[0] - h[0] <= 0.12), self.hist[0])
        span = last[0] - old[0]
        if span < 1e-3:
            return 0.0, 0.0
        vx, vy = (last[1] - old[1]) / span, (last[2] - old[2]) / span
        sp = math.hypot(vx, vy)
        if sp > max_speed:
            vx, vy = vx * max_speed / sp, vy * max_speed / sp
        return vx * gain, vy * gain
