# -*- coding: utf-8 -*-
"""Collect the real numbers for every video, and write them down.

    python growth/collect.py --key fun --days 28
    python growth/collect.py --key history --days 7 --retention 12

What it reads, all measured, none estimated:

    per video   views, watch minutes, average view duration, average percent
                viewed, subscribers gained and lost, likes, comments, shares,
                playlist adds
    per video   traffic sources (Shorts feed, browse, search, suggested, ...)
    per video   subscribed vs unsubscribed views - the closest the API gets to
                "returning viewers"
    per video   the retention curve, for the newest few, so the first three
                seconds can be judged instead of guessed

What it cannot read, and therefore stores as null: impressions and
click-through rate. They are Studio-only. Diagnosis has to work without them,
and the diagnosis module says so out loud rather than inventing a number.

Env: REFRESH_TOKEN (with yt-analytics.readonly), EXPECT_CHANNEL optional - if
set and the token belongs to a different channel, nothing is written.
"""
import argparse
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import store  # noqa: E402
import yt     # noqa: E402

BATCH = 150          # video ids per analytics filter
VIDEO_METRICS = ["views", "estimatedMinutesWatched", "averageViewDuration",
                 "averageViewPercentage", "subscribersGained", "subscribersLost",
                 "likes", "comments", "shares", "videosAddedToPlaylists"]


def window(days):
    end = date.today() - timedelta(days=1)          # yesterday: today is partial
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def per_video(tok, start, end, ids):
    out = {}
    for k in range(0, len(ids), BATCH):
        chunk = ids[k:k + BATCH]
        r = yt.report(tok, start, end, VIDEO_METRICS, dimensions=["video"],
                      filters="video==" + ",".join(chunk), limit=200)
        for row in yt.as_rows(r):
            out[row["video"]] = row
    return out


def traffic(tok, start, end, ids):
    """Where the views came from, per video. Costs one query per batch."""
    out = {}
    for k in range(0, len(ids), BATCH):
        chunk = ids[k:k + BATCH]
        r = yt.report(tok, start, end, ["views"],
                      dimensions=["video", "insightTrafficSourceType"],
                      filters="video==" + ",".join(chunk), limit=500)
        for row in yt.as_rows(r):
            out.setdefault(row["video"], {})[row["insightTrafficSourceType"]] = row["views"]
    return out


def subscribed_split(tok, start, end, ids):
    """Views from people who are subscribed, and from people who are not.

    FaRu's whole problem in one number: 11,321 views from people who were not
    subscribed and 65 from people who were.
    """
    out = {}
    for k in range(0, len(ids), BATCH):
        chunk = ids[k:k + BATCH]
        r = yt.report(tok, start, end, ["views"],
                      dimensions=["video", "subscribedStatus"],
                      filters="video==" + ",".join(chunk), limit=500)
        for row in yt.as_rows(r):
            out.setdefault(row["video"], {})[row["subscribedStatus"]] = row["views"]
    return out


def retention(tok, start, end, vid, duration_s):
    """The retention curve, and what fraction is still there at three seconds.

    audienceWatchRatio is reported against elapsedVideoTimeRatio in hundredths,
    so on a 20-second Short the 0.15 bucket is three seconds in. Anything below
    about 0.6 there means the hook failed, whatever the title did.
    """
    try:
        r = yt.report(tok, start, end, ["audienceWatchRatio"],
                      dimensions=["elapsedVideoTimeRatio"],
                      filters="video==" + vid)
    except Exception as e:
        print("   retention unavailable for %s: %s" % (vid, str(e)[:70]), flush=True)
        return None, None
    rows = yt.as_rows(r)
    if not rows:
        return None, None
    curve = [(row["elapsedVideoTimeRatio"], row["audienceWatchRatio"]) for row in rows]
    first3 = None
    if duration_s:
        target = min(0.99, 3.0 / duration_s)
        near = min(curve, key=lambda c: abs(c[0] - target))
        first3 = round(near[1], 3)
    return curve, first3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=["fun", "us", "history"])
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--retention", type=int, default=10,
                    help="how many of the newest videos get a retention curve")
    ap.add_argument("--cap", type=int, default=400)
    a = ap.parse_args()

    tok = yt.access_token()
    ch = yt.channel(tok)
    expect = (os.environ.get("EXPECT_CHANNEL") or "").strip()
    if expect and expect.lower() not in ch["title"].lower():
        raise SystemExit("token is for %r, expected %r - refusing to write"
                         % (ch["title"], expect))
    print("channel: %s  |  %d subscribers  |  %d lifetime views"
          % (ch["title"], ch["subscribers"], ch["views"]), flush=True)

    vids = yt.uploads(tok, ch["uploads"], cap=a.cap)
    public = [v for v in vids if v.get("privacy") == "public"]
    print("videos: %d public of %d" % (len(public), len(vids)), flush=True)

    start, end = window(a.days)
    ids = [v["id"] for v in public]
    print("window: %s .. %s (%d days)" % (start, end, a.days), flush=True)

    metrics = per_video(tok, start, end, ids)
    print("metrics: %d videos had activity in the window" % len(metrics), flush=True)
    src = traffic(tok, start, end, ids)
    subs = subscribed_split(tok, start, end, ids)

    data = store.load(a.key)
    data["channel"] = ch["title"]
    data["updated"] = date.today().isoformat()
    data["subscribers"] = ch["subscribers"]

    newest = sorted(public, key=lambda v: v["published"], reverse=True)[:a.retention]
    newest_ids = set(v["id"] for v in newest)

    for v in public:
        rec = store.upsert(data, v["id"], {
            "title": v["title"], "published": v["published"],
            "duration_s": v["duration_s"], "kind": v["kind"], "tags": v["tags"],
        })
        m = metrics.get(v["id"])
        if not m:
            continue                      # no activity in the window: nothing to add
        curve = first3 = None
        if v["id"] in newest_ids:
            curve, first3 = retention(tok, start, end, v["id"], v["duration_s"])
        snap = {
            "date": date.today().isoformat(),
            "window_days": a.days,
            "views": int(m.get("views") or 0),
            "watch_minutes": round(float(m.get("estimatedMinutesWatched") or 0), 1),
            "avd_s": int(m.get("averageViewDuration") or 0),
            "avg_pct": round(float(m.get("averageViewPercentage") or 0), 1),
            "subs_gained": int(m.get("subscribersGained") or 0),
            "subs_lost": int(m.get("subscribersLost") or 0),
            "likes": int(m.get("likes") or 0),
            "comments": int(m.get("comments") or 0),
            "shares": int(m.get("shares") or 0),
            "playlist_adds": int(m.get("videosAddedToPlaylists") or 0),
            # Studio-only: never guessed. See store.UNAVAILABLE.
            "impressions": None,
            "ctr": None,
            "traffic": src.get(v["id"]) or {},
            "subscribed": subs.get(v["id"]) or {},
            "first3_ratio": first3,
            "views_total": v["views_total"],
        }
        if curve:
            snap["retention_curve"] = [[round(x, 3), round(y, 3)] for x, y in curve][:40]
        store.add_snapshot(rec, snap)

    store.save(a.key, data)
    live = sum(1 for v in data["videos"].values() if store.latest(v))
    print("wrote analytics/videos_%s.json  (%d videos, %d with numbers)"
          % (a.key, len(data["videos"]), live), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
