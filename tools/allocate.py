# -*- coding: utf-8 -*-
"""Decide the daily slots from evidence, or say there is not enough.

The slots have moved three times in two weeks - to History, then to FaRu
Fact, then away from History again - and each time the ranking reversed
within days. Measured properly, at a matched video age so a four-day-old
video is not compared with a fortnight-old one:

    views at 4-7 days old      28 days    14 days
        History                   29         14
        Rise                      16         34
        FaRu Fact                 24         21

The two windows disagree about every channel, and the quartile spreads
overlap almost completely (History 11-114, Rise 7-39, FaRu 12-69). At this
sample size the three are not distinguishable, and every move I made was a
reaction to noise - which costs more than it sounds, because each move resets
what the next week's numbers mean.

So the rule, and it is deliberately hard to satisfy: a channel only gains
slots when it beats another on **both** windows, by at least half again, with
at least 20 videos behind each number. Otherwise the allocation holds and
this says so.

    python tools/allocate.py
"""
import datetime
import io
import json
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = (("history", "History", "autopost_history.yml"),
            ("us", "Rise", "autopost_us.yml"),
            ("fun", "FaRu Fact", "autopost_fun.yml"))
MIN_N = 20          # videos behind a number before it may decide anything
MARGIN = 1.5        # how much better one channel has to be to take a slot
AGE_LO, AGE_HI = 4, 7


def matched_age_views(key, since_days):
    """Views each video had at 4-7 days old - the only fair comparison.

    A video published yesterday and one published a fortnight ago have had
    different amounts of time to collect views, so comparing their totals, or
    even their views per day, flatters whichever is younger. This reads each
    video's snapshot from when it was the same age.
    """
    cut = (datetime.date.today() - datetime.timedelta(days=since_days)).isoformat()
    try:
        vids = json.load(io.open(os.path.join(ROOT, "analytics",
                                              "videos_%s.json" % key),
                                 encoding="utf-8"))["videos"]
    except Exception:
        return []
    out = []
    for v in vids.values():
        if v.get("kind") != "short":
            continue
        p = (v.get("published") or "")[:10]
        if not p or p < cut:
            continue
        for snap in (v.get("snapshots") or []):
            try:
                age = (datetime.date(*map(int, snap["date"].split("-")))
                       - datetime.date(*map(int, p.split("-")))).days
            except Exception:
                continue
            if AGE_LO <= age <= AGE_HI:
                out.append(snap.get("views") or 0)
                break
    return out


def slots(wf):
    try:
        return len(re.findall(r"^\s*- cron:", io.open(
            os.path.join(ROOT, ".github", "workflows", wf),
            encoding="utf-8").read(), re.M))
    except Exception:
        return 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = ["# What each channel's slots are worth", "",
           "Views each video had at %d-%d days old, so a video published "
           "yesterday is not compared with one published a fortnight ago."
           % (AGE_LO, AGE_HI), ""]
    data = {}
    out.append("    %-11s %6s %9s %9s %9s %9s"
               % ("channel", "slots", "28d med", "28d n", "14d med", "14d n"))
    for key, name, wf in CHANNELS:
        a = matched_age_views(key, 28)
        b = matched_age_views(key, 14)
        data[key] = (name, slots(wf),
                     st.median(a) if a else 0, len(a),
                     st.median(b) if b else 0, len(b))
        out.append("    %-11s %6d %9.0f %9d %9.0f %9d" % ((name,) + data[key][1:]))
    out.append("")

    # A channel is only clearly better if it wins on both windows, by the
    # margin, with enough videos behind each.
    verdicts = []
    keys = [k for k, _, _ in CHANNELS]
    for i in keys:
        for j in keys:
            if i == j:
                continue
            ni, _, m28i, n28i, m14i, n14i = data[i]
            nj, _, m28j, n28j, m14j, n14j = data[j]
            if min(n28i, n28j, n14i, n14j) < MIN_N:
                continue
            if m28i > MARGIN * m28j and m14i > MARGIN * m14j:
                verdicts.append("%s clearly beats %s on both windows" % (ni, nj))
    # How many a day each channel does best at. This is the finding that
    # matters most and it was invisible until 2 November: more uploads divide
    # a small channel's reach rather than adding to it. History took 905 views
    # a day at five Shorts and 164 at eight; FaRu Fact 384 at two and 96 at
    # six. Printed here so the next person to reach for "post more" sees it.
    window_from = (datetime.date.today() - datetime.timedelta(days=28)).isoformat()
    out += ["## What each channel does best at, by uploads a day",
            "", "    Published since %s, so every day compared is the same "
            "machine." % window_from, ""]
    out.append("    %-11s %-11s %7s %7s %10s" % ("channel", "a day", "days",
                                                "median", "that day"))
    for key, name, _wf in CHANNELS:
        try:
            vids = json.load(io.open(os.path.join(ROOT, "analytics",
                                                  "videos_%s.json" % key),
                                     encoding="utf-8"))["videos"]
        except Exception:
            continue
        byday = {}
        for v in vids.values():
            if v.get("kind") != "short":
                continue
            p2 = (v.get("published") or "")[:10]
            # 28 days. Over all history the only days with a low count are the
            # September ones when a gate had silenced the channels, so mixing
            # them in makes "fewer is better" look like "September was better".
            if not p2 or p2 < window_from:
                continue
            for snap in (v.get("snapshots") or []):
                try:
                    age = (datetime.date(*map(int, snap["date"].split("-")))
                           - datetime.date(*map(int, p2.split("-")))).days
                except Exception:
                    continue
                if AGE_LO <= age <= AGE_HI:
                    byday.setdefault(p2, []).append(snap.get("views") or 0)
                    break
        groups = {}
        for p2, l in byday.items():
            groups.setdefault(len(l), []).append(l)
        best, best_total = None, -1
        for n in sorted(groups):
            flat = [x for l in groups[n] for x in l]
            med = st.median(flat)
            # At least three days behind a count before it may be called best.
            # Rise's "6 a day" came from one single day, and recommending a
            # one-day reading is the exact mistake this tool exists to stop.
            if len(groups[n]) >= 3 and med * n > best_total:
                best, best_total = n, med * n
            out.append("    %-11s %-11d %7d %7.0f %10.0f"
                       % (name if n == min(groups) else "", n,
                          len(groups[n]), med, med * n))
        if best:
            now = slots(_wf)
            mark = "" if best == now else ("   <-- it has %d" % now)
            out.append("      -> best at %d a day, %d views for the day%s"
                       % (best, best_total, mark))
        else:
            out.append("      -> no count has three days behind it yet")
        out.append("")

    out.append("## Verdict")
    out.append("")
    if verdicts:
        for v in verdicts:
            out.append("    %s" % v)
        out.append("")
        out.append("    A slot may move. Move one, not three, and wait a week.")
    else:
        out.append("    No channel beats another on both windows by %gx with "
                   "%d videos behind each number." % (MARGIN, MIN_N))
        out.append("    HOLD. The allocation stays as it is.")
        out.append("")
        out.append("    The slots moved three times in two weeks and the "
                   "ranking reversed every time. Each move also resets what "
                   "the next week's numbers mean, so churning costs more than "
                   "leaving it alone.")
    out.append("")

    io.open(os.path.join(ROOT, "analytics", "allocation.md"), "w",
            encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
