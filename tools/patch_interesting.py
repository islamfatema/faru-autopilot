# -*- coding: utf-8 -*-
"""Fix the two things that make these videos boring.

Fatema asked people what they thought of FaRu Fact. They said it is not
interesting, so they do not watch. That is the most useful feedback this
project has had, and reading the actual scripts says exactly why.

Here is a whole video, as the viewer hears it:

    Your nose distinguishes / a HUGE range of smells. / Smell wires directly /
    to memory and emotion. / That's why one scent / brings back a memory /
    instantly.

Twenty-four words. Ten seconds. And the title is "Your Nose Can Remember
50,000 Smells" - the number is never said. The video does not deliver the one
thing its title promised, and it is over before anything happens.

Two defects, both fixable mechanically.

ONE: BROKEN PROMISES. Measured across the banks, a fifth of the titles that
promise a number never say it:

    us        3 titles promise a number,  1 never says it   (33%)
    fun      22 titles promise a number,  4 never say it    (18%)
    history  54 titles promise a number, 11 never say it    (20%)

    Rome Had a Million People 2,000 Years Ago     - "2,000" never said
    The 2,500-Year-Old Origin of the Red Carpet   - "2,500" never said
    Why Marathons Are Exactly 26.2 Miles          - "26.2" never said

A title that promises and does not pay is the definition of disappointing, and
it is a one-line validation rule.

TWO: ONE BEAT. The script states a fact, explains the fact, stops. There is no
second turn, so there is nothing to be surprised by twice and nothing to argue
with. That is what "not interesting" means, and no amount of picking better
subjects fixes it - the good subjects were getting the same ten-second
treatment.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- validator
RULE = '''

def promises_kept(d):
    """A number in the title must be said in the video.

    "Your Nose Can Remember 50,000 Smells" never says fifty thousand. "Rome Had
    a Million People 2,000 Years Ago" never says two thousand. About a fifth of
    the numbered titles in the banks are like this, and a title that promises
    something the video does not deliver is the plainest way to make a viewer
    feel cheated.
    """
    title = re.sub(r"#\\w+", " ", d.get("title") or "")
    want = set(re.findall(r"\\d[\\d,\\.]*%?", title))
    if not want:
        return None
    body = " ".join(list(d.get("phrases") or []) + [d.get("narration") or ""])
    have = {n.replace(",", "").rstrip(".")
            for n in re.findall(r"\\d[\\d,\\.]*%?", body)}
    missing = [n for n in want if n.replace(",", "").rstrip(".") not in have]
    if missing:
        return "title promises %s and the video never says it" % ", ".join(missing)
    return None
'''

CALL_OLD = '''    for p in d["phrases"]:
        if not isinstance(p, str) or not p.strip():
            return "empty phrase"'''
CALL_NEW = '''    broken = promises_kept(d)
    if broken:
        return broken
    for p in d["phrases"]:
        if not isinstance(p, str) or not p.strip():
            return "empty phrase"'''

# ---------------------------------------------------------------- the shape
SECOND_TURN = """
THE REASON PEOPLE SAY THESE ARE BORING. Fatema asked viewers directly. Here is
a whole video as they hear it, and it is typical:

    Your nose distinguishes a HUGE range of smells. Smell wires directly to
    memory and emotion. That's why one scent brings back a memory instantly.

Twenty-four words. It states a fact, explains the fact, and stops. There is
nothing to be surprised by twice, nothing to disagree with, nothing to tell
anybody. Picking a better subject does not fix this - the good subjects were
getting the same ten-second treatment.

So every script needs a SECOND TURN. Structure it exactly like this:

  1-2   The belief the viewer holds. Straight in.
  3-5   The turn: that belief is wrong. Do not explain yet.
  6-8   WHY it is wrong, with the checkable number or date.
  9-11  THE SECOND TURN - and this is the part that has been missing. Now that
        they know it, what does it MEAN for them? What follows from it that
        they had not thought of? A consequence, a use, or a thing it explains
        about their own life.
  12-13 The close: one thing to try, then a question worth arguing with.

Beats 9-11 are the whole difference between a fact and a video. "Your stomach
rebuilds its lining every few days" is a fact. "Which is why the drugs that
block acid also slow that repair" is a video.

If the title contains a number, the captions MUST say that number out loud.
"""


def patch_validator():
    p = os.path.join(ROOT, "tools", "grow.py")
    s = io.open(p, encoding="utf-8").read()
    if "def promises_kept" in s:
        print("  validator already patched")
        return
    if s.count(CALL_OLD) != 1:
        raise SystemExit("grow.py: phrase loop found %d times" % s.count(CALL_OLD))
    s = s.replace(CALL_OLD, CALL_NEW)
    s = s.replace("def valid(d):", RULE.strip("\n") + "\n\n\ndef valid(d):", 1)
    write(p, s)


def patch_briefs():
    p = os.path.join(ROOT, "tools", "grow.py")
    s = io.open(p, encoding="utf-8").read()
    if "THE REASON PEOPLE SAY THESE ARE BORING" in s:
        print("  briefs already carry the second-turn rule")
        return
    for key in ("us", "fun", "history"):
        marker = '    "%s": {' % key
        i = s.index(marker)
        end = s.index("\n        ),\n", i)
        lit = "".join('\n            %s' % repr(line + "\n")
                      for line in SECOND_TURN.strip("\n").split("\n"))
        s = s[:i] + s[i:end] + lit + s[end:]
        # rebuild index positions after each insert
        s = s
    write(p, s)


def patch_expand_prompt():
    p = os.path.join(ROOT, "tools", "expand.py")
    s = io.open(p, encoding="utf-8").read()
    if "SECOND TURN" in s:
        print("  expand prompt already patched")
        return
    old = """- The last caption is a question worth arguing with. Not "what do you think"."""
    new = """- The last caption is a question worth arguing with. Not "what do you think".
- A SECOND TURN before the close. This is the part that is missing from every
  script you are given: they state a fact, explain it, and stop, which is why
  viewers say these are boring. After the explanation, say what it MEANS for
  the viewer - a consequence, a use, or something it explains about their own
  life that they had not connected. "Your stomach rebuilds its lining every few
  days" is a fact; "which is why the drugs that block acid also slow that
  repair" is a video.
- If the title contains a number, the captions MUST say that number out loud.
  A fifth of these titles promise a number the video never mentions."""
    if s.count(old) != 1:
        raise SystemExit("expand.py: shape rules found %d times" % s.count(old))
    write(p, s.replace(old, new))


def write(path, s):
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % os.path.basename(path))


patch_validator()
patch_briefs()
patch_expand_prompt()
print("done")
