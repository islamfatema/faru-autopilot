# -*- coding: utf-8 -*-
"""Make the ending earn a comment or a share instead of ending identically.

Two problems, both mine.

First, every video on a channel closes with one of five canned lines, appended
unconditionally. A viewer who watches three videos hears "Were you taught this
at school?" twice. Fatema flagged exactly this - "why i am seeing same post in
my channel again and again" - and the ending is a large part of why the videos
feel the same even when the facts differ. The generator is already required to
write an arguable closing question per script; the code threw it away and
appended a canned one on top. Now the canned line is only used when the script
did not bring its own.

Second, the canned lines only ever ask for a comment. Nothing has ever asked for
a share, and a share is worth far more - it is the one signal that puts a video
in front of people who do not follow the channel. The shapes that earn one are
not "share this": they name the person the viewer should send it to, and that
person has to be someone specific enough to picture.

The pools below are per channel, so a motivation video does not close like a
trivia video, and they are long enough that a viewer watching several in a row
does not hear a repeat.
"""
import ast
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Roughly a third of each pool asks to be sent to someone, because reach comes
# from shares and nothing here has ever asked for one.
POOLS = {
    "autopilot_us/main_us.py": [
        "Which one hit hardest?",
        "Comment the one you needed today.",
        "Say it back to yourself once.",
        "Send this to the friend who quit.",
        "Tell me what you are working on.",
        "Who told you this was too late?",
        "Send this to someone starting over.",
        "What did you stop for no reason?",
        "Name the thing you keep putting off.",
        "Send this to the one who needs it.",
        "Agree, or is that too simple?",
        "What would you do with one free hour?",
    ],
    "autopilot_fun/main_fun.py": [
        "Did you know this one?",
        "Tell me if this shocked you.",
        "Which one did you not believe?",
        "Comment a fact that beats this.",
        "Send this to someone who will argue.",
        "Knew it, or news to you?",
        "Send this to the know-it-all.",
        "Bet you tell someone this today.",
        "Which part did you have to look up?",
        "Send this to whoever taught you wrong.",
        "True or does that sound made up?",
        "What fact do you still not believe?",
    ],
    "autopilot_history/main_history.py": [
        "Were you taught this at school?",
        "Comment if this is new to you.",
        "What else were we never told?",
        "Did your history class skip this?",
        "Send this to your history teacher.",
        "Tell me what surprised you here.",
        "Send this to someone who loves history.",
        "Which part did they leave out for you?",
        "Send this to whoever taught you otherwise.",
        "Does this change how you see it?",
        "What else did the textbook get wrong?",
        "Name a story you were told wrong.",
    ],
}

OLD_APPEND = "    phrases = phrases + [ENDERS[idx % len(ENDERS)]]"

NEW_APPEND = '''    # Only add a closing line if the script did not write its own. The
    # generator is required to end on a question worth arguing with, and
    # appending a canned one on top of it made every video on the channel
    # finish the same way - which is a large part of why they felt repetitive
    # even when the facts were different.
    if not phrases[-1].rstrip().endswith("?"):
        phrases = phrases + [ENDERS[idx % len(ENDERS)]]'''


def patch(rel, pool):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()

    block = "ENDERS = [\n" + "".join('    "%s",\n' % p for p in pool) + "]"
    s, n = re.subn(r"ENDERS = \[\n(?:    \".*\",\n)+\]", lambda m: block, s, count=1)
    if n != 1:
        raise SystemExit("%s: ENDERS block not found" % rel)

    if s.count(OLD_APPEND) != 1:
        raise SystemExit("%s: append line found %d times" % (rel, s.count(OLD_APPEND)))
    s = s.replace(OLD_APPEND, NEW_APPEND)

    # Validate before writing anything. Opening in "w" truncates the file
    # before it validates its own arguments; that is how main_us.py became
    # zero bytes.
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("patched %s  (%d endings)" % (rel, len(pool)))


for rel, pool in POOLS.items():
    patch(rel, pool)
print("done")
