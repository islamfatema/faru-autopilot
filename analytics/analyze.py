# -*- coding: utf-8 -*-
"""
Winner-loop analytics.

Pulls every video's real performance from the YouTube API, classifies each one
WINNER / AVERAGE / UNDERPERFORMER against that channel's own median, then writes
`winners.json` for the generator to bias future topic selection toward what is
actually working.

Env: REFRESH_TOKEN (required), CHANNEL_KEY (e.g. history|fun|us), OUT_DIR
"""
import os, sys, json, time, statistics, urllib.request, urllib.parse
from datetime import datetime, timezone

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
OUT_DIR = os.environ.get("OUT_DIR", os.path.dirname(os.path.abspath(__file__)))
KEY = os.environ.get("CHANNEL_KEY", "channel")


def _open(req, t=90):
    try:
        return urllib.request.urlopen(req, timeout=t)
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode("utf-8", "replace")[:300])
        raise


def access_token():
    d = json.dumps({"refresh_token": os.environ["REFRESH_TOKEN"].strip()}).encode()
    r = urllib.request.Request(TOKEN_URL, data=d, headers={"Content-Type": "application/json"})
    return json.loads(_open(r).read())["access_token"]


def api(url, tok):
    return json.loads(_open(urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})).read())


def collect():
    tok = access_token()
    ch = api("https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,contentDetails&mine=true", tok)
    if not ch.get("items"):
        print("no channel"); return None
    c = ch["items"][0]
    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
    title = c["snippet"]["title"]
    stats = c["statistics"]

    # page through uploads
    ids, page = [], None
    while len(ids) < 400:
        u = ("https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails"
             "&maxResults=50&playlistId=" + uploads)
        if page:
            u += "&pageToken=" + page
        j = api(u, tok)
        ids += [it["contentDetails"]["videoId"] for it in j.get("items", [])]
        page = j.get("nextPageToken")
        if not page:
            break

    vids = []
    for i in range(0, len(ids), 50):
        chunk = ",".join(ids[i:i + 50])
        j = api("https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id=" + chunk, tok)
        for it in j.get("items", []):
            st = it.get("statistics", {})
            sn = it["snippet"]
            pub = sn.get("publishedAt", "")
            try:
                age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(pub.replace("Z", "+00:00"))).total_seconds() / 3600.0
            except Exception:
                age_h = 0.0
            vids.append({
                "id": it["id"],
                "title": sn.get("title", ""),
                "tags": sn.get("tags", [])[:12],
                "published": pub,
                "age_hours": round(age_h, 1),
                "views": int(st.get("viewCount", 0) or 0),
                "likes": int(st.get("likeCount", 0) or 0),
                "comments": int(st.get("commentCount", 0) or 0),
                "duration": it["contentDetails"].get("duration", ""),
            })
    return {"channel": title, "stats": stats, "videos": vids}


def classify(data):
    """Rank by views-per-day so new and old videos compare fairly."""
    vids = data["videos"]
    for v in vids:
        v["vpd"] = round(v["views"] / max(0.5, v["age_hours"] / 24.0), 2)
    scored = [v for v in vids if v["age_hours"] >= 12]      # need a little time to judge
    if len(scored) < 4:
        med = 0.0
    else:
        med = statistics.median([v["vpd"] for v in scored]) or 0.0
    for v in vids:
        if v["age_hours"] < 12:
            v["verdict"] = "TOO_NEW"
        elif med > 0 and v["vpd"] >= med * 2:
            v["verdict"] = "WINNER"
        elif med > 0 and v["vpd"] <= med * 0.5:
            v["verdict"] = "UNDERPERFORMER"
        else:
            v["verdict"] = "AVERAGE"
    return med


def winning_tags(data, med):
    """Tags that appear disproportionately in winners -> bias future topics."""
    win, all_ = {}, {}
    for v in data["videos"]:
        for t in v["tags"]:
            t = t.lower()
            all_[t] = all_.get(t, 0) + 1
            if v["verdict"] == "WINNER":
                win[t] = win.get(t, 0) + 1
    total = len(data["videos"]) or 1
    winners = sum(1 for v in data["videos"] if v["verdict"] == "WINNER")
    base = (winners / float(total)) if total else 0.0

    out = []
    for t, n in win.items():
        seen = all_.get(t, 0)
        # A tag on nearly every video (shorts, history, facts) carries no signal.
        # Left in, it made 100% of scripts match a "winning" tag, so the 2:1 bias
        # applied to everything and therefore did nothing at all.
        if seen < 3 or seen > 0.6 * total:
            continue
        rate = n / float(seen)
        # Only keep tags that beat the channel's own win rate by a clear margin.
        if rate <= base * 1.25:
            continue
        out.append({"tag": t, "wins": n, "seen": seen, "rate": round(rate, 2)})
    out.sort(key=lambda x: (x["rate"], x["wins"]), reverse=True)
    return out[:12]


def engagement(data):
    """Rank by what viewers DID, not by how many feeds it reached.

    likes + comments per thousand views. A comment is weighted five times a
    like because it costs the viewer far more, and because comments are what
    make YouTube show a Short to a wider audience. Shares are not exposed by
    the public API; the comment rate is the closest proxy there is.
    """
    out = []
    for v in data["videos"]:
        if v["views"] < 30:
            # Rates on a handful of views are noise - one like on four views
            # reads as a 250 per thousand triumph.
            continue
        per_k = 1000.0 / v["views"]
        like_r = v["likes"] * per_k
        cmt_r = v["comments"] * per_k
        out.append(dict(v, like_rate=round(like_r, 2), comment_rate=round(cmt_r, 2),
                        engagement=round(like_r + 5 * cmt_r, 2)))
    out.sort(key=lambda v: v["engagement"], reverse=True)
    return out


def main():
    data = collect()
    if not data:
        return
    med = classify(data)
    vids = sorted(data["videos"], key=lambda v: v["vpd"], reverse=True)
    tags = winning_tags(data, med)
    eng = engagement(data)

    os.makedirs(OUT_DIR, exist_ok=True)
    report = {
        "channel": data["channel"],
        "generated": datetime.now(timezone.utc).isoformat(),
        "subscribers": data["stats"].get("subscriberCount"),
        "total_views": data["stats"].get("viewCount"),
        "videos_analysed": len(vids),
        "median_views_per_day": med,
        "top_10": [{k: v[k] for k in ("title", "views", "vpd", "verdict", "id")} for v in vids[:10]],
        "bottom_5": [{k: v[k] for k in ("title", "views", "vpd", "verdict", "id")} for v in vids[-5:]],
        "winning_tags": tags,
        "counts": {x: sum(1 for v in vids if v["verdict"] == x)
                   for x in ("WINNER", "AVERAGE", "UNDERPERFORMER", "TOO_NEW")},
        "engagement_top_15": [{k: e[k] for k in
                               ("title", "views", "likes", "comments",
                                "like_rate", "comment_rate", "engagement", "id")}
                              for e in eng[:15]],
        "engagement_bottom_10": [{k: e[k] for k in
                                  ("title", "views", "likes", "comments",
                                   "like_rate", "comment_rate", "engagement", "id")}
                                 for e in eng[-10:]],
        "median_engagement": (sorted(e["engagement"] for e in eng)[len(eng) // 2]
                              if eng else 0),
    }
    json.dump(report, open(os.path.join(OUT_DIR, "report_%s.json" % KEY), "w"), indent=2)
    json.dump({"videos": eng},
              open(os.path.join(OUT_DIR, "engagement_%s.json" % KEY), "w"), indent=1)
    json.dump({"tags": [t["tag"] for t in tags]},
              open(os.path.join(OUT_DIR, "winners_%s.json" % KEY), "w"), indent=2)

    print("=" * 60)
    print("CHANNEL:", data["channel"])
    print("subs:", report["subscribers"], "| total views:", report["total_views"],
          "| videos:", len(vids))
    print("median views/day: %.2f" % med)
    print("verdicts:", report["counts"])
    print("-" * 60)
    print("TOP PERFORMERS")
    for v in vids[:8]:
        print("  %6d views | %6.2f/day | %-14s | %s" % (v["views"], v["vpd"], v["verdict"], v["title"][:58]))
    if tags:
        print("-" * 60)
        print("WINNING TAGS (make more of these):")
        for t in tags[:8]:
            print("  %-22s wins %d/%d  (%.0f%%)" % (t["tag"], t["wins"], t["seen"], t["rate"] * 100))
    print("-" * 60)
    print("WHAT PEOPLE ACTUALLY ENGAGED WITH  (likes + 5x comments per 1k views)")
    for v in eng[:10]:
        print("  score %6.1f | %5d views | %3d likes | %2d comments | %s"
              % (v["engagement"], v["views"], v["likes"], v["comments"], v["title"][:50]))
    if len(eng) > 12:
        print("  ... and the flattest:")
        for v in eng[-5:]:
            print("  score %6.1f | %5d views | %3d likes | %2d comments | %s"
                  % (v["engagement"], v["views"], v["likes"], v["comments"], v["title"][:50]))
    print("=" * 60)


if __name__ == "__main__":
    main()
