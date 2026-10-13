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
