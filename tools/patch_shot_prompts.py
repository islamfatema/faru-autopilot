# -*- coding: utf-8 -*-
"""Shoot the written shot, not a random angle on top of it.

The first series dry-run showed both halves of this. _generated() appends one of
six camera angles to every prompt, which is right for a generated script that
only names its subject - but a series episode already says what is in frame
("macro, eye-level, crab in the lower half"), and adding "epic aerial view" to
that produced a murky black image of an unrecognisable shape. On top of that,
the opening frame came back so dark that nothing reads at thumbnail size, which
is the one frame the whole Short depends on: 76% of FaRu's viewers leave in the
first second.

So: written shots are generated without the extra angle, and the first shot of
every series episode carries a brightness clause. Nothing changes for the
generated bank, which still gets its angle variation.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

OLD_SIG = '''def _generated(i, base_prompt):
    """One AI image. Sequential by design - asking for several at once gets 429."""
    prompt = "%s, %s%s" % (base_prompt, SHOT_ANGLES[i % len(SHOT_ANGLES)], STYLE_SUFFIX)'''
NEW_SIG = '''def _generated(i, base_prompt, angle=True):
    """One AI image. Sequential by design - asking for several at once gets 429.

    angle=False for a prompt that already describes its own framing: a written
    shot list says "macro, eye-level" and appending "epic aerial view" to that
    gives an image of neither.
    """
    if angle:
        prompt = "%s, %s%s" % (base_prompt, SHOT_ANGLES[i % len(SHOT_ANGLES)], STYLE_SUFFIX)
    else:
        prompt = base_prompt + STYLE_SUFFIX'''

OLD_CALL = """    paths = []
    for i, p in enumerate(prompts[:MAX_IMAGES]):
        got = _generated(i, p)"""
NEW_CALL = '''    paths = []
    for i, p in enumerate(prompts[:MAX_IMAGES]):
        # The opening frame is the whole decision - 76% of viewers leave inside
        # the first second - and a moody, dark generation loses them before the
        # voice starts.
        got = _generated(i, p + (FIRST_FRAME if i == 0 else ""), angle=False)'''

CONST = '''FIRST_FRAME = (", bright high contrast lighting, the subject unmistakable at a "
               "glance, vivid, sharp")

'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "FIRST_FRAME" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_SIG, "_generated"), (OLD_CALL, "shot loop")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))
    s = s.replace(OLD_SIG, NEW_SIG).replace(OLD_CALL, NEW_CALL)
    s = s.replace("def get_shot_images(", CONST + "def get_shot_images(", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
