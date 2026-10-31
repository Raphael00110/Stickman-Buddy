"""
The stickman's personality: a small mood machine.

  fear     rises when your cursor is close and FAST, fades when you leave him alone
  courage  drifts randomly (chaos!), grows while he's being chased, and SPIKES
           when he's cornered - that's when the scared stickman snaps and fights

Each behaviour is a generator ("a_flee", "a_fight"...). Higher priority
behaviours interrupt lower ones. Add a new behaviour by writing a generator
and adding it to _idle_choice() or _decide().

Music: when main.py reports a song, he grooves (each song gets its own dance
style and tempo from a hash of the title) and, if mischief is on, now and then
pulls a harmless prank (see routines.py).
"""
import datetime
import math
import random
import re
import time
import traceback
import zlib
from collections import deque
from functools import partial

from fun import JOKES, COMPLIMENTS, ROASTS, NARRATION, SHOWOFF
from memory import Memory
from settings import SETTINGS, DIRECTOR_INTERVAL
from rig import SCALE, ARM_REACH
import routines

FIGHT_COURAGE = 0.55
REACH = ARM_REACH * SCALE            # how far his fist goes
STYLES = ["dance", "headbang", "air_guitar", "dj"]

LINES = {
    "flee": ["Nope nope nope!", "Not again!!", "Run run run!", "Why me?!", "Please no!"],
    "fight": ["Come at me!", "Hyah!", "Wrong stickman to mess with!", "Let's go, pointer!"],
    "taunt": ["Is that all you've got?", "Too slow!", "Come on then!"],
    "victory": ["Ha! Take that!", "Still got it.", "Undefeated!"],
    "tired": ["Okay... I'm done...", "*wheeze*", "Cursor 1, me 0..."],
    "curious": ["Whatcha doing?", "Psst, what are you working on?", "Hmm, what's that?"],
    "prank": ["Tag, you're it!", "Hehe.", "Boop!"],
    "cornered": ["That's it, no more running!", "I'm cornered?! Fine!"],
    "music_stop": ["Aww, it stopped.", "Hey, bring the music back!"],
    "pet": ["Hehe, that tickles!", "Aww, thanks!", "More scritches?", "Okay... that's nice."],
    "welcome_back": ["You're back!", "Oh! Hi! I was resting my eyes.", "Hey! Did I miss anything?"],
    "stretch": ["Stretch break! Seriously.", "Water? Posture? Eyes off the screen!",
                "You've been at it a while. Stretch!"],
    "tag_start": ["Tag! You're it. Catch me!", "Game on! Try to catch me!"],
    "tag_caught": ["Ow! Tagged! Now I'm coming for YOU!", "You got me! Run!"],
    "tag_tagged": ["Tag! You're it!", "Boop! Your turn!"],
    "tag_bored": ["Hello? Still playing?", "Aww, you left me hanging..."],
    "follow": ["Coming!", "Wait for me!", "Mind if I tag along?"],
    "short_next": ["Ooh, next!", "Swipe!", "Onwards!", "What's next?", "Scroll scroll scroll~"],
    "short_back": ["Wait, go back!", "Rewind!", "Again again!", "Back we go~"],
    "short_react": ["Ha!", "Ooooh.", "Wait, what?", "Relatable.", "Not bad!", "Okay that was good."],
    "grabbed": ["Hey! Put me down!", "Whoa, whoa, whoa!", "I'm flying!", "Heyyy!"],
    "thrown": ["WHEEEEE!", "Not the face!", "Again again!", "Yeeeeet!"],
    "dropped": ["Thanks for the lift!", "Oof.", "Hey, I was walking there!", "Gentle, please~"],
    "ouch": ["Ow.", "Oof!", "That's gonna leave a mark.", "I'm okay! ...I'm okay."],
    "jacks": ["One, two, three!", "Gotta stay fit!", "Feel the burn!"],
}

# things you can type to him (Ctrl+Alt+T). (action, regex, max words in the sentence)
COMMAND_WORDS = (
    # Shorts / Reels / TikTok scrolling ("up" = what swiping up does = next video)
    ("short_next", r"^(up|next|skip|swipe up|scroll up|go up|next one|next video)$", 3),
    ("short_back", r"^(back|go back|previous|prev|down|go down|previous video)$", 3),
    ("shorts_on", r"\bshorts?( mode)? on\b|\bwatch (with me|shorts|reels|tiktok)\b|\bwatch together\b", 5),
    ("shorts_off", r"\bshorts?( mode)? off\b|\bstop watching\b", 5),
    ("tag", r"\btag\b|\bcatch me\b|\bchase me\b", 6),
    ("follow", r"\bcome (here|over|to me)\b|\bfollow( me)?\b", 6),
    ("nap", r"\b(sleep|nap|go to bed|goodnight|good night)\b", 6),
    ("dance", r"\b(dance|boogie|groove)\b", 6),
    ("flip", r"\b(flip|jump|backflip)\b", 6),
    ("cheer", r"\b(cheer|celebrate|good job|well done|nice one)\b", 6),
    ("wave", r"\b(hi|hello|hey|yo|wave)\b", 3),
)
ACKS = {
    "shorts_on": ["Okay! Let's watch together."], "shorts_off": ["Okay, no more shorts."],
    "tag": ["You're on! Catch me!"], "follow": ["Coming!"], "nap": ["Okay... zzz..."],
    "dance": ["Watch this!"], "flip": ["Hup!"], "cheer": ["Woohoo!"], "wave": ["Hi hi!"],
}
LEVEL_LINES = {"acquaintance": "Hey, I'm starting to like you.", "friend": "I think we're friends now!",
               "best buddy": "You're my best buddy!!"}
GAME_ACTIONS = ("tag", "follow")
NAP_AFTER = 120          # seconds of no input before he dozes off


def match_command(text):
    """'play tag' -> 'tag'. Only SHORT messages count, so real conversation isn't hijacked."""
    t = re.sub(r"[^\w\s]", "", text.lower()).strip()
    words = len(t.split())
    for name, pattern, max_words in COMMAND_WORDS:
        if words <= max_words and re.search(pattern, t):
            return name
    return None


def sign(v):
    return 1 if v >= 0 else -1


class Behavior:
    def __init__(self, m):
        self.m = m
        self.fear, self.courage, self.courage_base = 0.0, 0.2, 0.25
        self.action = None
        self.name, self.priority = "", 0
        self.mode = None                  # None | "watch" (hang out in the corner)
        # first pranks don't fire until he's been around a while
        self.cooldowns = {"prank_media": 90, "tab": 180, "skip": 150}
        self.say_ready = 0.0
        self.hook = None                  # hook(kind) -> True if something else will speak
        self.media = None                 # now-playing dict while something plays (set by main.py)
        self.actions = None               # MediaControl-like object (set by main.py)
        self.browser_active = False
        self.song_style = "dance"
        # --- AI director (see _ask_ai): it only ever picks from the legal action list
        self.ai = None                    # ask(state, options, recent, callback) - set by main.py
        self.ai_choice = None             # (action, say, born) waiting for the next idle slot
        self.ai_next, self.ai_busy_until = 6.0, 0.0
        self.recent = deque(maxlen=4)
        self.window, self.window_kind = "", "other"   # set by main.py
        # --- social side: petting, games, naps, chat commands
        self.mem = Memory(persist=False)              # main.py swaps in the real, saved one
        self.idle_for = 0.0                           # seconds since your last input (main.py)
        self.pet_t = 0.0                              # how long you've been gently hovering on him
        self.in_game = False                          # playing tag / following: don't panic
        self.calm_until = 0.0                         # after being picked up / put down he isn't scared of you
        self.throws = deque(maxlen=4)                 # when you threw him (too many = dizzy)
        self.script, self.demo_mode = [], False       # control panel: script runner + auto-show mode
        self.last_error = None
        self.explicit = False
        self.started = time.time()
        self.pending_cmd = None                       # (name, force, born)
        self.shorts = False                           # True while you're scrolling Shorts/Reels/TikTok (main.py)
        self.commands = dict(
            short_next=partial(self.a_swipe, "next"), short_back=partial(self.a_swipe, "back"),
            dance=lambda: self.a_groove() if self.music_on else self.a_dance(),
            follow=self.a_follow, tag=self.a_tag, nap=partial(self.a_nap, True), flip=self.a_flip,
            wave=self.a_wave, cheer=self.a_cheer, stretch=self.a_stretch, think=self.a_think)

    # ---------------------------------------------------------------- plumbing
    @property
    def music_on(self):
        return bool(SETTINGS["music_react"] and self.media and self.media.get("kind") == "music")

    def cancel(self):
        if self.action:
            self.action.close()
        self.action, self.name, self.priority = None, "", 0
        self.in_game = False
        self.m.clear_pose()
        self.m.rot = 0.0
        self.m.body.desired_vx = 0.0

    def ready(self, key):
        return self.m.t >= self.cooldowns.get(key, 0)

    def set_cd(self, key, seconds):
        self.cooldowns[key] = self.m.t + seconds

    def line(self, kind, chance=0.8, ai=True):
        m = self.m
        level = max(0, min(3, int(SETTINGS.get("chat_level", 2))))      # 0 quiet .. 3 nonstop
        if not SETTINGS["chatty"] or level == 0 or m.t < self.say_ready:
            return
        if random.random() > min(1.0, chance * (0, 1.0, 1.5, 2.5)[level]):
            return
        self.say_ready = m.t + (99, 4.0, 2.0, 0.6)[level]
        if ai and self.hook and self.hook(kind):      # ai=False for lines that must be instant
            return
        m.say(random.choice(LINES[kind]), 2.6)

    # ---------------------------------------------------------------- being picked up
    def on_grabbed(self):
        m = self.m
        self.pending_cmd = None
        self.calm_until = m.t + 3.0
        self.fear = 0.0
        m.emote("!", 0.8)
        self.line("grabbed", 0.9, ai=False)

    def on_dropped(self, speed):
        m = self.m
        self.calm_until = m.t + 2.5                   # don't bolt from the hand that just put him down
        self.fear = 0.0
        self.throws.append(m.t)
        if speed > 900:
            m.emote("!!", 0.9)
            self.line("thrown", 0.9, ai=False)
        else:
            self.line("dropped", 0.5, ai=False)
        if speed > 600 and sum(m.t - t < 30 for t in self.throws) >= 3:      # thrown around too much
            m.fx("dizzy", at="head", loops=0, duration=2.5, follow=True)

    def on_hard_landing(self):
        self.line("ouch", 0.8, ai=False)

    def on_click(self):
        if SETTINGS["scared"] and self.m.cursor_dist() < 300:
            self.fear = max(self.fear, 0.9)
            self.m.emote("!!", 0.8)

    def song_changed(self, info):
        """Called by main.py when a new song starts. Picks this song's dance and reacts."""
        m = self.m
        h = zlib.crc32(f"{info.get('title','')}{info.get('artist','')}".encode())
        self.song_style = STYLES[h % len(STYLES)]
        m.tempo = 0.85 + (h >> 8) % 40 / 100          # 0.85x - 1.24x
        if info.get("kind") != "music" or not SETTINGS["music_react"] or m.routine or self.priority >= 2:
            return
        title = info.get("title", "")
        m.emote("♪", 1.5)
        if SETTINGS["chatty"]:
            m.say(f"♪ {title[:30]}" + ("…" if len(title) > 30 else ""), 3)
        self._start("groove", 1, self.a_groove)

    def _start(self, name, priority, factory, explicit=False):
        self.cancel()
        self.explicit = explicit                      # True = YOU asked for it (panel/script/chat): it may talk even in Quiet
        self.name, self.priority = name, priority
        self.in_game = name in GAME_ACTIONS
        self.action = factory()

    # ---------------------------------------------------------------- main tick
    # ---------------------------------------------------------------- social plumbing
    @property
    def affection(self):
        return self.mem.data["affection"]

    def _sfx(self, name, vol=1.0):
        sfx = getattr(self.m, "sfx", None)
        if sfx:
            # Dramatic cues in scripted jokes/coding scenes are intentional.
            # Never duck or suppress them as if they were background footsteps.
            demo_cue = name in {"drumroll", "rimshot", "laugh"}
            played = sfx.play(name, vol, 0.2, force=demo_cue)
            if demo_cue and not played:
                print(f"[sound] cue not played: {name} (check SFX settings / Qt audio)")

    def _gain(self, amount):
        """Grow the friendship; celebrate when he reaches a new level."""
        level = self.mem.add_affection(amount)
        if level:
            m = self.m
            m.say(LEVEL_LINES.get(level, "Yay!"), 4)
            m.emote("♥", 2.0)
            self._sfx("victory", 0.7)
            m.fx("confetti", at="head", offset=(0, -60 * SCALE))

    def _factory(self, name):
        """A move by name: the built-in commands first, then ANY a_<name> method (so the control panel reaches
        everything)."""
        if name in self.commands:
            return self.commands[name]
        return getattr(self, "a_" + name, None) if name.isidentifier() and name != "swipe" else None

    def command(self, name, force=False, *args):
        """An outside nudge (typed command, tray menu, reminder, app reaction).
        force=True is YOU asking, so it interrupts anything; otherwise he only does it when he's
        not busy, and never while you're watching a video. Returns True if accepted."""
        if self._factory(name) is None:
            return False
        if name in ("short_next", "short_back") and not self.shorts:   # never press scroll keys outside a feed
            return False
        if self.mode == "watch" and not force:
            return False
        self.pending_cmd = (name, force, self.m.t, args)
        return True

    def _consume_command(self):
        c = self.pending_cmd
        if not c:
            return
        name, force, born, args = c
        if self.m.t - born > 6:                       # too old to still make sense
            self.pending_cmd = None
        elif force or self.priority < 2:
            self.pending_cmd = None
            fn = self._factory(name)
            try:
                self._start(name, 2, (lambda: fn(*args)) if args else fn, explicit=bool(force))
            except Exception:
                traceback.print_exc()
                self.cancel()

    def update(self, dt):
        self._emotions(dt)
        self._consume_command()
        want = self._decide()
        if want and want[0] != self.name and (self.action is None or want[1] > self.priority):
            self._start(*want)
        if self.action is None:
            self._start(*self._idle_choice())
        try:
            next(self.action)
        except StopIteration:
            self.cancel()
        except Exception:                                 # a buggy move must NEVER take the whole app down
            print(f"[behavior] '{self.name}' failed and was stopped:")
            traceback.print_exc()
            self.last_error = f"{self.name}: {traceback.format_exc().strip().splitlines()[-1]}"
            self.cancel()

    def _emotions(self, dt):
        m, b = self.m, self.m.body
        d = m.cursor_dist()
        if SETTINGS["scared"]:
            prox = max(0.0, 1 - d / 320)
            threat = prox * (0.5 + 0.5 * min(1.0, m.cursor_speed / 1400))
            if d < 110:                                   # personal space!
                threat += 0.35 * (1 - d / 110)
            if m.cursor_speed < 150:                      # a slow, gentle cursor isn't a threat
                threat *= 0.35
            threat *= 1 - 0.6 * self.affection            # friends are braver around you
        else:
            threat = 0.0
        self.fear += (threat - self.fear) * (3.0 if threat > self.fear else 0.35) * dt
        if d < 100 and 8 < m.cursor_speed < 150:          # slow, moving cursor on him = petting
            self.pet_t += dt
        else:
            self.pet_t = max(0.0, self.pet_t - 2 * dt)

        self.courage_base = min(0.5, max(0.05, self.courage_base + random.gauss(0, 0.1 * math.sqrt(dt))))
        self.courage += (self.courage_base - self.courage) * 0.3 * dt
        if self.name == "flee":
            self.courage += 0.08 * dt                        # getting fed up
        cornered = d < 260 and ((b.x < 110 and m.cursor[0] > b.x) or (b.x > m.W - 110 and m.cursor[0] < b.x))
        if cornered and self.name == "flee":
            self.courage += 0.9 * dt
        if self.fear > 0.3 and random.random() < 0.08 * dt:  # random "snap!"
            self.courage = 0.9
        self.courage = min(1.0, max(0.0, self.courage))

    def _decide(self):
        m = self.m
        if self.in_game:                                  # playing: nothing to be scared of
            return None
        if m.t < self.calm_until:
            return None
        if SETTINGS["interact"] and self.pet_t > 1.6 and self.ready("pet"):
            return ("pet", 1, self.a_pet)
        if (SETTINGS["sleepy"] and self.idle_for > NAP_AFTER and self.ready("nap")
                and self.mode != "watch" and not self.music_on):
            return ("nap", 1, self.a_nap)                 # you're away: he dozes off
        if not SETTINGS["scared"]:
            return None
        d, fear = m.cursor_dist(), self.fear
        if SETTINGS["fighting"] and fear > 0.28 and d < 280 and self.courage >= FIGHT_COURAGE and self.ready("fight"):
            return ("fight", 3, self.a_fight)
        if fear > 0.5 and self.courage < FIGHT_COURAGE:
            return ("flee", 2, self.a_flee)
        if 140 < d < 520 and fear < 0.15 and m.cursor_speed < 250 and self.ready("curious"):
            return ("curious", 1, self.a_curious)
        return None

    def _idle_choice(self):
        if self.demo_mode:                                # auto-show: a steady stream of showpiece moves
            return self._demo_choice()
        m = self.m
        opts = [("wander", 3.5), ("sit", 0.8), ("look", 1.2), ("dance", 1.0), ("zoom", 1.0), ("think", 0.6),
                ("wave", 0.5), ("cheer", 0.3), ("jacks", 0.8), ("shadowbox", 0.7), ("parkour", 1.2),
                ("moonwalk", 0.6), ("flip", 0.6), ("party", 0.3), ("superhero", 0.4), ("magic", 0.5),
                ("karate", 0.5), ("vanish", 0.5), ("giant", 0.25), ("tiny", 0.25), ("meditate", 0.4),
                ("joke", 0.6), ("compliment", 0.35), ("roast", 0.3), ("clock", 0.3)]
        has_windows = any(p[0] != "floor" for p in m.platforms)
        if has_windows:
            opts.append(("hop_window", 2.5))
        if self.mode == "watch":
            opts = [("perch", 9)] + opts[:3]
        if self.music_on:
            opts = [("groove", 8), ("wander", 1), ("look", 0.5)] + ([("hop_window", 1)] if has_windows else [])
        if SETTINGS["interact"] and self.mode != "watch" and not self.music_on and self.idle_for < 20:
            opts.append(("tag", 0.35))                    # you're here and active: invite you to play
            if self.affection > 0.35:
                opts.append(("follow", 2.0 * self.affection))
        if self.shorts:
            opts.append(("short_react", 3))               # watching a feed together: he reacts to it
        if self.actions and SETTINGS["mischief"]:
            if self.music_on and self.ready("prank_media"):
                opts.append(("prank_pause", 2))
            if (self.browser_active and self.mode != "watch" and self.ready("tab")
                    and m.foreground_provider()):                   # never flip tabs mid-video
                opts.append(("tab_peek", 2))
        if self.actions and SETTINGS["skip_songs"] and self.music_on and self.ready("skip"):
            opts.append(("skip_song", 1.5))
        if self.mode != "watch":                          # variety: not the same thing twice in a row
            fresh = [o for o in opts if o[0] not in list(self.recent)[-2:]]
            if len(fresh) >= 2:
                opts = fresh
        names, weights = zip(*opts)
        legal = list(names)                           # everything in here is allowed RIGHT NOW
        picked = self._take_ai_choice(legal)
        if picked:
            name, say = picked
            if say and SETTINGS["chatty"] and m.t >= self.say_ready:
                self.say_ready = m.t + 4
                m.say(say, 2.6)
        else:
            name = random.choices(names, weights)[0]
        if not (picked and picked[1]):
            self._narrate(name)                           # mutters about what he's doing (more at higher levels)
        self._ask_ai(legal)                           # prefetch the NEXT decision while this one plays
        self.recent.append(name)
        return name, 0, getattr(self, "a_" + name)

    # ---------------------------------------------------------------- AI director
    def _ai_state(self):
        m, h = self.m, datetime.datetime.now().hour
        return dict(
            time_of_day="morning" if 5 <= h < 12 else "afternoon" if h < 17 else "evening" if h < 22 else "night",
            window=self.window[:60],
            window_kind=self.window_kind,
            music=(self.media.get("title", "")[:40] if self.music_on else None),
            cursor="near" if m.cursor_dist() < 300 else "far",
            mood="nervous" if self.fear > 0.3 else "bold" if self.courage > 0.4 else "relaxed",
            standing_on="the floor" if (not m.body.support or m.body.support[0] == "floor") else "a window",
            friendship=self.mem.level,
            user="away" if self.idle_for > 60 else "active",
        )

    def _ask_ai(self, legal):
        """Ask the model in the background. Never blocks; if it's slow or wrong we just stay random."""
        m = self.m
        if not (self.ai and SETTINGS["ai_director"]) or len(legal) < 2:
            return
        if m.t < self.ai_next or m.t < self.ai_busy_until:
            return
        self.ai_next, self.ai_busy_until = m.t + DIRECTOR_INTERVAL, m.t + 30
        self.ai(self._ai_state(), legal, list(self.recent), self._ai_reply)

    def _ai_reply(self, result):
        self.ai_busy_until = 0.0
        if result:
            self.ai_choice = (result["action"], result.get("say", ""), self.m.t)

    def _take_ai_choice(self, legal):
        c, self.ai_choice = self.ai_choice, None
        if not c or not SETTINGS["ai_director"]:
            return None
        action, say, born = c
        # re-check: the situation may have changed while the model was thinking
        if action in legal and self.m.t - born < 30:
            return action, say
        return None

    # ---------------------------------------------------------------- idle behaviours
    def a_wander(self):
        m = self.m
        x1, x2 = m.support_range()
        lo, hi = max(x1 + 40, 40), min(x2 - 40, m.W - 40)
        x = random.uniform(lo, hi) if lo < hi else (x1 + x2) / 2
        yield from m.walk_to(x, speed=random.uniform(90, 160))
        yield from m.wait(random.uniform(0.5, 2.0))

    def a_sit(self):
        m = self.m
        dur = random.uniform(3, 7)
        m.set_pose("sit")
        yield from m.wait(min(3, dur))
        if dur > 6 and not self.music_on:               # drifts off...
            m.fx("zzz", at="head", offset=(14 * SCALE, 0), loops=0, duration=dur - 3, follow=True)
        yield from m.wait(max(0, dur - 3))

    # ---------------------------------------------------------------- social behaviours
    def a_pet(self):
        """You hovered gently on him: he loves it."""
        m = self.m
        self.set_cd("pet", 10)
        self.pet_t = 0.0
        self.mem.bump("pets")
        self._gain(0.03)
        m.face_cursor()
        if not m.fx("heart", at="head", follow=True, loops=2):
            m.emote("♥", 1.6)
        self._sfx("aww", 0.9)
        self.line("pet", 0.9)
        m.set_pose(random.choice(["wave", "dance"]))
        yield from m.wait(2.2)

    def a_nap(self, forced=False):
        """Dozes off while you're away; wakes up (startled!) the moment you're back."""
        m = self.m
        self.set_cd("nap", 90)
        m.say("*yawn* ...nap time", 2.5)
        m.set_pose("sit")
        yield from m.wait(1.5)
        end, next_z = m.t + (8 if forced else 1800), 0.0
        while m.t < end and (forced or self.idle_for > 5):
            if m.t >= next_z:
                m.fx("zzz", at="head", offset=(14 * SCALE, 0), loops=0, duration=2.6, follow=True)
                self._sfx("snore", 0.5)
                next_z = m.t + 3.2
            yield
        m.emote("!", 1.0)
        self.line("welcome_back", 1.0, ai=False)
        m.set_pose("wave")
        yield from m.wait(1.8)

    def a_stretch(self):
        """Break reminder."""
        m = self.m
        self.set_cd("stretch", 600)
        m.emote("!", 1.0)
        self._sfx("ding", 0.8)
        m.say(random.choice(LINES["stretch"]), 5)
        m.set_pose("victory")                          # arms overhead = a big stretch
        yield from m.wait(2.8)
        m.set_pose("wave")
        yield from m.wait(1.2)

    def a_flip(self):
        m = self.m
        yield from m.jump(0, -840, flip=1)
        m.set_pose("victory")
        yield from m.wait(0.8)

    def a_follow(self, duration=10.0):
        """Tags along next to your cursor (and hops onto windows to keep up)."""
        m, b = self.m, self.m.body
        self.line("follow", 0.9, ai=False)
        end = m.t + duration
        while m.t < end:
            cx, cy = m.cursor
            dx = cx - b.x
            if cy < b.y - 220 and abs(dx) < 220 and b.on_ground:       # you're up on a window: hop up
                cand = [p for p in m.platforms if p[0] != "floor" and p[1] - 40 <= cx <= p[2] + 40
                        and 40 < b.y - p[3] < 360]
                if cand:
                    p = cand[0]
                    yield from m.hop_to(min(max(cx, p[1] + 30), p[2] - 30), p[3])
                    continue
            if abs(dx) > 110:
                b.facing = 1 if dx > 0 else -1
                b.desired_vx = b.facing * min(380, 110 + abs(dx) * 0.7)
                m.clear_pose()
            else:
                b.desired_vx = 0
                m.face_cursor()
                m.clear_pose()
            yield
        b.desired_vx = 0

    def a_tag(self):
        """A real game: you chase him with the cursor; catch him and HE chases YOU."""
        m, b = self.m, self.m.body
        self.set_cd("tag", 150)
        end, caught, grace, last_leap, bored = m.t + 45.0, 0, m.t + 2.0, -9.0, 0.0
        it = "you"                                     # who has to catch whom
        self.line("tag_start", 1.0, ai=False)
        m.emote("!", 1.0)
        yield from m.wait(0.5)
        try:
            while m.t < end:
                self.fear = min(self.fear, 0.15)       # it's a game, not a threat
                d = m.cursor_dist()
                cx, cy = m.cursor
                bored = bored + m.dt if (m.cursor_speed < 40 and d > 350) else 0.0
                if bored > 8:                          # you stopped playing
                    self.line("tag_bored", 1.0, ai=False)
                    break
                if it == "you":                        # YOU chase HIM
                    away = 1 if b.x >= cx else -1
                    at_wall = (b.x < 100 and away < 0) or (b.x > m.W - 100 and away > 0)
                    if at_wall and d < 260 and b.on_ground and m.t - last_leap > 1.5:
                        last_leap = m.t
                        yield from m.jump(-away * 520, -820, flip=1)          # hops OVER you
                        continue
                    b.facing, b.desired_vx = away, away * (290 + 25 * min(caught, 4))
                    m.clear_pose()
                    if d < 62 and m.t > grace:         # caught!
                        caught += 1
                        it, grace = "me", m.t + 1.6
                        b.desired_vx = 0
                        self._sfx("boop")
                        m.emote("!!", 0.9)
                        self.line("tag_caught", 1.0, ai=False)
                        yield from m.wait(0.6)
                        continue
                else:                                  # HE chases YOU
                    dx = cx - b.x
                    if cy < b.y - 150 * SCALE and abs(dx) < 120 and b.on_ground:
                        yield from m.jump(0, -760)
                        continue
                    m.face_cursor()
                    if d > REACH * 0.9:
                        b.desired_vx = sign(dx) * 340
                        m.clear_pose()
                    else:                              # got you!
                        b.desired_vx = 0
                        self.line("tag_tagged", 1.0, ai=False)
                        yield from m.strike("punch")
                        it, grace = "you", m.t + 1.6
                        continue
                yield
        finally:
            b.desired_vx = 0
        self.mem.bump("tag_games")
        self.mem.bump("tag_caught", caught)
        self.mem.data["best_tag"] = max(self.mem.data["best_tag"], caught)
        self._gain(0.04 if caught else 0.01)
        m.say(f"Game over! You caught me {caught} time{'s' if caught != 1 else ''}!", 4)
        if caught >= 3:
            m.fx("confetti", at="head", offset=(0, -60 * SCALE))
            m.set_pose("victory")
        else:
            m.set_pose("tired")
        yield from m.wait(2.0)

    # ---------------------------------------------------------------- watching shorts together
    def a_swipe(self, direction):
        """You said 'up' / 'go back': he does a little swipe gesture and the key goes to the feed."""
        m = self.m
        nxt = direction == "next"
        m.emote("↑" if nxt else "↓", 0.9)
        m.face_cursor()
        m.set_pose("tinker")                           # flicking at an invisible screen
        yield from m.wait(0.3)
        if self.actions:
            self.actions.short(direction)              # the real Down/Up key, 0.3s into the gesture
        yield from m.wait(0.45)
        self.line("short_next" if nxt else "short_back", 0.55, ai=False)

    def a_short_react(self):
        """Reacts to whatever is on screen: he can't see it, but he's a good audience."""
        m = self.m
        kind = random.choice(["laugh", "wow", "clap", "hmm"])
        if kind == "laugh":
            m.emote("ha!", 1.4)
            m.set_pose("victory")
        elif kind == "wow":
            m.emote("!", 1.2)
            m.set_pose("look")
        elif kind == "clap":
            m.set_pose("dance")
        else:
            m.emote("?", 1.2)
            m.set_pose("thinking")
        self.line("short_react", 0.5, ai=False)
        yield from m.wait(random.uniform(1.4, 2.2))

    # ---------------------------------------------------------------- more things to do
    def a_jacks(self):
        m = self.m
        self.line("jacks", 0.5, ai=False)
        m.set_pose("jack")
        yield from m.wait(random.uniform(3.0, 4.5))

    def a_shadowbox(self):
        m = self.m
        m.set_pose("shadowbox")
        yield from m.wait(random.uniform(3.0, 4.0))

    def a_parkour(self):
        """A little burst of jumps (with the odd flip) across wherever he's standing."""
        m, b = self.m, self.m.body
        for _ in range(random.randint(2, 4)):
            d = random.choice([-1, 1])
            if b.x < 200:
                d = 1
            elif b.x > m.W - 200:
                d = -1
            yield from m.jump(d * random.uniform(260, 520), -random.uniform(760, 900), flip=random.choice([0, 0, 1, -1]))
            yield from m.wait(0.25)

    def a_moonwalk(self):
        """Walks across while facing the OTHER way. Smooth."""
        m, b = self.m, self.m.body
        x1, x2 = m.support_range()
        lo, hi = max(x1 + 60, 60), min(x2 - 60, m.W - 60)
        tx = random.uniform(lo, hi) if lo < hi else b.x
        d = 1 if tx > b.x else -1
        end = m.t + 9
        m.clear_pose()
        while abs(b.x - tx) > 8 and m.t < end:
            b.facing, b.desired_vx = -d, d * 105
            yield
        b.desired_vx = 0
        yield from m.wait(0.4)

    # ---------------------------------------------------------------- talking + showpiece moves
    def _demo_choice(self):
        m = self.m
        pool = [n for n in SHOWOFF if hasattr(self, "a_" + n)] + (["groove"] * 3 if self.music_on else [])
        fresh = [n for n in pool if n not in list(self.recent)[-5:]] or pool
        name = random.choice(fresh)
        self.recent.append(name)
        self._narrate(name, force=True)
        return name, 0, getattr(self, "a_" + name)

    def _narrate(self, name, force=False):
        level = max(0, min(3, int(SETTINGS.get("chat_level", 2))))
        lines = NARRATION.get(name)
        if not lines or not SETTINGS["chatty"] or level == 0:
            return
        if force or random.random() < (0, 0.35, 0.75, 1.0)[level]:
            self.m.say(random.choice(lines), 2.4, queue=True)

    def _vm(self):
        """How his lines are voiced: 'force' when you explicitly asked for this move, else 'auto' (ambient)."""
        return "force" if self.explicit else "auto"

    def say_wait(self, text, voice=None, extra=0.25):
        """Say a line and wait until the bubble has been up long enough AND the voice has finished."""
        m = self.m
        voice = voice or self._vm()
        m.say(text, 2.0, voice=voice)
        yield from m.wait(max(1.6, len(text) / 11.0) + extra)
        guard = m.t + 12
        while m.speaker_busy() and m.t < guard:
            yield

    def a_pose(self, name="idle", secs=3.0):
        self.m.set_pose(name)
        yield from self.m.wait(secs)

    def a_script(self):
        """Runs the script from the control panel (say / do / pose / fx / sound / emote / wait)."""
        m = self.m
        try:
            for cmd, arg, _line in list(self.script):
                if cmd == "say":
                    yield from self.say_wait(arg, voice="force")
                elif cmd == "do":
                    yield from self._factory(arg)()
                elif cmd == "pose":
                    m.set_pose(arg[0])
                    yield from m.wait(arg[1])
                elif cmd == "fx":
                    m.fx(arg, at="head", follow=True, loops=1)
                elif cmd == "sound":
                    m.sfx.play(arg, 1.0, 0.0, force=True)
                elif cmd == "emote":
                    m.emote(arg, 1.4)
                elif cmd == "wait":
                    yield from m.wait(arg)
        finally:
            m.clear_pose()

    def a_party(self):
        m = self.m
        m.say("It's a PARTY!", 2.0, voice=self._vm())
        m.fx("confetti", at="head", offset=(0, -60 * SCALE))
        m.fx("music_notes", at="head", follow=True, loops=3)
        self._sfx("tada", 0.9)
        m.set_pose("dance")
        yield from m.wait(1.4)
        yield from m.jump(0, -820, flip=1)
        m.set_pose("jack")
        yield from m.wait(1.6)
        m.fx("confetti", at="head", offset=(0, -60 * SCALE))
        m.set_pose("victory")
        yield from m.wait(1.2)

    def a_superhero(self):
        m, b = self.m, self.m.body
        m.say("Up, up and away!", 1.6, voice=self._vm())
        d = 1 if b.x < m.W / 2 else -1
        yield from m.jump(d * 420, -1150)
        m.fx("sparkle", at="feet", loops=2)
        m.set_pose("victory")
        yield from self.say_wait("Justice is served!", voice=self._vm())

    def a_magic(self):
        m = self.m
        yield from self.say_wait("Behold... real magic!", voice=self._vm(), extra=0)
        m.set_pose("wand")
        m.fx("sparkle", at="head", offset=(30 * SCALE, -10), loops=2)
        yield from m.wait(1.0)
        self._sfx("tada", 0.8)
        m.fx("confetti", at="head", offset=(0, -60 * SCALE))
        m.set_pose("wave")
        yield from self.say_wait("Ta-da!", voice=self._vm())

    def a_joke(self):
        m = self.m
        setup, punch = random.choice(JOKES)
        m.set_pose("talk")
        yield from self.say_wait(setup, voice=self._vm())
        self._sfx("drumroll", 0.7)
        yield from m.wait(2.0)  # wait for the longer snare roll to end
        m.emote("!", 0.8)
        yield from self.say_wait(punch, voice=self._vm())
        self._sfx("rimshot", 0.9)
        yield from m.wait(0.5)
        self._sfx("laugh", 1.0)  # little giggle after the punchline
        m.fx("sparkle", at="head", follow=True, loops=1)
        m.set_pose("victory")
        yield from m.wait(2.2)

    def a_code(self):
        """Pretend to type code for a quick demo; does NOT edit real files."""
        m = self.m
        yield from self.say_wait("Let me write a little code!", voice=self._vm())
        m.set_pose("tinker")
        yield from m.wait(2.0)
        self._sfx("ding", 0.7)
        yield from self.say_wait("Compiled! Zero bugs. Obviously.", voice=self._vm())
        self._sfx("laugh", 0.9)
        m.set_pose("victory")
        yield from m.wait(1.1)

    def a_karate(self):
        m, b = self.m, self.m.body
        m.say("HIYAH!", 1.6, voice=self._vm())
        m.set_pose("stance")
        yield from m.wait(0.4)
        for kind in ("punch", "kick", "punch", "kick"):
            m.aim_point = (b.x + b.facing * 70 * SCALE, b.y - 40 * SCALE)
            yield from m.strike(kind)
        m.aim_point = None
        m.set_pose("victory")
        yield from m.wait(1.1)

    def a_vanish(self):
        """Fades out in a puff, reappears somewhere else."""
        m, b = self.m, self.m.body
        try:
            m.say("Now you see me...", 1.4, voice=self._vm())
            m.fx("poof", at="feet")
            while m.opacity > 0.0:
                m.opacity = max(0.0, m.opacity - 3.0 * m.dt)
                yield
            x1, x2 = m.support_range()
            lo, hi = max(x1 + 60, 60), min(x2 - 60, m.W - 60)
            b.x = random.uniform(lo, hi) if lo < hi else b.x
            yield from m.wait(0.5)
            m.fx("poof", at="feet")
            while m.opacity < 1.0:
                m.opacity = min(1.0, m.opacity + 3.0 * m.dt)
                yield
            m.emote("!", 1.0)
            yield from self.say_wait("...now you don't!", voice=self._vm())
        finally:
            m.opacity = 1.0

    def _resize(self, target, seconds=0.7):
        m = self.m
        start, t0 = m.body_scale, m.t
        while m.t - t0 < seconds:
            k = (m.t - t0) / seconds
            m.body_scale = start + (target - start) * (k * k * (3 - 2 * k))      # smooth ease
            yield
        m.body_scale = target

    def a_giant(self):
        m = self.m
        try:
            m.say("I'M HUGE!", 2.0, voice=self._vm())
            yield from self._resize(2.1)
            m.fx("poof", at="feet")
            m.set_pose("victory")
            yield from m.wait(1.3)
            d, end = (1 if m.body.x < m.W / 2 else -1), m.t + 3.2        # a short stomp across the screen
            m.clear_pose()
            while m.t < end:
                m.body.facing, m.body.desired_vx = d, d * 110
                yield
            m.body.desired_vx = 0
            yield from self._resize(1.0)
        finally:
            m.body_scale = 1.0

    def a_tiny(self):
        m = self.m
        try:
            m.say("I'm tiny!", 2.0, voice=self._vm())
            yield from self._resize(0.45)
            yield from self.a_zoom()
            yield from self._resize(1.0)
        finally:
            m.body_scale = 1.0

    def a_meditate(self):
        m = self.m
        m.say("Ommmmm...", 2.4, voice=self._vm())
        m.set_pose("meditate")
        m.fx("sparkle", at="head", follow=True, loops=2)
        yield from m.wait(random.uniform(4.0, 6.0))

    def a_compliment(self):
        m = self.m
        m.face_cursor()
        m.set_pose("wave")
        yield from self.say_wait(random.choice(COMPLIMENTS), voice=self._vm())
        self._sfx("aww", 0.8)

    def a_roast(self):
        m = self.m
        m.set_pose("taunt")
        pool = ROASTS.get(self.window_kind) or ROASTS["other"]
        yield from self.say_wait(random.choice(pool), voice=self._vm())
        self._sfx("rimshot", 0.6)
        yield from m.wait(0.6)

    def a_clock(self):
        m = self.m
        now = datetime.datetime.now()
        mins = int((time.time() - self.started) / 60)
        up = f"We've been hanging out for {mins} minute{'s' if mins != 1 else ''}." if mins >= 1 else "We just got started."
        m.set_pose("thinking")
        yield from self.say_wait(f"It's {now.strftime('%I:%M %p').lstrip('0')}. {up}", voice=self._vm())

    def a_wave(self):
        self.m.set_pose("wave")
        yield from self.m.wait(1.8)

    def a_cheer(self):
        m = self.m
        m.set_pose("victory")
        m.fx("sparkle", at="head", follow=True, loops=2)
        yield from m.wait(1.6)

    def a_look(self):
        m = self.m
        m.set_pose("look")
        yield from m.wait(1.2)
        m.body.facing *= -1
        yield from m.wait(1.5)

    def a_dance(self):
        self.m.set_pose("dance")
        self.m.emote("♪", 2.5)
        yield from self.m.wait(random.uniform(2.5, 4))

    def a_think(self):
        self.m.set_pose("thinking")
        self.m.emote("?", 1.5)
        yield from self.m.wait(2)

    def a_zoom(self):                           # zoomies!
        m = self.m
        x1, x2 = m.support_range()
        for _ in range(3):
            x = random.uniform(max(x1 + 40, 40), min(x2 - 40, m.W - 40)) if x2 - x1 > 200 else (x1 + x2) / 2
            yield from m.walk_to(x, speed=430)
        yield from m.wait(0.4)

    def a_hop_window(self):
        m, b = self.m, self.m.body
        cands = [p for p in m.platforms if p[0] != "floor" and abs(b.y - p[3]) <= 360
                 and p[2] - p[1] > 140 and (b.support is None or p[0] != b.support[0])]
        if not cands:
            yield from self.a_wander()
            return
        p = random.choice(cands)
        x1, x2 = m.support_range()
        take = min(max((p[1] + p[2]) / 2, x1 + 30), x2 - 30)
        yield from m.walk_to(take)
        lo, hi = max(p[1] + 40, take - 450), min(p[2] - 40, take + 450)
        if lo > hi:
            return
        yield from m.hop_to(random.uniform(lo, hi), p[3], flip=random.choice([0, 0, 1]))
        m.emote("!", 0.8)
        yield from m.wait(1.0)

    def a_perch(self):                          # "watch mode": chill in the corner
        m, b = self.m, self.m.body
        if abs(b.x - m.home_x) > 8:
            if b.support and b.support[0] != "floor":
                yield from m.hop_to(min(max(m.home_x, b.x - 450), b.x + 450), m.floor_y)
            else:
                yield from m.walk_to(m.home_x)
        else:
            b.facing = -1
            m.set_pose("sit")
            yield from m.wait(random.uniform(20, 40))

    # ---------------------------------------------------------------- music
    def a_groove(self):
        m = self.m
        demo = self.explicit and not self.music_on                    # asked from the panel with no music: dance anyway
        end, next_note = m.t + (random.uniform(6, 9) if demo else random.uniform(12, 25)), 0.0
        m.set_pose(self.song_style)
        while m.t < end and (self.music_on or demo):
            if m.t >= next_note:
                m.fx("music_notes", at="head", follow=True)
                next_note = m.t + 1.6
            if m.body.on_ground and random.random() < 0.1 * m.dt:      # to-the-beat flourish
                yield from m.jump(0, -640, flip=1)
                m.set_pose(self.song_style)
            yield
        if not self.music_on and not demo:
            self.line("music_stop", 0.6)

    def a_prank_pause(self):
        self.set_cd("prank_media", random.uniform(150, 260))
        self.m.request_routine(routines.pause_prank(self.m, self.actions))
        yield

    def a_skip_song(self):
        self.set_cd("skip", random.uniform(240, 400))
        self.m.request_routine(routines.skip_song(self.m, self.actions))
        yield

    def a_tab_peek(self):
        self.set_cd("tab", random.uniform(300, 480))
        fg = self.m.foreground_provider()
        if fg:
            self.m.request_routine(routines.tab_peek(self.m, fg, self.actions))
        yield

    # ---------------------------------------------------------------- reactive behaviours
    def a_curious(self):
        m, b = self.m, self.m.body
        self.set_cd("curious", 25)
        m.emote("?", 1.0)
        self.line("curious")
        prank = random.random() < 0.4
        if prank:
            m.fx("lightbulb", at="head", follow=True, duration=1.0, loops=0)
        t0 = m.t
        while abs(m.cursor[0] - b.x) > (REACH + 12 if prank else 170) and m.t - t0 < 9:
            m.face_cursor()
            m.set_pose("sneak")
            b.desired_vx = b.facing * 70
            yield
        b.desired_vx = 0
        if prank:
            m.face_cursor()
            self.line("prank", 1.0)
            yield from m.strike("punch")
            m.emote("heh", 0.8)
            away = -b.facing
            t0 = m.t
            while m.t - t0 < 1.3:
                b.facing, b.desired_vx = away, away * 400
                m.clear_pose()
                yield
            b.desired_vx = 0
        else:
            m.face_cursor()
            m.set_pose("look")
            yield from m.wait(3)

    def a_flee(self):
        m, b = self.m, self.m.body
        m.emote("!", 0.9)
        self.line("flee")
        t0, last_leap = m.t, -9.0
        while m.t - t0 < 14:
            d = m.cursor_dist()
            if self.fear < 0.22 and d > 340:
                break
            away = 1 if b.x >= m.cursor[0] else -1
            at_wall = (b.x < 110 and away < 0) or (b.x > m.W - 110 and away > 0)
            if at_wall and d < 260 and b.on_ground and m.t - last_leap > 1.5:
                last_leap = m.t                       # leap OVER the cursor
                self.line("cornered", 0.6)
                yield from m.jump(-away * 560, -840, flip=1)
                continue
            if b.on_ground and random.random() < 0.7 * m.dt:
                for p in m.platforms:                 # escape onto a window if one is near
                    if p[0] != "floor" and 40 < b.y - p[3] < 330 and p[1] - 250 < b.x < p[2] + 250 \
                            and (b.support is None or p[0] != b.support[0]):
                        tx = min(max(b.x + away * 150, p[1] + 30), p[2] - 30)
                        yield from m.hop_to(tx, p[3])
                        break
            b.facing, b.desired_vx = away, away * 400
            m.set_pose("flee")
            yield
        b.desired_vx = 0
        self.line("tired", 0.7)
        m.set_pose("tired")
        m.fx("dizzy", at="head", follow=True, loops=0, duration=1.8)
        yield from m.wait(1.8)

    def a_fight(self):
        m, b = self.m, self.m.body
        self.set_cd("fight", 12)
        m.emote("!!", 1.0)
        self.line("fight", 1.0)
        m.face_cursor()
        m.set_pose("stance")
        yield from m.wait(0.3)
        end, last_dodge, hits = m.t + random.uniform(6, 10), -9.0, 0
        while m.t < end:
            d = m.cursor_dist()
            if d > 420:
                break
            m.face_cursor()
            cx, cy = m.cursor
            dx = cx - b.x
            closing = -(m.cursor_vel[0] * sign(dx))
            if closing > 1000 and d < 170 and m.t - last_dodge > 1.2 and b.on_ground:
                last_dodge = m.t
                m.emote("!", 0.5)
                yield from m.jump(-sign(dx) * 360, -780, flip=-1)   # back flip!
                m.set_pose("stance")
                continue
            if cy < b.y - 150 * SCALE and abs(dx) < 120 and b.on_ground:   # cursor way above: hop at it
                yield from m.jump(0, -760)
                m.set_pose("stance")
                continue
            if abs(dx) > REACH + 4:
                b.desired_vx = sign(dx) * 330
                m.clear_pose()
                yield
                continue
            b.desired_vx = 0
            r = random.random()
            if r < 0.14:
                self.line("taunt", 0.8)
                m.set_pose("taunt")
                yield from m.wait(0.9)
            else:
                yield from m.strike("punch" if r < 0.68 else "kick")
                hits += 1
            m.set_pose("stance")
            yield from m.wait(random.uniform(0.2, 0.5))
        b.desired_vx = 0
        self.fear, self.courage = 0.2, 0.2
        if hits >= 3 and random.random() < 0.65:
            self.line("victory", 1.0)
            m.set_pose("victory")
            m.fx("confetti", at="head", offset=(0, -60 * SCALE))
            m.fx("sparkle", at="head", follow=True, loops=2)
            yield from m.jump(0, -620)
            m.set_pose("victory")
            yield from m.jump(0, -620)
            m.set_pose("victory")
            yield from m.wait(1.0)
        else:
            self.line("tired", 1.0)
            m.set_pose("tired")
            m.fx("dizzy", at="head", follow=True, loops=0, duration=2.2)
            yield from m.wait(2.2)
