"""Data for the fun stuff (jokes, narration, roasts...) and the demo-script parser. No Qt in here."""

JOKES = [
    ("Why do programmers prefer dark mode?", "Because light attracts bugs!"),
    ("How many programmers does it take to change a light bulb?", "None. That's a hardware problem."),
    ("What is a hackathon?", "A place where sleep goes to die and coffee goes to work."),
    ("Why did the developer go broke?", "He used up all his cache."),
    ("I'd tell you a UDP joke...", "but you might not get it."),
    ("Why was the JavaScript developer sad?", "He didn't Node how to Express himself."),
    ("What did the stickman say at the hackathon?", "I'm just here for the free snacks!"),
    ("Why do Java developers wear glasses?", "Because they can't C sharp."),
    ("What's a programmer's favorite hangout?", "The Foo Bar."),
    ("Why did the AI cross the road?", "It was the optimal path according to the training data."),
    ("How do you comfort a JavaScript bug?", "You console it."),
    ("Why did the computer get cold?", "It left its Windows open."),
    ("What's my favorite type of music?", "Algo-rhythms."),
    ("Why was the stickman such a good dancer?", "He had no body to worry about!"),
    ("What do you call 8 hobbits?", "A hobbyte."),
    ("There are 10 kinds of people.", "Those who understand binary and those who don't."),
]

COMPLIMENTS = [
    "You have excellent taste in desktop pets.", "Your cursor movements are poetry.",
    "That's a really nice window you've got open there.", "You are doing great. Seriously.",
    "I bet you write beautiful code.", "Your productivity is inspiring. Mostly.",
    "You're the best human I've ever lived on a screen with.", "Wow, you're awesome at this. Keep going!",
]

ROASTS = {
    "code": ["Is that code, or modern art?", "Your code has more bugs than my sock drawer.",
             "Have you tried turning it off and on again? Asking for a friend."],
    "chat": ["Typing... stops typing... typing... Just send it!", "That's a lot of messages for someone 'busy'."],
    "game": ["Shouldn't you be working? ...Okay, one more round.", "Your aim is great. At the cursor. Of this app."],
    "docs": ["Is that a document, or a to-do list from 2019?", "Ctrl+S. Do it now. I'll wait."],
    "video": ["Another video? Productivity just left the chat.", "Is this research, or are we procrastinating?"],
    "shorts": ["Just one more short. You said that an hour ago.", "Your thumb is getting a workout."],
    "other": ["You have way too many tabs open.", "Your desktop is giving 'organized chaos'.",
              "I've seen better-looking taskbars. Not many."],
}

# one-liners he mutters as he starts a move (more of them the higher the chattiness level)
NARRATION = {
    "wander": ["Just stretching my legs.", "Nice day for a stroll.", "Where to next?"],
    "sit": ["Time for a little sit.", "Ahh, resting my pixels.", "Just taking five."],
    "look": ["What's going on over there?", "I spy with my little eye...", "Anything interesting?"],
    "dance": ["Feeling groovy!", "Watch these moves.", "Dance break!"],
    "zoom": ["ZOOMIES!", "Gotta go fast!", "I have the zoomies."],
    "think": ["Hmm, let me think.", "Pondering the universe.", "Interesting..."],
    "wave": ["Hi there!", "Hello, human!"],
    "cheer": ["Woohoo!", "Go team!"],
    "jacks": ["Time to work out!", "Fitness break!"],
    "shadowbox": ["Float like a stickman!", "I could've been a contender."],
    "parkour": ["Parkour time!", "Watch me fly.", "Look at me go!"],
    "moonwalk": ["Smooth, right?", "Hee-hee!"],
    "flip": ["Hup!", "Check this out!"],
    "hop_window": ["Ooh, a window!", "Let's go up there.", "I'm climbing!"],
    "tag": ["Tag, you're it!", "Wanna play a game?"],
    "follow": ["Wait for me!", "I'm coming with you."],
}

# who does what, for the control panel (only moves that really exist are shown)
MOVE_GROUPS = {
    "Show-off": ["party", "superhero", "magic", "karate", "vanish", "giant", "tiny", "parkour", "flip",
                 "jacks", "shadowbox", "moonwalk"],
    "Talk": ["joke", "code", "compliment", "roast", "clock", "think", "wave", "cheer"],
    "Everyday": ["wander", "sit", "look", "dance", "zoom", "hop_window", "perch", "meditate"],
    "Play": ["tag", "follow", "nap", "stretch", "pet"],
    "Music & browser": ["groove", "prank_pause", "skip_song", "tab_peek", "short_react"],
}
SHOWOFF = ["party", "superhero", "magic", "karate", "vanish", "giant", "tiny", "parkour", "flip", "jacks",
           "shadowbox", "moonwalk", "joke", "dance", "zoom", "cheer", "meditate", "compliment", "roast", "clock", "wave"]

SAY_PRESETS = [
    "Hi judges! I'm Stickman Buddy.", "Goodbye judges! Thanks for watching my demo!",
    "I live on your desktop and I'm powered by AI.",
    "Pick me up and throw me, I don't mind!", "Thank you for watching!", "Please vote for us!",
]

DEFAULT_SCRIPT = """# Stickman demo script. One command per line.
#   say <text>        speech bubble + voice, waits until he's done talking
#   do <move>         any move from the Moves tab (dance, karate, joke, party...)
#   pose <name> [s]   hold a pose for s seconds     fx <name>     sound <name>     emote <text>     wait <s>
say Hi judges! I'm Stickman Buddy, an AI that lives on your desktop.
do wave
say I can walk, jump and hang out on your windows.
do parkour
say I react to what you're doing, and I'm never boring.
do cheer
say I can even do karate!
do karate
say Want to hear a joke?
do joke
say And you can pick me up and throw me around.
pose dangle 2
do superhero
do party
say Thank you for watching!
do wave
"""

SCENES = {
    "Hi Judges": "say Hi judges! I'm Stickman Buddy. Nice to meet you!\ndo wave\n",
    "Goodbye Judges": "say Goodbye judges! Thank you for watching. See you next time!\ndo wave\nsound applause\n",
    "Coding moment": "do code\n",
    "Show reel": DEFAULT_SCRIPT,
    "Comedy hour": "say Welcome to comedy hour!\npose talk 1\ndo joke\ndo joke\ndo joke\nsound applause\nsay Thank you, I'll be here all week!\n",
    "Superpowers": "say Watch this.\ndo vanish\ndo giant\ndo tiny\ndo superhero\ndo magic\nsay Not bad, right?\n",
    "Fight scene": "say Who wants some?\ndo shadowbox\ndo karate\ndo flip\ndo karate\npose victory 2\nsay Too easy.\n",
}


def parse_script(text, moves, poses, fx, sounds):
    """-> (steps, errors). A step is (command, argument, line number). Nothing runs if there are errors."""
    steps, errors = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cmd, _, arg = line.partition(" ")
        cmd, arg = cmd.lower(), arg.strip()
        if cmd in ("say", "emote"):
            if not arg:
                errors.append(f"line {n}: '{cmd}' needs some text")
            else:
                steps.append((cmd, arg, n))
        elif cmd == "do":
            if arg in moves:
                steps.append((cmd, arg, n))
            else:
                errors.append(f"line {n}: unknown move '{arg}'")
        elif cmd == "pose":
            parts = arg.split()
            try:
                secs = float(parts[1]) if len(parts) > 1 else 2.0
            except ValueError:
                errors.append(f"line {n}: '{parts[1]}' isn't a number of seconds")
                continue
            if not parts or parts[0] not in poses:
                errors.append(f"line {n}: unknown pose '{parts[0] if parts else ''}'")
            elif not 0 < secs <= 30:
                errors.append(f"line {n}: seconds must be between 0 and 30")
            else:
                steps.append((cmd, (parts[0], secs), n))
        elif cmd == "fx":
            (steps if arg in fx else errors).append((cmd, arg, n) if arg in fx else f"line {n}: unknown effect '{arg}'")
        elif cmd == "sound":
            (steps if arg in sounds else errors).append((cmd, arg, n) if arg in sounds else f"line {n}: unknown sound '{arg}'")
        elif cmd == "wait":
            try:
                secs = float(arg)
            except ValueError:
                errors.append(f"line {n}: 'wait' needs a number of seconds")
                continue
            if 0 <= secs <= 60:
                steps.append((cmd, secs, n))
            else:
                errors.append(f"line {n}: wait must be between 0 and 60 seconds")
        else:
            errors.append(f"line {n}: unknown command '{cmd}' (use say, do, pose, fx, sound, emote, wait)")
    return steps, errors
