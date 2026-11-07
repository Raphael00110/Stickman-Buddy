"""
Every move is one tiny function: pose(m, t, st) -> (target_pose, blend_speed).
  m  = the mascot (phase, speed, aim vectors...)   t = global time
  st = seconds since this pose started (for wind-up / strike / recover timing)
Higher blend_speed = snappier. Write a new move by copying any of these.
"""
import math
from rig import P, STAND, ARM_REACH, LEG_REACH


def idle(m, t, st):
    b = math.sin(t * 2.2)
    return P(ha_y=46 + b * 1.5, hb_y=46 + b * 1.5, hip_dy=b * 1.2,
             head_dx=math.sin(t * 0.7) * 2), 8


def walk(m, t, st):
    r = min(1.0, m.speed / 450.0)
    s, c = math.sin(m.phase), math.cos(m.phase)
    amp, lift = 22 + 10 * r, 12 + 10 * r
    return P(fa_x=s * amp, fa_y=STAND - max(0, c) * lift,
             fb_x=-s * amp, fb_y=STAND - max(0, -c) * lift,
             ha_x=-s * (14 + 8 * r), ha_y=44 - 22 * r,
             hb_x=s * (14 + 8 * r), hb_y=44 - 22 * r,
             hip_dy=-abs(c) * (3 + 2 * r), lean=3 + 13 * r), 14


def sneak(m, t, st):
    s, c = math.sin(m.phase), math.cos(m.phase)
    return P(fa_x=s * 12, fa_y=STAND - max(0, c) * 6,
             fb_x=-s * 12, fb_y=STAND - max(0, -c) * 6,
             ha_x=14, ha_y=30, hb_x=18, hb_y=26, hip_dy=16, lean=12, head_dx=6), 10


def flee(m, t, st):                      # sprinting with arms flailing overhead
    base, _ = walk(m, t, st)
    f = math.sin(t * 18)
    base.update(ha_x=-8 + f * 6, ha_y=-38 + f * 10, hb_x=10 - f * 6,
                hb_y=-40 - f * 10, lean=base["lean"] + 4)
    return base, 16


def cower(m, t, st):
    sh = math.sin(t * 45) * 1.6
    return P(ha_x=10, ha_y=-20, hb_x=14, hb_y=-18, hip_dy=14, lean=-4 + sh,
             head_dx=-2 + sh, fa_x=-8, fb_x=8), 14


def jump(m, t, st):
    return P(ha_x=-16, ha_y=-34, hb_x=18, hb_y=-34, fa_x=-8, fa_y=38,
             fb_x=14, fb_y=32, lean=3), 14


def fall(m, t, st):
    fl = math.sin(t * 20) * 6
    return P(ha_x=-24, ha_y=-14 + fl, hb_x=24, hb_y=-14 - fl,
             fa_x=-10, fa_y=48 + fl, fb_x=10, fb_y=52 - fl), 12


def land(m, t, st):
    return P(hip_dy=16, fa_x=-16, fb_x=16, ha_x=-22, ha_y=40,
             hb_x=22, hb_y=40, lean=6), 30


def stance(m, t, st):                    # fists up, bouncing
    bob = math.sin(t * 8) * 2
    return P(fa_x=-18, fb_x=18, hip_dy=8 + bob, ha_x=14, ha_y=-4,
             hb_x=24, hb_y=2, lean=6), 12


def punch(m, t, st):                     # wind-up, then the fist flies AT the cursor
    ax, ay = m.aim_s
    k = min(1.0, ARM_REACH * 0.98 / (math.hypot(ax, ay) or 1.0))
    if st < 0.12:
        return P(fa_x=-18, fb_x=18, hip_dy=8, ha_x=14, ha_y=-2,
                 hb_x=-12, hb_y=14, lean=-6), 40
    if st < 0.32:
        return P(fa_x=-18, fb_x=20, hip_dy=10, ha_x=14, ha_y=-4,
                 hb_x=ax * k, hb_y=ay * k, lean=14), 70
    return stance(m, t, st)


def kick(m, t, st):                      # the foot flies at the cursor
    ax, ay = m.aim_h
    k = min(1.0, LEG_REACH * 0.98 / (math.hypot(ax, ay) or 1.0))
    if st < 0.15:
        return P(fa_x=-14, fb_x=6, fb_y=28, hip_dy=6, lean=-10,
                 ha_x=-16, ha_y=20, hb_x=20, hb_y=14), 40
    if st < 0.36:
        return P(fa_x=-14, fb_x=ax * k, fb_y=ay * k, hip_dy=8, lean=-14,
                 ha_x=-24, ha_y=6, hb_x=24, hb_y=2), 70
    return stance(m, t, st)


def taunt(m, t, st):                     # "come on then" beckoning
    return P(ha_x=-4, hb_x=26 + math.sin(t * 10) * 4, hb_y=-2, lean=-6,
             head_dx=-3, hip_dy=4, fa_x=-14, fb_x=14), 10


def victory(m, t, st):
    b = abs(math.sin(t * 9))
    return P(ha_x=-14, ha_y=-46, hb_x=14, hb_y=-46, hip_dy=-b * 4), 14


def tired(m, t, st):
    b = math.sin(t * 6) * 2
    return P(ha_x=10, ha_y=34, hb_x=14, hb_y=36, lean=18, hip_dy=10 + b,
             head_dy=6 + b, fa_x=-12, fb_x=12), 7


def sit(m, t, st):                       # legs dangling off a ledge
    sw = math.sin(t * 2.5) * 7
    return P(hip_dy=STAND, fa_x=30, fa_y=30 + sw, fb_x=26, fb_y=30 - sw,
             ha_x=8, ha_y=40, hb_x=16, hb_y=40, lean=-3, head_dx=4), 6


def look(m, t, st):                      # hand shading eyes, scanning
    return P(hb_x=14, hb_y=-18, head_dx=math.sin(t * 2) * 4, lean=2), 8


def thinking(m, t, st):
    return P(ha_x=11, ha_y=-12, hb_x=12, hb_y=34,
             fb_y=STAND - abs(math.sin(t * 6)) * 5, head_dx=3, lean=-2), 9


def wave(m, t, st):
    return P(hb_x=22 + math.sin(t * 12) * 9, hb_y=-45, head_dx=2), 12


def tinker(m, t, st):
    return P(hb_x=26 + math.cos(t * 8) * 6, hb_y=18 + math.sin(t * 8) * 6,
             ha_x=18, ha_y=26, head_dy=3, lean=5), 12


def dance(m, t, st):
    t = t * m.tempo
    s, c = math.sin(t * 9), math.cos(t * 9)
    return P(ha_x=-12 - s * 8, ha_y=-20 - s * 26, hb_x=12 + s * 8, hb_y=-20 + s * 26,
             fa_x=-12 + s * 6, fb_x=12 + s * 6,
             fa_y=STAND - max(0, s) * 8, fb_y=STAND - max(0, -s) * 8,
             hip_dy=abs(c) * 5, lean=s * 5, head_dx=s * 3), 18


def smash(m, t, st):                     # two-fisted overhead slam
    if st < 0.45:
        k = min(1.0, st / 0.35)
        return P(ha_x=4, ha_y=-62, hb_x=12, hb_y=-62, lean=-9 * k,
                 hip_dy=3 * k, head_dx=-3), 10
    return P(ha_x=22, ha_y=48, hb_x=28, hb_y=48, lean=15, hip_dy=9,
             head_dx=5, fa_x=-14, fb_x=16), 45


def headbang(m, t, st):                  # metal
    t = t * m.tempo
    b = math.sin(t * 8)
    return P(ha_x=18, ha_y=-4, hb_x=24, hb_y=4, hip_dy=abs(b) * 7, lean=b * 11,
             head_dx=b * 9, head_dy=abs(b) * 6, fa_x=-18, fb_x=18), 20


def air_guitar(m, t, st):                # one hand on the neck, one hand strumming
    t = t * m.tempo
    return P(ha_x=28, ha_y=8, hb_x=8 + math.cos(t * 14) * 5, hb_y=26 + math.sin(t * 14) * 7,
             hip_dy=10 + math.sin(t * 6) * 2, lean=-8, head_dx=-2, head_dy=3,
             fa_x=-18, fb_x=20), 16


def dj(m, t, st):                        # scratching a pair of decks
    t = t * m.tempo
    return P(ha_x=24 + math.sin(t * 7) * 7, ha_y=28, hb_x=24 + math.cos(t * 7) * 7, hb_y=28,
             head_dy=math.sin(t * 8) * 2.5, lean=6, hip_dy=3 + abs(math.sin(t * 4)) * 3,
             fa_x=-12, fb_x=14), 14


def dangle(m, t, st):                    # being carried: hangs by his hands, legs swinging with your cursor
    sw = getattr(m, "drag_swing", 0.0) * m.body.facing
    sw = max(-900.0, min(900.0, sw)) / 60.0
    k = math.sin(t * 5) * 4
    return P(ha_x=-6, ha_y=-62, hb_x=8, hb_y=-62, fa_x=-6 - sw, fa_y=STAND + 8 + k,
             fb_x=6 - sw, fb_y=STAND + 8 - k, lean=-sw * 0.5, head_dx=-sw * 0.2), 14


def jack(m, t, st):                      # jumping jacks
    s = abs(math.sin(t * 7.5))           # 0 = arms down / feet together, 1 = arms up / feet apart
    return P(ha_x=-14 + 6 * s, ha_y=46 - 98 * s, hb_x=14 - 6 * s, hb_y=46 - 98 * s,
             fa_x=-11 - 13 * s, fb_x=11 + 13 * s, hip_dy=-s * 5), 20


def shadowbox(m, t, st):                 # alternating jabs, bouncing on his toes
    s = math.sin(t * 9)
    a, b = max(0.0, s), max(0.0, -s)
    return P(fa_x=-16, fb_x=18, hip_dy=8 + abs(s) * 2, ha_x=10 + 24 * a, ha_y=-6 - 4 * a,
             hb_x=10 + 24 * b, hb_y=-6 - 4 * b, lean=5 + 3 * s, head_dx=2), 16


def talk(m, t, st):                      # gesturing while he speaks
    return P(ha_x=16 + math.sin(t * 6) * 6, ha_y=18 + math.cos(t * 5) * 8,
             hb_x=18 + math.cos(t * 7) * 6, hb_y=14 + math.sin(t * 4) * 8,
             head_dy=math.sin(t * 16) * 1.2, head_dx=math.sin(t * 3) * 1.5, lean=math.sin(t * 2) * 1.5), 10


def meditate(m, t, st):                  # cross-legged, breathing
    b = math.sin(t * 1.2) * 1.5
    return P(hip_dy=STAND - 4 + b, fa_x=24, fa_y=24, fb_x=20, fb_y=26, ha_x=18, ha_y=24,
             hb_x=20, hb_y=26, head_dy=2 + b, lean=-2), 5


def wand(m, t, st):                      # waving a magic wand
    return P(hb_x=24 + math.sin(t * 11) * 9, hb_y=-34 + math.cos(t * 11) * 8, ha_x=-10, ha_y=40,
             lean=-4, head_dx=2), 14


POSES = dict(talk=talk, meditate=meditate, wand=wand, dangle=dangle, jack=jack, shadowbox=shadowbox, idle=idle, walk=walk, sneak=sneak, flee=flee, cower=cower, jump=jump,
             fall=fall, land=land, stance=stance, punch=punch, kick=kick,
             taunt=taunt, victory=victory, tired=tired, sit=sit, look=look,
             thinking=thinking, wave=wave, tinker=tinker, dance=dance, smash=smash,
             headbang=headbang, air_guitar=air_guitar, dj=dj)
