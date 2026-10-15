# -*- coding: utf-8 -*-
"""Read the subscribe-placement test.

Every video records which half of the test it was in - the follow line one
caption before the end, or last as it has always been - and this reads those
assignments against what the channels measured.

It reports subscribers per thousand views, because that is what the test is
about, and views and retention beside it so a result that is really a
difference in reach is visible as one.

It says nothing until an arm has 15 videos and 1,500 views behind it. The
whole reason this experiment exists is that four explanations for History's
conversion spread were accepted on too little evidence and all four turned out
to be nothing; calling this one early would be the same mistake again.

    python tools/ab_report.py
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = (("history", "History That Explains the World"),
            ("us", "Rise With Fate"),
            ("fun", "FaRu Fact"))
MIN_VIDEOS = 15
MIN_VIEWS = 1500


def arms(key):
    try:
        return json.load(io.open(os.path.join(ROOT, "analytics",
                                              "ab_subscribe_%s.json" % key),
                                 encoding="utf-8"))
    except Exception:
        return {}


def measured(key):
    try:
        return json.load(io.open(os.path.join(ROOT, "analytics",
                                              "videos_%s.json" % key),
                                 encoding="utf-8"))["videos"]
    except Exception:
        return {}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = ["# The subscribe-placement test", "",
           "Half the videos ask one caption before the end, half ask last. "
           "Which half is decided by the rotation index, so the arms stay the "
           "same size and cannot drift.", ""]
    for key, name in CHANNELS:
        assigned = arms(key)
        vids = measured(key)
        out += ["## %s" % name, ""]
        if not assigned:
            out += ["    Nothing assigned yet - the test starts with the next "
                    "video this channel publishes.", ""]
            continue
        buckets = {"early": [0, 0, 0, 0], "end": [0, 0, 0, 0]}  # n, views, subs, pct
        for vid, row in assigned.items():
            v = vids.get(vid)
            if not v:
                continue
            snaps = v.get("snapshots") or []
            if not snaps:
                continue
            s = snaps[-1]
            b = buckets.get(row.get("arm"))
            if b is None:
                continue
            b[0] += 1
            b[1] += s.get("views") or 0
            b[2] += s.get("subs_gained") or 0
            b[3] += s.get("avg_pct") or 0
        for arm, label in (("early", "one caption before the end"),
                           ("end", "last, as before")):
            n, views, subs, pct = buckets[arm]
            if not n:
                out.append("    %-28s nothing measured yet" % label)
                continue
            out.append("    %-28s n=%3d  %6d views  %2d subs  %5.2f per 1k  "
                       "%4.0f%% watched"
                       % (label, n, views, subs,
                          1000.0 * subs / max(1, views), pct / n))
        a, b = buckets["early"], buckets["end"]
        ready = (min(a[0], b[0]) >= MIN_VIDEOS and min(a[1], b[1]) >= MIN_VIEWS)
        out.append("")
        if not ready:
            out.append("    Too early to read. Needs %d videos and %d views in "
                       "each half; has %d/%d videos and %d/%d views."
                       % (MIN_VIDEOS, MIN_VIEWS, a[0], b[0], a[1], b[1]))
        else:
            ra = 1000.0 * a[2] / max(1, a[1])
            rb = 1000.0 * b[2] / max(1, b[1])
            if rb and ra > rb * 1.25:
                out.append("    EARLY WINS - %.2f against %.2f subscribers per "
                           "thousand. Move the ask on this channel." % (ra, rb))
            elif ra and rb > ra * 1.25:
                out.append("    LAST WINS - %.2f against %.2f. Leave it where "
                           "it is." % (rb, ra))
            else:
                out.append("    NO DIFFERENCE - %.2f against %.2f. The ask is "
                           "not the constraint here; the next thing to question "
                           "is what is being offered, not where." % (ra, rb))
        out.append("")

    text = "\n".join(out) + "\n"
    io.open(os.path.join(ROOT, "analytics", "ab_subscribe.md"), "w",
            encoding="utf-8", newline="\n").write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
