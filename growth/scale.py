# -*- coding: utf-8 -*-
"""When something wins, make more of that - deliberately, not by copying it.

    python growth/scale.py --key history

The diagnosis file knows which videos beat the channel's own best fifth. Left
alone, that knowledge dies there: the bank keeps handing out whatever was next,
and a subject that just proved it works waits three hundred scripts for its
turn.

This turns each winner into three concrete openings, written into
analytics/opportunities_<key>.json and appended to the channel brief the
generators read:

  SIBLING     the same shape on a neighbouring subject - what a viewer who
              liked this one would want next, not the same video reworded
  LONG-FORM   the subject queued as a documentary, because a Short that wins is
              the cheapest possible test of a twelve-minute idea, and long-form
              is where the watch hours and the money are
  SERIES      if three winners share a subject family, that family is a series
              rather than three lucky uploads

Nothing here publishes anything. It writes the opportunities down where the
generator and the topic writer will read them on their next run, so the
decision is made by what won rather than by what happened to be next.
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import store  # noqa: E402

STOP = set(("the a an is are was were of in on to for and or not it its this that with "
            "you your has have had can could than then more most actually really just "
            "ago years year about into over under from what why how does do did").split())
TOPIC_BANK = {"fun": "autopilot_fun/longform/topics_fun.json",
              "us": "autopilot_us/longform/topics_us.json",
              "history": "autopilot_history/longform/topics_history.json"}


def subject_words(title):
    t = re.sub(r"#\w+", " ", title or "").lower()
    return [w for w in re.findall(r"[a-z]{3,}", t) if w not in STOP]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=["fun", "us", "history"])
    ap.add_argument("--max", type=int, default=6)
    a = ap.parse_args()

    dpath = os.path.join(store.DIR, "diagnosis_%s.json" % a.key)
    if not os.path.exists(dpath):
        print("no diagnosis yet")
        return 0
    diag = json.load(io.open(dpath, encoding="utf-8"))
    winners = [v for v in diag.get("videos") or []
               if v.get("verdict") == "WINNER" and v.get("kind") == "short"]
    winners.sort(key=lambda v: -(v["m"]["views"] or 0))
    winners = winners[:a.max]
    if not winners:
        print("%s: no winners in this window" % a.key)
        return 0

    # subject families across the winners: three winners sharing a word is a
    # series waiting to be named, not a coincidence
    families = {}
    for w in winners:
        for word in set(subject_words(w["title"])):
            families.setdefault(word, []).append(w["title"])
    repeated = {k: v for k, v in families.items() if len(v) >= 3}

    # which winner subjects are not already queued as documentaries
    topics = []
    tpath = os.path.join(ROOT, TOPIC_BANK[a.key])
    try:
        topics = json.load(io.open(tpath, encoding="utf-8"))
    except Exception:
        pass
    queued = " ".join((t.get("title") or "").lower() for t in topics)

    ops = []
    for w in winners:
        words = subject_words(w["title"])
        head = " ".join(words[:3])
        ops.append({
            "from_video": w["id"],
            "title": w["title"],
            "views": w["m"]["views"],
            "why_it_won": w["why"],
            "sibling": ("a second Short in the same shape on a neighbouring subject "
                        "to '%s' - what someone who watched this would want next, "
                        "not this one reworded" % head),
            "long_form": None if head and head in queued else
                         ("queue a documentary about %s - this Short is the cheapest "
                          "test a twelve-minute idea can get, and it passed" % head),
        })

    out = {
        "key": a.key, "channel": diag.get("channel"),
        "updated": date.today().isoformat(),
        "opportunities": ops,
        "series_candidates": [{"subject": k, "videos": v} for k, v in repeated.items()],
    }
    io.open(os.path.join(store.DIR, "opportunities_%s.json" % a.key), "w",
            encoding="utf-8", newline="\n").write(json.dumps(out, ensure_ascii=False, indent=1))

    # append to the brief the generators read, so the next batch is written
    # from what won rather than from what was next in the bank
    bpath = os.path.join(store.DIR, "brief_%s.md" % a.key)
    lines = ["", "## Build from these - they already beat this channel", ""]
    for o in ops:
        lines.append("- **%s** (%s views): %s" % (o["title"][:70], o["views"], o["why_it_won"]))
        lines.append("  - %s" % o["sibling"])
        if o["long_form"]:
            lines.append("  - %s" % o["long_form"])
    if repeated:
        lines.append("")
        lines.append("Three or more winners share these subjects, which makes them a "
                     "series rather than luck: %s." % ", ".join(sorted(repeated)))
    lines.append("")
    with io.open(bpath, "a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    print("%s: %d winners turned into openings" % (diag.get("channel"), len(ops)))
    for o in ops:
        print("  %-52s %s views" % (o["title"][:52], o["views"]))
    if repeated:
        print("  series candidates: %s" % ", ".join(sorted(repeated)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
