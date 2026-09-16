# -*- coding: utf-8 -*-
"""Turn what was learned into what the machines actually do next.

    python growth/apply.py --key fun

A playbook nobody reads is a diary. This writes two things the running system
consumes on its next tick, with no human in the loop:

  analytics/weights_<key>.json     read by main_*.py when it orders the bank:
                                   tags the data prefers are played first, tags
                                   it has already lost with are played last, and
                                   the length band that wins is preferred.

  analytics/brief_<key>.md         pasted into the script and topic generators'
                                   prompts: this channel's current baseline, its
                                   biggest measured problem, what to do more of,
                                   what to stop making, and - when the channel is
                                   in recovery - an instruction to change the
                                   variable that is failing rather than produce
                                   more of the same.

Recovery mode is the part Fatema asked for by name: when the recent uploads are
doing materially worse than the channel's own earlier normal, the brief stops
asking for more of the same and asks for a small batch that changes the weakest
variable. Nothing stops publishing; what is published changes.
"""
import argparse
import io
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import store  # noqa: E402

FIX = {
    "WEAK_HOOK": ("Open on the strangest thing in the video. The first caption is "
                  "the claim itself - no set-up, no 'did you know', no naming the "
                  "subject before the surprise. If the first line could open any "
                  "video on this channel, it is wrong."),
    "NO_DISTRIBUTION": ("Pick subjects people are already searching for and put the "
                        "surprise in the title. A title that only makes sense after "
                        "watching is a title nobody clicks."),
    "WEAK_SUBSCRIBE": ("Every script ends by naming the next episode in the series "
                       "and what it is about. Keep the subject inside the family "
                       "this channel converts on."),
    "WEAK_COMMENTS": ("End on a question only this subject could ask, answerable "
                      "from the viewer's own life. Never 'comment below'."),
    "WEAK_SHARES": ("End by naming who to send it to - 'send this to whoever taught "
                    "you X' - or make the fact useful enough to forward."),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=["fun", "us", "history"])
    a = ap.parse_args()

    book_path = os.path.join(HERE, "playbook_%s.json" % a.key)
    if not os.path.exists(book_path):
        print("no playbook yet - nothing to apply")
        return 0
    book = json.load(io.open(book_path, encoding="utf-8"))
    diag_path = os.path.join(store.DIR, "diagnosis_%s.json" % a.key)
    diag = json.load(io.open(diag_path, encoding="utf-8")) if os.path.exists(diag_path) else {}

    prefer_tags = [p["value"] for p in book.get("prefer", []) if p["kind"] == "tag"]
    avoid_tags = [p["value"] for p in book.get("avoid", []) if p["kind"] == "tag"]
    prefer_titles = [p["value"] for p in book.get("prefer", []) if p["kind"] == "title"]
    prefer_length = [p["value"] for p in book.get("prefer", []) if p["kind"] == "length"]
    prefer_hours = [p["value"] for p in book.get("prefer", []) if p["kind"] == "hour_utc"]

    weights = {
        "key": a.key,
        "updated": date.today().isoformat(),
        "source": "growth/playbook_%s.json" % a.key,
        "prefer_tags": prefer_tags[:8],
        "avoid_tags": avoid_tags[:8],
        "prefer_title_shapes": prefer_titles[:5],
        "prefer_length": prefer_length[:2],
        "prefer_hours_utc": prefer_hours[:3],
        "recovery_mode": bool(book.get("recovery_mode")),
        "biggest_problem": book.get("biggest_problem"),
    }
    wpath = os.path.join(store.DIR, "weights_%s.json" % a.key)
    io.open(wpath, "w", encoding="utf-8", newline="\n").write(
        json.dumps(weights, ensure_ascii=False, indent=1))

    # ---- the brief the generators read
    o = book.get("overall") or {}
    base = (diag.get("baselines") or {}).get("short") or {}
    lines = []
    lines.append("# What the numbers say about %s" % (book.get("channel") or a.key))
    lines.append("")
    lines.append("Measured on %s from %d judged videos. These are this channel's "
                 "own numbers, not a target copied from somewhere else."
                 % (book.get("updated"), book.get("judged_videos") or 0))
    lines.append("")
    lines.append("    median views per Short      %s" % (base.get("views") or o.get("views")))
    lines.append("    median percent viewed       %s" % (base.get("avg_pct") or o.get("avg_pct")))
    lines.append("    median subscribers per 1k   %s" % (base.get("subs_per_1k") or o.get("subs_per_1k")))
    lines.append("    median comments per 1k      %s" % (base.get("comments_per_1k") or o.get("comments_per_1k")))
    lines.append("    median shares per 1k        %s" % (base.get("shares_per_1k") or o.get("shares_per_1k")))
    lines.append("")
    problem = book.get("biggest_problem")
    if problem and problem in FIX:
        lines.append("## The one thing to fix now: %s" % problem.replace("_", " ").lower())
        lines.append("")
        lines.append(FIX[problem])
        lines.append("")
    if prefer_tags or prefer_titles or prefer_length:
        lines.append("## More of this - it is beating the channel median")
        lines.append("")
        for p in book.get("prefer", [])[:8]:
            lines.append("- %s **%s** (%d videos): %s" % (p["kind"], p["value"], p["n"], p["why"]))
        lines.append("")
    if avoid_tags or book.get("avoid"):
        lines.append("## Stop making this - it has already been tested and lost")
        lines.append("")
        for p in book.get("avoid", [])[:8]:
            lines.append("- %s **%s** (%d videos): %s" % (p["kind"], p["value"], p["n"], p["why"]))
        lines.append("")
    if book.get("recovery_mode"):
        lines.append("## RECOVERY MODE")
        lines.append("")
        lines.append("Recent uploads are doing materially worse than this channel's own "
                     "earlier normal. Do not produce more of the same shape. Write the "
                     "next batch changing the weakest variable named above - a different "
                     "subject family, a different opening, a different length - and keep "
                     "the batch small enough to read the result within a week.")
        lines.append("")
    winners = [v for v in (diag.get("videos") or []) if v.get("verdict") == "WINNER"][:6]
    if winners:
        lines.append("## What won, and what to build from it")
        lines.append("")
        for w in winners:
            lines.append("- **%s** - %s" % (w["title"][:70], w["why"]))
        lines.append("")
        lines.append("Scale the principle, not the video: the same shape and length on a "
                     "new subject in the same family, and a long-form on the subject that won.")
        lines.append("")
    bpath = os.path.join(store.DIR, "brief_%s.md" % a.key)
    io.open(bpath, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    print("wrote analytics/weights_%s.json and analytics/brief_%s.md" % (a.key, a.key))
    print("  prefer tags: %s" % (", ".join(prefer_tags[:6]) or "-"))
    print("  avoid tags:  %s" % (", ".join(avoid_tags[:6]) or "-"))
    print("  recovery:    %s" % bool(book.get("recovery_mode")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
