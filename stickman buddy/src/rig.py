"""
The skeleton. A pose is 12 numbers; two-bone IK turns hand/foot targets into
elbows and knees. The rig is drawn Animator-vs-Animation style: thick round
limbs, a plain circle head, no face.
"""
import math
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QPainterPath

SCALE = 0.9                       # overall size of the stickman (was 1.2)
TORSO, HEAD_R = 48, 15
UARM, FARM = 26, 25
THIGH, SHIN = 32, 32
STAND = 60                        # hip -> foot distance when standing
ARM_REACH, LEG_REACH = UARM + FARM, THIGH + SHIN

# Hands are relative to the shoulder, feet relative to the hip, +x = forward.
BASE = dict(ha_x=-14, ha_y=46, hb_x=14, hb_y=46,
            fa_x=-11, fa_y=STAND, fb_x=11, fb_y=STAND,
            lean=0.0, hip_dy=0.0, head_dx=0.0, head_dy=0.0)


def P(**overrides):
    pose = dict(BASE)
    pose.update(overrides)
    return pose


def two_bone_ik(root, target, l1, l2, bend):
    dx, dy = target[0] - root[0], target[1] - root[1]
    d = max(abs(l1 - l2) + 1e-3, min(math.hypot(dx, dy), l1 + l2 - 1e-3))
    base = math.atan2(dy, dx)
    cos_a = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    a = math.acos(max(-1.0, min(1.0, cos_a)))
    th = base + bend * a
    joint = (root[0] + l1 * math.cos(th), root[1] + l1 * math.sin(th))
    end = (root[0] + d * math.cos(base), root[1] + d * math.sin(base))
    return joint, end


class Rig:
    def __init__(self):
        self.cur = P()

    def blend(self, target, speed, dt):
        k = 1 - math.exp(-speed * dt)
        for key, v in target.items():
            self.cur[key] += (v - self.cur[key]) * k

    def skeleton(self, x, y, facing, rot=0.0, sx=1.0, sy=1.0):
        """World-space joints. (x, y) = point between his feet. rot = flip angle,
        sx/sy = squash & stretch."""
        c = self.cur
        hip = (0.0, -STAND + c["hip_dy"])
        neck = (c["lean"], hip[1] - TORSO)
        head = (neck[0] + c["head_dx"], neck[1] - HEAD_R - 4 + c["head_dy"])
        sh = (neck[0], neck[1] + 5)
        arm_a = two_bone_ik(sh, (sh[0] + c["ha_x"], sh[1] + c["ha_y"]), UARM, FARM, +1)
        arm_b = two_bone_ik(sh, (sh[0] + c["hb_x"], sh[1] + c["hb_y"]), UARM, FARM, +1)
        leg_a = two_bone_ik(hip, (hip[0] + c["fa_x"], hip[1] + c["fa_y"]), THIGH, SHIN, -1)
        leg_b = two_bone_ik(hip, (hip[0] + c["fb_x"], hip[1] + c["fb_y"]), THIGH, SHIN, -1)

        a = rot * facing
        ca, sa = math.cos(a), math.sin(a)

        def tf(pt):
            lx, ly = pt[0] * facing, pt[1]
            dx, dy = lx, ly - hip[1]
            lx, ly = dx * ca - dy * sa, hip[1] + dx * sa + dy * ca
            return (x + SCALE * sx * lx, y + SCALE * sy * ly)

        return dict(
            hip=tf(hip), neck=tf(neck), head=tf(head), sh=tf(sh),
            arm_a=[tf(sh), tf(arm_a[0]), tf(arm_a[1])],
            arm_b=[tf(sh), tf(arm_b[0]), tf(arm_b[1])],
            leg_a=[tf(hip), tf(leg_a[0]), tf(leg_a[1])],
            leg_b=[tf(hip), tf(leg_b[0]), tf(leg_b[1])])


def draw_figure(p, sk, body, outline, alpha=1.0, k=1.0):
    p.save()
    p.setOpacity(alpha)
    chains = [[sk["hip"], sk["neck"]], sk["leg_b"], sk["arm_b"], sk["leg_a"], sk["arm_a"]]
    for color, width in ((outline, 9.5 * SCALE * k), (body, 5.5 * SCALE * k)):
        pen = QPen(color, width, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        for chain in chains:
            path = QPainterPath(QPointF(*chain[0]))
            for pt in chain[1:]:
                path.lineTo(QPointF(*pt))
            p.drawPath(path)
    p.setPen(QPen(outline, 3.2 * SCALE * k))
    p.setBrush(body)
    p.drawEllipse(QPointF(*sk["head"]), HEAD_R * SCALE * k, HEAD_R * SCALE * k)
    p.restore()
