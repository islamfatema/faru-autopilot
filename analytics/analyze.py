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
    out = []
    for t, n in win.items():
        if all_.get(t, 0) >= 2:
            out.append({"tag": t, "wins": n, "seen": all_[t], "rate": round(n / all_[t], 2)})
    out.sort(key=lambda x: (x["rate"], x["wins"]), reverse=True)
    return out[:15]


def main():
    data = collect()
    if not data:
        return
    med = classify(data)
    vids = sorted(data["videos"], key=lambda v: v["vpd"], reverse=True)
    tags = winning_tags(data, med)

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
    }
    json.dump(report, open(os.path.join(OUT_DIR, "report_%s.json" % KEY), "w"), indent=2)
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
    print("=" * 60)


if __name__ == "__main__":
    main()
