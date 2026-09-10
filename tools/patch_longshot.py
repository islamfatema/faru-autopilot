# -*- coding: utf-8 -*-
"""Split the long shot instead of throwing the documentary away.

FaRu's documentary run on 9 September ended:

    !! SLIDESHOW CHECK FAILED - not rendering:
    - a static shot runs 11.2s (>11s)

The check is right. Eleven seconds on one still image is a slideshow, and
slideshows are what made these films unwatchable. But the response was to
abandon a finished twelve-minute script over two tenths of a second on one
shot, and no documentary published that day at all.

A shot is long because its narration is long, so the fix belongs before the
narration is spoken, not after. Any shot whose text would run past ten seconds
is split in two at a sentence boundary. Two shots, two images, two camera
moves, the same words - and the check passes honestly rather than being
loosened.

If a shot has no sentence boundary to split on it is left alone and the check
still refuses it, which is correct: that is a genuinely unrenderable shot and
the board should be rewritten.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/longform/docgen2.py",
         "autopilot_fun/longform/docgen2.py",
         "autopilot_history/longform/docgen2.py"]

FUNC = '''
# Roughly the narration rate these voices actually produce, measured against
# the shot durations in the logs: about 2.6 words a second plus the 0.3s tail.
WORDS_PER_SECOND = 2.6
MAX_SHOT_SECONDS = 10.0


def split_long_shots(shots):
    """One image held past eleven seconds is a slideshow; split it in two.

    The alternative, which is what happened before, is that the whole film is
    abandoned because one shot overran by two tenths of a second.
    """
    out = []
    for s in shots:
        say = (s.get("say") or "").strip()
        words = len(say.split())
        if words <= MAX_SHOT_SECONDS * WORDS_PER_SECOND:
            out.append(s)
            continue

        # Split at the sentence boundary nearest the middle, so both halves are
        # whole sentences and the voice does not stop mid-thought.
        parts, buf = [], ""
        for ch in say:
            buf += ch
            if ch in ".!?" :
                parts.append(buf.strip())
                buf = ""
        if buf.strip():
            parts.append(buf.strip())
        if len(parts) < 2:
            # Nothing to split on. Leave it and let the check refuse it - a
            # single unbroken sentence that long is a board problem, not a
            # rendering one.
            out.append(s)
            continue

        best, target = 1, words / 2.0
        running = 0
        for i, p in enumerate(parts[:-1]):
            running += len(p.split())
            if abs(running - target) < abs(
                    sum(len(x.split()) for x in parts[:best]) - target):
                best = i + 1

        first = dict(s)
        first["say"] = " ".join(parts[:best])
        second = dict(s)
        second["say"] = " ".join(parts[best:])
        # A different visual on the second half, otherwise it is still one
        # image held for eleven seconds and nothing has been solved.
        if second.get("type") == "cinematic":
            second["type"] = "textcard" if s.get("line") or s.get("say") else "document"
        print("split a %d-word shot into %d + %d words"
              % (words, len(first["say"].split()), len(second["say"].split())),
              flush=True)
        out.append(first)
        out.append(second)
    return out


'''

OLD = '''    shots = doc["shots"]

    print("== narrating %d shots ==" % len(shots), flush=True)'''
NEW = '''    shots = split_long_shots(doc["shots"])

    print("== narrating %d shots ==" % len(shots), flush=True)'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def split_long_shots" in s:
        print("  already patched: %s" % rel)
        return
    if s.count(OLD) != 1:
        raise SystemExit("%s: anchor found %d times" % (rel, s.count(OLD)))
    s = s.replace(OLD, NEW)
    s = s.replace("# ---------------- storyboard analyzer ----------------",
                  FUNC.strip("\n") + "\n\n\n"
                  "# ---------------- storyboard analyzer ----------------", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
