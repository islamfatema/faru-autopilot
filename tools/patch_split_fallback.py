# -*- coding: utf-8 -*-
"""Split a long shot even when it is one unbroken sentence.

The flagship render failed on this: eight shots were single sentences of eleven
seconds with no full stop inside them, split_long_shots left them alone, and the
slideshow check - correctly - refused to render a film holding one picture for
11.3 seconds. A whole documentary was thrown away over a comma.

A sentence that long always has a seam: a comma, a semicolon, a colon, a dash.
Split there, at the seam nearest the middle, and only fall back to a plain word
count if there is not even that. The second half becomes a different visual the
same way it already does, so the picture changes when the voice does.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = ["autopilot_us", "autopilot_fun", "autopilot_history"]

OLD = '''        if len(parts) < 2:
            # Nothing to split on. Leave it and let the check refuse it - a
            # single unbroken sentence that long is a board problem, not a
            # rendering one.
            print("  shot runs %.1fs and has no sentence break to split on"
                  % s.get("_dur", 0), flush=True)
            out.append(s)
            continue'''

NEW = '''        if len(parts) < 2:
            # One unbroken sentence. It still has a seam - a comma, a colon, a
            # dash - and splitting there beats losing the whole render to the
            # slideshow check, which is what happened to the first flagship.
            parts, buf = [], ""
            for ch in say:
                buf += ch
                if ch in ",;:" or buf.endswith(" - "):
                    parts.append(buf.strip())
                    buf = ""
            if buf.strip():
                parts.append(buf.strip())
        if len(parts) < 2:
            # Not even a seam: cut at the middle word. Reads slightly abruptly,
            # which is a smaller cost than an eleven-second still.
            w = say.split()
            if len(w) >= 8:
                half = len(w) // 2
                parts = [" ".join(w[:half]), " ".join(w[half:])]
        if len(parts) < 2:
            print("  shot runs %.1fs and is too short to split"
                  % s.get("_dur", 0), flush=True)
            out.append(s)
            continue'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "It still has a seam" in s:
        print("  already patched: %s" % rel)
        return
    if s.count(OLD) != 1:
        raise SystemExit("%s: split fallback anchor found %d times" % (rel, s.count(OLD)))
    s = s.replace(OLD, NEW)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for ch in CHANNELS:
    patch(os.path.join(ch, "longform", "docgen2.py"))
print("done")
