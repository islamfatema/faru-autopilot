# -*- coding: utf-8 -*-
"""The YouTube clients the growth loop needs, in one place.

tools/insights.py already talks to both APIs, but it prints a report and exits;
the growth loop needs the same calls as functions it can compose. Auth is the
same as everywhere else in this repo: a refresh token in REFRESH_TOKEN, swapped
for an access token by the app's own endpoint so the client secret stays on the
server.

The token must carry yt-analytics.readonly (granted by
/api/yt-auth?manage=1). A token without it fails with a 403 that reads exactly
like a permissions problem on the channel, which cost this project a week once.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
DATA_API = "https://www.googleapis.com/youtube/v3"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"


def _open(req, timeout=120, tries=3):
    last = None
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            # 403 on a quota or a scope is final; a 5xx is worth retrying.
            if e.code < 500:
                raise RuntimeError("%d %s" % (e.code, body[:300]))
            last = RuntimeError("%d %s" % (e.code, body[:200]))
        except Exception as e:
            last = e
        time.sleep(3 * (attempt + 1))
    raise last


def access_token(refresh=None):
    refresh = (refresh or os.environ.get("REFRESH_TOKEN") or "").strip()
    if not refresh:
        raise SystemExit("no REFRESH_TOKEN")
    req = urllib.request.Request(TOKEN_URL, data=json.dumps({"refresh_token": refresh}).encode(),
                                 headers={"Content-Type": "application/json"})
    with _open(req) as r:
        j = json.loads(r.read())
    if not j.get("access_token"):
        raise SystemExit("no access_token in response: %s" % str(j)[:200])
    return j["access_token"]


def get(url, tok):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with _open(req) as r:
        return json.loads(r.read())


def channel(tok):
    j = get(DATA_API + "/channels?part=snippet,contentDetails,statistics&mine=true", tok)
    if not j.get("items"):
        raise SystemExit("this token has no channel")
    c = j["items"][0]
    return {"id": c["id"], "title": c["snippet"]["title"],
            "uploads": c["contentDetails"]["relatedPlaylists"]["uploads"],
            "subscribers": int(c["statistics"].get("subscriberCount") or 0),
            "views": int(c["statistics"].get("viewCount") or 0)}


def _iso_seconds(dur):
    """PT1M30S -> 90. Durations are how a Short is told from a documentary."""
    import re
    m = re.match(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?$", dur or "")
    if not m:
        return 0
    d, h, mi, s = [float(x or 0) for x in m.groups()]
    return int(d * 86400 + h * 3600 + mi * 60 + s)


def uploads(tok, uploads_playlist, cap=400):
    """Every published video: id, title, publish time, duration, tags, stats."""
    ids, page = [], None
    while len(ids) < cap:
        u = (DATA_API + "/playlistItems?part=contentDetails&maxResults=50&playlistId="
             + uploads_playlist)
        if page:
            u += "&pageToken=" + page
        j = get(u, tok)
        ids += [i["contentDetails"]["videoId"] for i in j.get("items", [])]
        page = j.get("nextPageToken")
        if not page:
            break

    out = []
    for k in range(0, len(ids), 50):
        j = get(DATA_API + "/videos?part=snippet,contentDetails,statistics,status&id="
                + ",".join(ids[k:k + 50]), tok)
        for v in j.get("items", []):
            secs = _iso_seconds(v["contentDetails"]["duration"])
            out.append({
                "id": v["id"],
                "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"],
                "tags": [t.lower() for t in (v["snippet"].get("tags") or [])][:12],
                "duration_s": secs,
                "kind": "short" if secs and secs <= 180 else "long",
                "privacy": v.get("status", {}).get("privacyStatus"),
                "views_total": int(v["statistics"].get("viewCount") or 0),
            })
    return out


def report(tok, start, end, metrics, dimensions=None, filters=None,
           sort=None, limit=None):
    """One Analytics query. Raises with a readable message on a missing scope."""
    q = {"ids": "channel==MINE", "startDate": start, "endDate": end,
         "metrics": ",".join(metrics)}
    if dimensions:
        q["dimensions"] = ",".join(dimensions)
    if filters:
        q["filters"] = filters
    if sort:
        q["sort"] = sort
    if limit:
        q["maxResults"] = str(limit)
    try:
        return get(ANALYTICS + "?" + urllib.parse.urlencode(q), tok)
    except RuntimeError as e:
        msg = str(e)
        if "insufficient" in msg.lower():
            raise SystemExit(
                "This token cannot read analytics - re-authorise the channel "
                "with the analytics scope and replace the secret.\n%s" % msg[:200])
        raise


def as_rows(r):
    """Analytics rows as dicts keyed by the column names it returned."""
    cols = [c["name"] for c in (r.get("columnHeaders") or [])]
    return [dict(zip(cols, row)) for row in (r.get("rows") or [])]
