# -*- coding: utf-8 -*-
"""The subscriber scorecard: gained, lost, and what caused each.

    python growth/subscribers.py --key history

Views were the number this project watched. They are the wrong one. A channel
that gains 20 subscribers and loses 25 is shrinking while its view count looks
fine, and until now nothing here measured the losing half at all.

This pulls, per channel, from the Analytics API:

    subscribersGained and subscribersLost      7 days and 28 days
    the same two per video                     so a video that costs
                                               subscribers can be named
    views, watch minutes, Shorts views         for the monetisation gaps

and writes analytics/subscribers_<key>.json plus a scorecard in
analytics/scorecard_<key>.md.

The monetisation arithmetic is YouTube's own, not an estimate: 1,000
subscribers, and then EITHER 4,000 public watch hours in 365 days OR 10 million
public Shorts views in 90 days. Both paths are reported, because these channels
are close to neither on the same axis.

Env: REFRESH_TOKEN (manage token), EXPECT_CHANNEL optional.
"""
import argparse
import io
import json
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import store  # noqa: E402
import yt     # noqa: E402

GOAL_SUBS = 1000
GOAL_WATCH_HOURS = 4000       # in 365 days, long-form path
GOAL_SHORTS_VIEWS = 10000000  # in 90 days, Shorts path


def window(days):
    end = date.today() - timedelta(days=1)
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def totals(tok, days, metrics):
    start, end = window(days)
    r = yt.report(tok, start, end, metrics)
    rows = yt.as_rows(r)
    return rows[0] if rows else dict((m, 0) for m in metrics)


def per_video(tok, days, ids):
    """Subscribers gained and lost, per video, in this window."""
    start, end = window(days)
    out = {}
    for k in range(0, len(ids), 150):
        r = yt.report(tok, start, end,
                      ["views", "subscribersGained", "subscribersLost",
                       "averageViewPercentage"],
                      dimensions=["video"],
                      filters="video==" + ",".join(ids[k:k + 150]), limit=200)
        for row in yt.as_rows(r):
            out[row["video"]] = row
    return out


def shorts_views(tok, days, vids):
    """Views of videos under three minutes - the Shorts monetisation path."""
    start, end = window(days)
    ids = [v["id"] for v in vids if v["kind"] == "short"]
    total = 0
    for k in range(0, len(ids), 150):
        r = yt.report(tok, start, end, ["views"], dimensions=["video"],
                      filters="video==" + ",".join(ids[k:k + 150]), limit=200)
        total += sum(row["views"] for row in yt.as_rows(r))
    return total


def pace(net, days, remaining):
    """Days to close a gap at the current rate, or None if it never closes."""
    if net <= 0 or remaining <= 0:
        return None
    per_day = net / float(days)
    return int(round(remaining / per_day)) if per_day else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=["fun", "us", "history"])
    a = ap.parse_args()

    tok = yt.access_token()
    ch = yt.channel(tok)
    expect = (os.environ.get("EXPECT_CHANNEL") or "").strip()
    if expect and expect.lower() not in ch["title"].lower():
        raise SystemExit("token is for %r, expected %r" % (ch["title"], expect))

    m = ["views", "estimatedMinutesWatched", "subscribersGained", "subscribersLost"]
    t7, t28 = totals(tok, 7, m), totals(tok, 28, m)
    t365 = totals(tok, 365, ["views", "estimatedMinutesWatched"])

    vids = yt.uploads(tok, ch["uploads"], cap=400)
    public = [v for v in vids if v.get("privacy") == "public"]
    ids = [v["id"] for v in public]
    by_video = per_video(tok, 28, ids)
    s90 = shorts_views(tok, 90, public)

    titles = dict((v["id"], v["title"]) for v in public)
    rows = []
    for vid, r in by_video.items():
        views = r.get("views") or 0
        if not views:
            continue
        gained = int(r.get("subscribersGained") or 0)
        lost = int(r.get("subscribersLost") or 0)
        rows.append({
            "id": vid, "title": titles.get(vid, ""), "views": views,
            "gained": gained, "lost": lost, "net": gained - lost,
            "per_1k": round((gained - lost) * 1000.0 / views, 2),
            "avg_pct": r.get("averageViewPercentage"),
        })

    converters = sorted([r for r in rows if r["views"] >= 50],
                        key=lambda r: (-r["per_1k"], -r["views"]))
    losers = sorted([r for r in rows if r["lost"] > 0], key=lambda r: (r["net"], -r["lost"]))
    no_convert = sorted([r for r in rows if r["views"] >= 150 and r["gained"] == 0],
                        key=lambda r: -r["views"])

    net7 = int(t7.get("subscribersGained") or 0) - int(t7.get("subscribersLost") or 0)
    net28 = int(t28.get("subscribersGained") or 0) - int(t28.get("subscribersLost") or 0)
    subs_gap = max(0, GOAL_SUBS - ch["subscribers"])
    hours_365 = round(float(t365.get("estimatedMinutesWatched") or 0) / 60.0, 1)
    hours_gap = max(0, GOAL_WATCH_HOURS - hours_365)
    shorts_gap = max(0, GOAL_SHORTS_VIEWS - s90)

    card = {
        "channel": ch["title"], "key": a.key, "generated": date.today().isoformat(),
        "subscribers": ch["subscribers"],
        "last_7": {"gained": int(t7.get("subscribersGained") or 0),
                   "lost": int(t7.get("subscribersLost") or 0), "net": net7,
                   "views": int(t7.get("views") or 0),
                   "watch_hours": round(float(t7.get("estimatedMinutesWatched") or 0) / 60.0, 1)},
        "last_28": {"gained": int(t28.get("subscribersGained") or 0),
                    "lost": int(t28.get("subscribersLost") or 0), "net": net28,
                    "views": int(t28.get("views") or 0),
                    "watch_hours": round(float(t28.get("estimatedMinutesWatched") or 0) / 60.0, 1)},
        "monetisation": {
            "subscribers": ch["subscribers"], "subscriber_gap": subs_gap,
            "watch_hours_365": hours_365, "watch_hour_gap": hours_gap,
            "shorts_views_90": s90, "shorts_view_gap": shorts_gap,
            "days_to_1000_subs_at_this_rate": pace(net28, 28, subs_gap),
            "days_to_4000_hours_at_this_rate": pace(
                round(float(t28.get("estimatedMinutesWatched") or 0) / 60.0, 1), 28, hours_gap),
        },
        "best_converters": converters[:8],
        "subscriber_losing_videos": losers[:8],
        "views_without_subscribers": no_convert[:8],
    }
    io.open(os.path.join(store.DIR, "subscribers_%s.json" % a.key), "w",
            encoding="utf-8", newline="\n").write(json.dumps(card, ensure_ascii=False, indent=1))

    # ---- the scorecard, in the shape Fatema asked for
    L = []
    L.append("# Subscriber scorecard - %s" % ch["title"])
    L.append("")
    L.append("Measured %s from YouTube Analytics. Gained and lost are both real; "
             "net is what matters." % date.today().isoformat())
    L.append("")
    L.append("    CURRENT SUBSCRIBERS            %d" % ch["subscribers"])
    L.append("    GAINED - LAST 7 DAYS           %d" % card["last_7"]["gained"])
    L.append("    LOST   - LAST 7 DAYS           %d" % card["last_7"]["lost"])
    L.append("    NET    - LAST 7 DAYS           %+d" % net7)
    L.append("    GAINED - LAST 28 DAYS          %d" % card["last_28"]["gained"])
    L.append("    LOST   - LAST 28 DAYS          %d" % card["last_28"]["lost"])
    L.append("    NET    - LAST 28 DAYS          %+d" % net28)
    L.append("")
    if converters:
        b = converters[0]
        L.append("    BEST CONVERTER   %s (%+.2f net subs / 1k views, %d views)"
                 % (b["title"][:54], b["per_1k"], b["views"]))
    if no_convert:
        w = no_convert[0]
        L.append("    WORST CONVERTER  %s (%d views, 0 subscribers)"
                 % (w["title"][:54], w["views"]))
    L.append("")
    if losers:
        L.append("## Videos that cost subscribers in the last 28 days")
        L.append("")
        for r in losers[:8]:
            L.append("- **%s** - gained %d, lost %d, net %+d on %d views"
                     % (r["title"][:70], r["gained"], r["lost"], r["net"], r["views"]))
        L.append("")
    L.append("## Monetisation, by YouTube's own thresholds")
    L.append("")
    L.append("    subscribers           %5d / 1,000        gap %d" % (ch["subscribers"], subs_gap))
    L.append("    watch hours (365d)    %7.1f / 4,000      gap %.1f" % (hours_365, hours_gap))
    L.append("    Shorts views (90d)    %9d / 10,000,000  gap %d" % (s90, shorts_gap))
    d1 = card["monetisation"]["days_to_1000_subs_at_this_rate"]
    d2 = card["monetisation"]["days_to_4000_hours_at_this_rate"]
    L.append("")
    L.append("    at the last 28 days' rate: %s to 1,000 subscribers, %s to 4,000 hours"
             % ("%d days" % d1 if d1 else "never - the net is not positive enough",
                "%d days" % d2 if d2 else "never at this rate"))
    L.append("")
    io.open(os.path.join(store.DIR, "scorecard_%s.md" % a.key), "w",
            encoding="utf-8", newline="\n").write("\n".join(L) + "\n")

    print("\n".join(L), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
