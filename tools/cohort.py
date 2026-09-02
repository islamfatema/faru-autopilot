# -*- coding: utf-8 -*-
"""Did the fixes work? Compare the videos made before them with the ones after.

A run of real bugs was fixed on 2026-09-01: duplicate uploads, a canned opening
line that buried the interesting sentence, a 25 second timeout that meant almost
every video quietly used a stock background instead of its own picture, and a
rotation that ignored the one thing separating this channel's hits from its
flops.

Every one of those was a genuine defect. Whether fixing them moves subscribers
is a different question, and the only honest way to answer it is to let both
cohorts age and compare them - so this splits the channel at the fix date and
reports views per day either side.

Views per day, not total views: an older video has had longer to collect them,
and comparing raw totals would always flatter the older cohort.

    python tools/cohort.py            # since the default fix date
    python tools/cohort.py --since 2026-09-01

Env: REFRESH_TOKEN
"""
import argparse
import json
import os
import statistics
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"
FIX_DATE = "2026-09-01"

# Videos need a few days before views/day means anything - a video published an
# hour ago can show a wild rate off two views.
MIN_AGE_HOURS = 18


def _open(req, timeout=90):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        print("HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))
        raise


def access_token():
    d = json.dumps({"refresh_token": os.environ["REFRESH_TOKEN"].strip()}).encode()
    r = urllib.request.Request(TOKEN_URL, data=d, headers={"Content-Type": "application/json"})
    return json.loads(_open(r).read())["access_token"]


def get(url, tok):
    return json.loads(_open(urllib.request.Request(
        url, headers={"Authorization": "Bearer " + tok})).read())


def videos(tok):
    ch = get(API + "/channels?part=snippet,contentDetails&mine=true", tok)
    if not ch.get("items"):
        raise SystemExit("no channel for this token")
    c = ch["items"][0]
    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, page = [], None
    while True:
        u = API + "/playlistItems?part=contentDetails&maxResults=50&playlistId=" + uploads
        if page:
            u += "&pageToken=" + page
        j = get(u, tok)
        ids += [it["contentDetails"]["videoId"] for it in j.get("items", [])]
        page = j.get("nextPageToken")
        if not page:
            break

    out = []
    for i in range(0, len(ids), 50):
        j = get(API + "/videos?part=snippet,status,statistics&id=" + ",".join(ids[i:i + 50]), tok)
        out += j.get("items", [])
    return c["snippet"]["title"], out


def per_day(v, now):
    pub = datetime.strptime(v["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    hours = (now - pub).total_seconds() / 3600.0
    if hours < MIN_AGE_HOURS:
        return None, pub
    views = int((v.get("statistics") or {}).get("viewCount") or 0)
    return views / (hours / 24.0), pub


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=FIX_DATE,
                    help="the date the fixes landed (YYYY-MM-DD)")
    ap.add_argument("--window-days", type=float, default=0,
                    help="only compare against videos published this many days "
                         "before the cut, so both sides are a similar age "
                         "(0 = match the new cohort's age automatically)")
    a = ap.parse_args()
    cut = datetime.strptime(a.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    tok = access_token()
    name, vids = videos(tok)
    vids = [v for v in vids if v["status"]["privacyStatus"] == "public"]

    # Views per day flatters new videos: an old one's views have plateaued while
    # a two-day-old is still being shown around. Comparing everything ever
    # published against three days of new uploads would therefore show an
    # improvement even if nothing had changed. So the older side is limited to
    # videos of a similar age - by default, as far back before the cut as the
    # new cohort reaches forward.
    # At least a fortnight, so there is a real sample on the older side. Matching
    # the ages exactly is impossible while the fixes are only days old - nothing
    # published before the cut can be as young as something published after it -
    # so the age gap is measured below and reported rather than hidden.
    span = a.window_days or max(14.0, (now - cut).total_seconds() / 86400.0)
    window_start = cut - timedelta(days=span)

    before, after, too_new, out_of_window = [], [], 0, 0
    age_before, age_after = [], []
    for v in vids:
        rate, pub = per_day(v, now)
        if rate is None:
            too_new += 1
            continue
        age = (now - pub).total_seconds() / 86400.0
        if pub >= cut:
            after.append(rate); age_after.append(age)
        elif pub >= window_start:
            before.append(rate); age_before.append(age)
        else:
            out_of_window += 1

    print("=" * 62)
    print("%s   (public videos: %d)" % (name, len(vids)))
    print("=" * 62)
    if too_new:
        print("%d published in the last %dh - too new to rate, excluded"
              % (too_new, MIN_AGE_HOURS))
    if out_of_window:
        print("%d older than %.1f days before the cut - excluded so both sides "
              "are a comparable age" % (out_of_window, span))
    print()

    def row(label, rows):
        if not rows:
            print("%-22s no videos yet" % label)
            return None
        med = statistics.median(rows)
        print("%-22s %4d videos   median %6.1f views/day   best %6.0f"
              % (label, len(rows), med, max(rows)))
        return med

    b = row("before " + a.since, before)
    f = row("after  " + a.since, after)

    if b and f:
        change = (f - b) / b * 100.0
        print()
        print("median views/day: %+.0f%%" % change)

        # Be honest about what this number can and cannot support yet.
        warn = []
        if len(after) < 15:
            warn.append("only %d videos on the new side" % len(after))
        if age_before and age_after:
            ab, aa = statistics.median(age_before), statistics.median(age_after)
            print("median age: %.1f days before, %.1f days after" % (ab, aa))
            if ab > aa * 2.5:
                warn.append("the old videos are %.0fx older, and views per day "
                            "always flatters the younger side" % (ab / max(aa, 0.1)))
        if warn:
            print()
            print("TOO EARLY TO TRUST THIS: " + "; ".join(warn) + ".")
            print("Let the new videos age for a week, then read it again.")
        elif change > 15:
            print("The new videos are doing better.")
        elif change < -15:
            print("The new videos are doing worse. Something in the change hurt.")
        else:
            print("No clear difference.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
