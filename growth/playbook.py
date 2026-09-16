# -*- coding: utf-8 -*-
"""What works on this channel, and what has already been proved not to.

    python growth/playbook.py --key us

The diagnosis file says what happened to each video. This turns that into
patterns, because a channel does not grow by knowing that one video failed - it
grows by not making that kind of video again.

Every judged video is broken into attributes that production can actually
control:

    subject        its tags, which is the closest thing to a topic family
    title shape    does it name a number, does it address the viewer as "you",
                   is it a comparison ("older than"), a correction ("actually")
    length bucket  under 20s, 20-35s, 35-60s, long-form bands
    format         series episode or generated bank script
    hook shape     the first caption's grammar: claim, question, instruction
    hour           when it published, in UTC

For each attribute value with enough evidence, the win rate and the median
views, subs per thousand, comments and shares are recorded. Attributes that
beat the channel median go into `prefer`; attributes that lose go into `avoid`.
Nothing with fewer than three videos behind it is allowed to make a decision -
that is how noise becomes doctrine.

The file it writes, growth/playbook_<key>.json, is permanent memory: each run
keeps the previous conclusions under `history` so a pattern that stops working
is visible as a change rather than silently overwritten.
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import store  # noqa: E402

MIN_EVIDENCE = 3          # videos behind an attribute before it may decide anything
WINNERS = ("WINNER",)
LOSERS = ("WEAK_HOOK", "NO_DISTRIBUTION", "WEAK_SUBSCRIBE", "WEAK_COMMENTS",
          "WEAK_SHARES")


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def length_bucket(rec):
    s = rec.get("duration_s") or 0
    if not s:
        return None
    if s <= 20:
        return "<=20s"
    if s <= 35:
        return "21-35s"
    if s <= 60:
        return "36-60s"
    if s <= 180:
        return "61-180s"
    if s <= 600:
        return "long <10m"
    return "long >10m"


def title_shapes(title):
    """The shapes a title can have, as production can choose them."""
    t = (title or "").lower()
    out = []
    if re.search(r"\d", t):
        out.append("has_number")
    if re.search(r"\byou(r|rs)?\b", t):
        out.append("about_you")
    if " older than" in t or " before " in t or " than " in t:
        out.append("comparison")
    if "actually" in t or "really" in t or " not " in t or "isn't" in t or "doesn't" in t:
        out.append("correction")
    if t.strip().endswith("?") or t.startswith("what ") or t.startswith("why ") or t.startswith("how "):
        out.append("question")
    if "this " in t:
        out.append("this_thing")
    return out or ["plain"]


def attributes(rec, row):
    """Every controllable attribute of one video, as (kind, value) pairs."""
    out = []
    for tag in (rec.get("tags") or [])[:6]:
        out.append(("tag", tag))
    b = length_bucket(rec)
    if b:
        out.append(("length", b))
    for shape in title_shapes(rec.get("title")):
        out.append(("title", shape))
    ser = rec.get("series")
    out.append(("format", "series" if ser else "bank"))
    pub = rec.get("published") or ""
    if len(pub) >= 13:
        out.append(("hour_utc", pub[11:13]))
    return out


def summarise(rows):
    return {
        "n": len(rows),
        "wins": sum(1 for r in rows if r["verdict"] in WINNERS),
        "losses": sum(1 for r in rows if r["verdict"] in LOSERS),
        "views": median([r["m"]["views"] for r in rows]),
        "subs_per_1k": median([r["m"]["subs_per_1k"] for r in rows]),
        "comments_per_1k": median([r["m"]["comments_per_1k"] for r in rows]),
        "shares_per_1k": median([r["m"]["shares_per_1k"] for r in rows]),
        "avg_pct": median([r["m"]["avg_pct"] for r in rows]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=["fun", "us", "history"])
    a = ap.parse_args()

    dpath = os.path.join(store.DIR, "diagnosis_%s.json" % a.key)
    diag = json.load(io.open(dpath, encoding="utf-8"))
    data = store.load(a.key)

    judged = [r for r in diag["videos"] if r.get("judgeable")]
    if len(judged) < 6:
        print("only %d judged videos - not enough to learn from yet" % len(judged))
        return 0

    # group every judged video by each of its attributes
    groups = {}
    for r in judged:
        rec = data["videos"].get(r["id"]) or {}
        for kind, value in attributes(rec, r):
            groups.setdefault((kind, value), []).append(r)

    overall = summarise(judged)
    prefer, avoid, evidence = [], [], {}
    for (kind, value), rows in sorted(groups.items()):
        if len(rows) < MIN_EVIDENCE:
            continue
        s = summarise(rows)
        evidence["%s:%s" % (kind, value)] = s
        better_views = (s["views"] or 0) > 1.3 * (overall["views"] or 0)
        better_subs = (s["subs_per_1k"] or 0) > 1.3 * (overall["subs_per_1k"] or 0)
        worse_views = (overall["views"] or 0) and (s["views"] or 0) < 0.6 * overall["views"]
        loss_rate = s["losses"] / float(s["n"])
        if (better_views or better_subs) and loss_rate < 0.5:
            prefer.append({"kind": kind, "value": value, "n": s["n"],
                           "views": s["views"], "subs_per_1k": s["subs_per_1k"],
                           "why": "views %s vs %s median%s"
                                  % (s["views"], overall["views"],
                                     ", subs/1k %s vs %s" % (s["subs_per_1k"],
                                                             overall["subs_per_1k"])
                                     if better_subs else "")})
        elif worse_views and loss_rate >= 0.5:
            avoid.append({"kind": kind, "value": value, "n": s["n"],
                          "views": s["views"],
                          "why": "views %s vs %s median, %d of %d diagnosed as failures"
                                 % (s["views"], overall["views"], s["losses"], s["n"])})

    prefer.sort(key=lambda p: -(p["views"] or 0))
    avoid.sort(key=lambda p: (p["views"] or 0))

    # what the channel is failing at most often, which is what to work on
    fail_counts = {}
    for r in judged:
        if r["verdict"] in LOSERS:
            fail_counts[r["verdict"]] = fail_counts.get(r["verdict"], 0) + 1
    worst = sorted(fail_counts.items(), key=lambda kv: -kv[1])

    out_path = os.path.join(HERE, "playbook_%s.json" % a.key)
    try:
        previous = json.load(io.open(out_path, encoding="utf-8"))
    except Exception:
        previous = {}

    book = {
        "key": a.key,
        "channel": diag.get("channel"),
        "updated": date.today().isoformat(),
        "judged_videos": len(judged),
        "overall": overall,
        "biggest_problem": worst[0][0] if worst else None,
        "problem_counts": dict(worst),
        "recovery_mode": diag.get("recovery_mode"),
        "prefer": prefer[:14],
        "avoid": avoid[:14],
        "evidence": evidence,
        # permanent memory: the last ten conclusions, so a pattern that stops
        # working shows up as a change instead of vanishing
        "history": ([{k: previous.get(k) for k in
                      ("updated", "biggest_problem", "overall", "prefer", "avoid")}]
                    + (previous.get("history") or []))[:10] if previous else [],
    }
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(book, ensure_ascii=False, indent=1))

    print("%s: learned from %d judged videos" % (book["channel"], len(judged)), flush=True)
    print("  biggest problem: %s %s" % (book["biggest_problem"], dict(worst)), flush=True)
    for p in prefer[:6]:
        print("  PREFER %-10s %-22s %s" % (p["kind"], str(p["value"])[:22], p["why"][:60]), flush=True)
    for p in avoid[:6]:
        print("  AVOID  %-10s %-22s %s" % (p["kind"], str(p["value"])[:22], p["why"][:60]), flush=True)
    print("wrote growth/playbook_%s.json" % a.key, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
