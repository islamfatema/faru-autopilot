# -*- coding: utf-8 -*-
"""The seven-day report, written from the API and nothing else.

Fatema asked for one number above all others: net subscribers, gained minus
lost. It sits at the top of every channel's block here, next to the two gates
YouTube actually measures monetisation against and the days-to-target at the
rate the last 28 days really ran at. Where a channel is going backwards the
report says so; it never estimates, and it never fills a gap with a guess.

Run by growth.yml after the daily collection, so analytics/week.md is always
the latest Monday-to-Monday picture.
"""
import io
import json
import os
import re
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = (("history", "History That Explains the World"),
            ("us", "Rise With Fate"),
            ("fun", "FaRu Fact"))
KEEP = ("CURRENT", "GAINED", "LOST", "NET", "subscribers ", "watch hours",
        "Shorts views", "at the last")


def _a(name):
    return os.path.join(ROOT, "analytics", name)


def card_net7(key):
    """The net subscriber change this week, as the scorecard measured it."""
    try:
        c = io.open(_a("scorecard_%s.md" % key), encoding="utf-8").read()
        m = re.search(r"NET    - LAST 7 DAYS\s+\+?(-?\d+)", c)
        return m.group(1) if m else "?"
    except Exception:
        return "?"


def main():
    today = datetime.date.today()
    cut = (today - datetime.timedelta(days=7)).isoformat()
    out = ["# The week to %s" % today.isoformat(), "",
           "Every number here is read from the YouTube Analytics API. "
           "Nothing is estimated.", ""]
    rows = []
    for key, name in CHANNELS:
        try:
            d = json.load(io.open(_a("videos_%s.json" % key), encoding="utf-8"))
        except Exception as e:
            out.append("%s: no data (%s)" % (name, str(e)[:60]))
            continue
        week = [v for v in d["videos"].values() if v["published"][:10] > cut]
        last = lambda v: (v.get("snapshots") or [{}])[-1]
        rows.append((name, key, d.get("subscribers", 0), week, last,
                     sum(last(v).get("views") or 0 for v in week),
                     sum(last(v).get("watch_minutes") or 0 for v in week)))
    # The target, and what it costs in views on each channel's own conversion.
    out += ["## The target: 100 new subscribers a week, per channel", "",
            "    %-11s %7s %9s %11s %14s"
            % ("channel", "subs", "this week", "subs per 1k", "views needed")]
    want_total = have_total = 0
    for name, key, subs, week, last, views, wmin in rows:
        vv = sg = 0
        try:
            allv = json.load(io.open(_a("videos_%s.json" % key),
                                     encoding="utf-8"))["videos"]
        except Exception:
            allv = {}
        for rec in allv.values():
            s = rec.get("snapshots") or []
            if not s:
                continue
            vv += s[-1].get("views") or 0
            sg += s[-1].get("subs_gained") or 0
        per1k = (1000.0 * sg / vv) if vv else 0.0
        need = int(100 / per1k * 1000) if per1k > 0.01 else 0
        want_total += need
        have_total += views
        got = card_net7(key)
        out.append("    %-11s %7d %9s %11.2f %14s"
                   % (name[:11], subs, got, per1k,
                      "{:,}".format(need) if need else "?"))
    out.append("")
    if want_total and have_total:
        out.append("    all three need about %s views a week; they made %s."
                   % ("{:,}".format(want_total), "{:,}".format(have_total)))
        out.append("    That is %.0f times away." % (want_total / have_total))
    out.append("")

    out += ["| channel | subs | published this week | views on them | watch hours |",
            "|---|---|---|---|---|"]
    for name, key, subs, week, last, views, wmin in rows:
        out.append("| %s | %d | %d | %d | %.1f |"
                   % (name, subs, len(week), views, wmin / 60.0))
    out.append("")
    for name, key, subs, week, last, views, wmin in rows:
        out += ["## %s" % name, ""]
        try:
            card = io.open(_a("scorecard_%s.md" % key), encoding="utf-8").read()
        except Exception:
            card = ""
        for line in card.splitlines():
            s = line.strip()
            if s.startswith(KEEP):
                out.append("    " + s)
        out.append("")
        if week:
            best = max(week, key=lambda v: last(v).get("views") or 0)
            worst = min(week, key=lambda v: last(v).get("views") or 0)
            for label, v in (("best", best), ("worst", worst)):
                L = last(v)
                out.append("    %-6s %5d views  %3ds watched  %s"
                           % (label, L.get("views") or 0, L.get("avd_s") or 0,
                              re.sub(r"#\w+", "", v["title"]).strip()[:54]))
        out.append("")
    io.open(_a("week.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print("wrote analytics/week.md  (%d channels)" % len(rows))


if __name__ == "__main__":
    sys.exit(main())
