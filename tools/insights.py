# -*- coding: utf-8 -*-
"""The numbers that actually decide whether a channel grows.

Everything measured in this project so far came from the Data API: views,
likes, comments, duration. Useful, and not enough. The Data API cannot tell you
how many times a video was SHOWN, so it cannot tell you whether a video failed
because nobody clicked it or because everyone who clicked left after four
seconds. Those two failures need opposite fixes, and until now every decision
here has been a guess between them.

The Analytics API has them. This pulls, per channel and per video:

    impressions, click-through rate      -> is the packaging working
    average view duration, % viewed      -> is the content working
    subscribers gained per 1,000 views   -> is the positioning working
    traffic sources                      -> where discovery is actually coming from
    new vs returning viewers             -> is anything being built

and prints the diagnosis those numbers imply, because the combination is what
matters: strong CTR with weak retention is a content problem, the reverse is a
packaging problem, and both weak means the topic is wrong.

    python tools/insights.py --days 28
    python tools/insights.py --days 7 --videos 15

Env: REFRESH_TOKEN with the yt-analytics.readonly scope, granted via
/api/yt-auth?manage=1. A token issued before that scope was added will fail
with 403; re-authorise the channel and replace the secret.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
DATA_API = "https://www.googleapis.com/youtube/v3"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"


def _open(req, timeout=120):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:400]))


def access_token():
    d = json.dumps({"refresh_token": os.environ["REFRESH_TOKEN"].strip()}).encode()
    r = urllib.request.Request(TOKEN_URL, data=d, headers={"Content-Type": "application/json"})
    return json.loads(_open(r).read())["access_token"]


def get(url, tok):
    return json.loads(_open(urllib.request.Request(
        url, headers={"Authorization": "Bearer " + tok})).read())


def report(tok, start, end, metrics, dimensions=None, sort=None,
           filters=None, limit=None):
    q = {"ids": "channel==MINE", "startDate": start, "endDate": end,
         "metrics": ",".join(metrics)}
    if dimensions:
        q["dimensions"] = ",".join(dimensions)
    if sort:
        q["sort"] = sort
    if filters:
        q["filters"] = filters
    if limit:
        q["maxResults"] = str(limit)
    try:
        return get(ANALYTICS + "?" + urllib.parse.urlencode(q), tok)
    except RuntimeError as e:
        msg = str(e)
        if "insufficient" in msg.lower() or "403" in msg[:12]:
            # The distinction matters: a missing scope is fixed by
            # re-authorising, and looks nothing like a spent quota.
            raise SystemExit(
                "This token cannot read analytics.\n"
                "Re-authorise the channel at\n"
                "  https://faru-pwa.vercel.app/api/yt-auth?manage=1\n"
                "signed in as this channel's owner, then replace the secret.\n"
                "\nGoogle said: %s" % msg[:200])
        raise


def rows(r):
    return r.get("rows") or []


def one(r, default=0):
    rr = rows(r)
    return rr[0] if rr else [default] * len(r.get("columnHeaders", [1]))


def fmt_secs(s):
    return "%d:%02d" % (int(s) // 60, int(s) % 60)


def channel_name(tok):
    j = get(DATA_API + "/channels?part=snippet&mine=true", tok)
    return j["items"][0]["snippet"]["title"] if j.get("items") else "(unknown)"


def diagnose(ctr, pct_viewed, subs_per_k, have_ctr=True):
    """The decision rule. CTR and retention fail in opposite directions and
    need opposite fixes, which is exactly why guessing between them wastes
    weeks.

    have_ctr says whether a click-through rate was actually measured. On a
    Shorts-dominated channel YouTube returns none at all, and the first live
    run read that absence as a zero and announced a packaging problem that no
    number supported. An invented finding is worse than a missing one.
    """
    # Benchmarks for a small channel, not absolutes: 4-6% CTR is ordinary,
    # 30%+ average viewed is healthy, and 1 subscriber per thousand views is a
    # weak but common starting point.
    weak_ret = pct_viewed < 30.0
    weak_subs = subs_per_k < 1.0

    if not have_ctr:
        parts = ["NO CTR AVAILABLE - YouTube reports no impressions for this "
                 "channel, which is normal when almost all views come from the "
                 "Shorts feed. Nothing here can say whether packaging works."]
        if weak_ret:
            parts.append("Retention IS measured and it is weak: fix the first "
                         "ten seconds.")
        elif weak_subs:
            parts.append("Retention is fine and nobody subscribes: this is "
                         "positioning, not packaging.")
        else:
            parts.append("Retention and subscriber conversion are both fine.")
        return " ".join(parts)

    weak_ctr = ctr < 4.0
    if weak_ctr and weak_ret:
        return ("BOTH WEAK - the topic is not wanted. Change the subject, "
                "not the packaging.")
    if weak_ctr:
        return ("PACKAGING - people who watch it stay, and almost nobody "
                "clicks. Rewrite titles and thumbnails; the content is fine.")
    if weak_ret:
        return ("CONTENT - the packaging earns the click and the video loses "
                "them. Fix the first ten seconds before touching the title.")
    if weak_subs:
        return ("POSITIONING - clicks and retention are both fine and nobody "
                "subscribes. The channel is not telling them what they get "
                "if they come back.")
    return "WORKING - make more of this."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--videos", type=int, default=10)
    ap.add_argument("--json", help="also write the raw numbers here")
    a = ap.parse_args()

    end = date.today() - timedelta(days=1)     # today is always incomplete
    start = end - timedelta(days=a.days - 1)
    s, e = start.isoformat(), end.isoformat()

    tok = access_token()
    name = channel_name(tok)
    print("=" * 74)
    print("%s   %s to %s" % (name, s, e))
    print("=" * 74)

    core = report(tok, s, e, [
        "views", "estimatedMinutesWatched", "averageViewDuration",
        "averageViewPercentage", "subscribersGained", "subscribersLost",
        "likes", "comments", "shares"])
    ch = one(core)
    heads = [h["name"] for h in core.get("columnHeaders", [])]
    C = dict(zip(heads, ch))

    views = C.get("views", 0) or 0
    subs_net = (C.get("subscribersGained", 0) or 0) - (C.get("subscribersLost", 0) or 0)
    subs_per_k = (1000.0 * (C.get("subscribersGained", 0) or 0) / views) if views else 0

    # Impressions and CTR live in a separate report and are not available for
    # every video type; missing is not an error, it means YouTube has none.
    # Impressions have gone by more than one identifier, and on a channel whose
    # views are nearly all Shorts the API returns none under any of them. Try
    # each and say plainly which worked, rather than defaulting to zero and
    # letting the diagnosis treat "absent" as "low".
    ctr = imp = 0.0
    have_ctr = False
    last_imp_error = ""
    for names in (["impressions", "impressionClickThroughRate"],
                  ["annotationImpressions"],):
        try:
            ir = report(tok, s, e, names)
            ih = [h["name"] for h in ir.get("columnHeaders", [])]
            I = dict(zip(ih, one(ir)))
            imp = I.get(names[0], 0) or 0
            ctr = I.get("impressionClickThroughRate", 0) or 0
            have_ctr = "impressionClickThroughRate" in I
            break
        except Exception as ex:
            last_imp_error = str(ex)[:100]
    else:
        print("(no impressions metric available - %s)" % last_imp_error)

    print("\nCHANNEL, last %d days" % a.days)
    print("  views                     %s" % views)
    print("  impressions               %s" % (imp or "-"))
    print("  click-through rate        %s" % ("%.2f%%" % ctr if ctr else "-"))
    print("  watch time                %.1f hours" % ((C.get("estimatedMinutesWatched", 0) or 0) / 60.0))
    print("  average view duration     %s" % fmt_secs(C.get("averageViewDuration", 0) or 0))
    print("  average percentage viewed %.1f%%" % (C.get("averageViewPercentage", 0) or 0))
    print("  subscribers               +%s / -%s  (net %+d)"
          % (C.get("subscribersGained", 0), C.get("subscribersLost", 0), subs_net))
    print("  subscribers per 1k views  %.2f" % subs_per_k)
    print("  likes %s | comments %s | shares %s"
          % (C.get("likes", 0), C.get("comments", 0), C.get("shares", 0)))
    print("\n  DIAGNOSIS: %s"
          % diagnose(ctr, C.get("averageViewPercentage", 0) or 0, subs_per_k,
                     have_ctr))

    print("\nWHERE THE VIEWS CAME FROM")
    try:
        tr = report(tok, s, e, ["views", "estimatedMinutesWatched"],
                    dimensions=["insightTrafficSourceType"], sort="-views")
        tot = sum(r[1] for r in rows(tr)) or 1
        for r in rows(tr)[:8]:
            print("  %-26s %6d views  (%4.1f%%)  %6.1f hours"
                  % (r[0], r[1], 100.0 * r[1] / tot, r[2] / 60.0))
    except Exception as ex:
        print("  unavailable: %s" % str(ex)[:90])

    print("\nNEW vs RETURNING")
    try:
        nr = report(tok, s, e, ["views"], dimensions=["subscribedStatus"])
        for r in rows(nr):
            print("  %-14s %6d views" % (r[0], r[1]))
    except Exception as ex:
        print("  unavailable: %s" % str(ex)[:90])

    print("\nPER VIDEO - what to scale and what to fix")
    vids = []
    try:
        vr = report(tok, s, e,
                    ["views", "averageViewPercentage", "averageViewDuration",
                     "subscribersGained", "estimatedMinutesWatched"],
                    dimensions=["video"], sort="-views", limit=a.videos)
        ids = [r[0] for r in rows(vr)]
        titles = {}
        # Titles come from the Data API, whose quota is shared with the uploads
        # and runs out most afternoons. Losing the names is a nuisance; losing
        # the whole table because of it is not acceptable.
        for i in range(0, len(ids), 50):
            try:
                j = get(DATA_API + "/videos?part=snippet&id=" + ",".join(ids[i:i + 50]), tok)
            except Exception as ex:
                print("  (titles unavailable, showing ids: %s)" % str(ex)[:80])
                break
            for it in j.get("items", []):
                titles[it["id"]] = it["snippet"]["title"]
        print("  %-46s %6s %7s %6s %5s" % ("title", "views", "%viewed", "subs", "s/1k"))
        for r in rows(vr):
            vid, vw, pct, dur, sg, mw = r[0], r[1], r[2], r[3], r[4], r[5]
            spk = (1000.0 * sg / vw) if vw else 0
            vids.append({"id": vid, "title": titles.get(vid, vid), "views": vw,
                         "pct_viewed": pct, "avg_duration": dur,
                         "subs_gained": sg, "subs_per_1k": round(spk, 2),
                         "minutes_watched": mw})
            print("  %-46s %6d %6.1f%% %6d %5.2f"
                  % (titles.get(vid, vid)[:46], vw, pct, sg, spk))
    except Exception as ex:
        print("  unavailable: %s" % str(ex)[:120])

    if a.json:
        json.dump({"channel": name, "start": s, "end": e,
                   "channel_totals": C, "impressions": imp, "ctr": ctr,
                   "subs_per_1k": round(subs_per_k, 2), "videos": vids},
                  open(a.json, "w", encoding="utf-8"), indent=1)
        print("\nwrote %s" % a.json)
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
