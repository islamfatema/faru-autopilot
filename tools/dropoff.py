# -*- coding: utf-8 -*-
"""Where the documentary loses people, second by second.

The fan-funding gate needs 3,000 public long-form watch hours. The
documentaries retain 8-9%: a viewer watches about one minute of thirteen. Every
decision made about them so far - including shortening them to six minutes -
came from that single average, because the retention curve was never collected
for a long-form video. Not once, on any of the three channels.

It is now (growth/collect.py pulls one for every documentary each run), and
this reads it. The average says people leave. The curve says where, and the
answer decides what to fix:

  * a collapse inside the first 10% is the opening - the first fifteen seconds
    promise nothing, or the title promised something else
  * a steady slide with no cliff is pacing - it is simply not interesting
    enough to stay for, and no edit to one moment will fix it
  * a cliff at a particular point is that moment: an intro that outstays its
    welcome, a passage of stills, a tangent

Watch hours are views times minutes watched, so lifting the curve is worth
more than lifting views: at 8% retention a 13-minute film needs 180,000 views
for 3,000 hours, and at 40% it needs 36,000.

    python tools/dropoff.py
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = (("history", "History That Explains the World"),
            ("us", "Rise With Fate"),
            ("fun", "FaRu Fact"))
# Buckets of elapsed video time. The first is deliberately narrow: on a
# thirteen-minute film 10% is the first seventy-eight seconds, and that is
# where an eight percent average is decided.
BANDS = ((0.00, 0.10), (0.10, 0.25), (0.25, 0.50), (0.50, 0.75), (0.75, 1.00))


def curves(key):
    """(title, duration, [(elapsed ratio, watch ratio)]) for each long-form video."""
    p = os.path.join(ROOT, "analytics", "videos_%s.json" % key)
    try:
        vids = json.load(io.open(p, encoding="utf-8"))["videos"]
    except Exception:
        return []
    out = []
    for v in vids.values():
        if v.get("kind") == "short":
            continue
        for snap in reversed(v.get("snapshots") or []):
            c = snap.get("curve")
            if c:
                out.append((re.sub(r"#\w+", "", v["title"]).strip(),
                            v.get("duration_s") or 0,
                            [(float(a), float(b)) for a, b in c],
                            snap.get("views") or 0))
                break
    return out


def band_means(curve):
    """Mean audience-watch-ratio inside each band, or None where there is none."""
    out = []
    for lo, hi in BANDS:
        vals = [w for t, w in curve if lo <= t < hi]
        out.append(sum(vals) / len(vals) if vals else None)
    return out


def biggest_cliff(curve, duration):
    """(seconds, drop) at the steepest fall between two consecutive points."""
    pts = sorted(curve)
    worst = (None, 0.0)
    for (t1, w1), (t2, w2) in zip(pts, pts[1:]):
        drop = w1 - w2
        if drop > worst[1]:
            worst = (t2 * duration, drop)
    return worst


def verdict(bands, cliff_drop):
    start = bands[0]
    if start is not None and start < 0.55:
        return ("THE OPENING - under 55% are still there at a tenth of the way "
                "in. The first fifteen seconds promise nothing, or the title "
                "promised something else.")
    if cliff_drop >= 0.18:
        return ("A CLIFF - one moment loses nearly a fifth of the audience at "
                "once. Watch that second and cut what is there.")
    known = [b for b in bands if b is not None]
    if len(known) >= 2 and known[0] - known[-1] > 0.35:
        return ("A STEADY SLIDE with no single cliff - this is pacing, not one "
                "bad moment, and no edit to one passage will fix it.")
    return "No clear pattern yet - more videos need curves before this is worth reading."


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = ["# Where the documentaries lose people", "",
           "Read from the retention curves YouTube reports. Watch hours are "
           "views times minutes watched, so this is worth more than views: at "
           "8% retention a 13-minute film needs 180,000 views for 3,000 hours, "
           "at 40% it needs 36,000.", ""]
    any_data = False
    for key, name in CHANNELS:
        rows = curves(key)
        out += ["## %s" % name, ""]
        if not rows:
            out += ["    No curve collected yet. growth/collect.py pulls one "
                    "for every documentary from 15 October 2026; before that "
                    "it only ever took the newest few videos, which are always "
                    "Shorts.", ""]
            continue
        any_data = True
        out.append("    %-34s %5s  %s" % ("", "views", "  ".join(
            "%d-%d%%" % (a * 100, b * 100) for a, b in BANDS)))
        agg = [[] for _ in BANDS]
        worst_cliff = (0.0, None, None)
        for title, dur, curve, views in sorted(rows, key=lambda r: -r[3]):
            b = band_means(curve)
            for i, x in enumerate(b):
                if x is not None:
                    agg[i].append(x)
            secs, drop = biggest_cliff(curve, dur)
            if drop > worst_cliff[0]:
                worst_cliff = (drop, secs, title)
            out.append("    %-34s %5d  %s" % (
                title[:34], views,
                "  ".join(("%4.0f%%" % (x * 100)) if x is not None else "   - "
                          for x in b)))
        mean = [sum(a) / len(a) if a else None for a in agg]
        out += ["", "    %-34s %5s  %s" % ("AVERAGE", "", "  ".join(
            ("%4.0f%%" % (x * 100)) if x is not None else "   - " for x in mean))]
        if worst_cliff[1] is not None:
            out.append("    steepest single drop: %.0f%% at %ds into %r"
                       % (worst_cliff[0] * 100, worst_cliff[1], worst_cliff[2][:40]))
        out += ["", "    %s" % verdict(mean, worst_cliff[0]), ""]

    text = "\n".join(out) + "\n"
    io.open(os.path.join(ROOT, "analytics", "dropoff.md"), "w",
            encoding="utf-8", newline="\n").write(text)
    print(text)
    print("wrote analytics/dropoff.md%s" % ("" if any_data else
          "  (no curves yet - first ones arrive with tomorrow's collection)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
