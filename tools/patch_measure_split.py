# -*- coding: utf-8 -*-
"""Split by what the clock says, not by what I guessed the voice would do.

The splitter I added did not fire. The documentary failed again with exactly
the same number:

    "longest_uninterrupted_static_s": 11.2
    !! SLIDESHOW CHECK FAILED - not rendering

I had estimated the narration rate at 2.6 words a second and split anything
over 26 words. The shot that overran was under that and still took 11.2
seconds, so the real rate is nearer 2.3 - and any estimate would have the same
class of failure eventually.

There is no need to estimate. The code already measures every shot: it runs
the text through TTS and reads the duration off the resulting wav. So the
split now happens after that measurement, on shots that are actually too long,
and only those halves are re-narrated. Exact instead of approximate, at the
cost of one extra TTS call per offending shot.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/longform/docgen2.py",
         "autopilot_fun/longform/docgen2.py",
         "autopilot_history/longform/docgen2.py"]

OLD = '''    shots = split_long_shots(doc["shots"])

    print("== narrating %d shots ==" % len(shots), flush=True)
    for i, s in enumerate(shots):
        tts(s["say"], os.path.join(WORK, "sc%d.mp3" % i))
        run(["ffmpeg", "-y", "-i", "sc%d.mp3" % i, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
             "-ar", "48000", "-ac", "2", "sc%d.wav" % i])
        s["_dur"] = round(dur("sc%d.wav" % i) + 0.3, 2)
'''

NEW = '''    shots = doc["shots"]

    def narrate(all_shots):
        for i, s in enumerate(all_shots):
            tts(s["say"], os.path.join(WORK, "sc%d.mp3" % i))
            run(["ffmpeg", "-y", "-i", "sc%d.mp3" % i, "-af",
                 "loudnorm=I=-16:TP=-1.5:LRA=11",
                 "-ar", "48000", "-ac", "2", "sc%d.wav" % i])
            s["_dur"] = round(dur("sc%d.wav" % i) + 0.3, 2)

    print("== narrating %d shots ==" % len(shots), flush=True)
    narrate(shots)

    # Now that every shot has a measured duration, split the ones that are
    # genuinely too long and narrate again. Estimating the speaking rate from
    # word counts got this wrong: the shot that failed twice was under the
    # word threshold and still ran 11.2 seconds.
    split = split_long_shots(shots)
    if len(split) != len(shots):
        print("== re-narrating %d shots after splitting ==" % len(split), flush=True)
        shots = split
        narrate(shots)
'''

FUNC_OLD_START = "def split_long_shots(shots):"
FUNC_NEW = '''def split_long_shots(shots):
    """Split any shot the clock says holds one image too long.

    Called after narration, so s["_dur"] is the measured length of the audio
    rather than a guess from the word count. The check refuses anything over
    eleven seconds; splitting at ten leaves room for the 0.3s tail.
    """
    out = []
    for s in shots:
        if s.get("_dur", 0) <= MAX_SHOT_SECONDS:
            out.append(s)
            continue
        say = (s.get("say") or "").strip()

        # Split at the sentence boundary nearest the middle, so both halves are
        # whole sentences and the voice does not stop mid-thought.
        parts, buf = [], ""
        for ch in say:
            buf += ch
            if ch in ".!?":
                parts.append(buf.strip())
                buf = ""
        if buf.strip():
            parts.append(buf.strip())
        if len(parts) < 2:
            # Nothing to split on. Leave it and let the check refuse it - a
            # single unbroken sentence that long is a board problem, not a
            # rendering one.
            print("  shot runs %.1fs and has no sentence break to split on"
                  % s.get("_dur", 0), flush=True)
            out.append(s)
            continue

        words = len(say.split())
        target = words / 2.0
        best, running, closest = 1, 0, None
        for i, p in enumerate(parts[:-1]):
            running += len(p.split())
            if closest is None or abs(running - target) < closest:
                closest, best = abs(running - target), i + 1

        first = dict(s)
        first["say"] = " ".join(parts[:best])
        second = dict(s)
        second["say"] = " ".join(parts[best:])
        first.pop("_dur", None)
        second.pop("_dur", None)
        # A different visual on the second half, otherwise it is still one
        # image held too long and nothing has been solved.
        if second.get("type") == "cinematic":
            second["type"] = "textcard"
        print("  split a %.1fs shot into %d + %d words"
              % (s.get("_dur", 0), len(first["say"].split()),
                 len(second["say"].split())), flush=True)
        out.append(first)
        out.append(second)
    return out'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def narrate(all_shots)" in s:
        print("  already patched: %s" % rel)
        return
    if s.count(OLD) != 1:
        raise SystemExit("%s: narration block found %d times" % (rel, s.count(OLD)))
    s = s.replace(OLD, NEW)

    i = s.index(FUNC_OLD_START)
    j = s.index("\n\n\n", i)
    s = s[:i] + FUNC_NEW + s[j:]

    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
