# -*- coding: utf-8 -*-
"""Give every video a next video.

Three channels, 514 published videos, and one playlist between them. Someone who
finishes a Short and taps through to the channel arrives at a wall of thumbnails
in no order and leaves. Nothing chains, nothing autoplays, and the channel page
answers none of the three questions it has to: who is this for, what do I get,
why subscribe.

Playlists are the cheapest fix available. They cost no production, they put a
next video in front of a viewer who has already proved they are interested, and
watch time from a playlist counts toward the 4,000 hours that open the Partner
Programme.

Each channel gets:

  DOCUMENTARIES  every video over four minutes, newest first. This is where the
                 money is - long-form pays several dollars per thousand views
                 against about two cents for Shorts - and it is currently the
                 hardest thing on the channel to find.

  START HERE     the ten highest-viewed Shorts, best first. A first-time visitor
                 should meet the channel's best work, not its most recent.

Both are idempotent: an existing playlist with the same title is reused and only
missing videos are added, so running this daily costs almost nothing and keeps
the lists current as new videos publish.

    python tools/playlists.py --check
    python tools/playlists.py --apply

Env: REFRESH_TOKEN with the editing scope (/api/yt-auth?manage=1).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"

DOC_SECONDS = 240
START_HERE_SIZE = 10

PLAYLISTS = {
    "documentaries": {
        "title": "Documentaries",
        "description": ("The long ones. Full stories, properly told - the videos "
                        "the Shorts are taken from."),
    },
    "start_here": {
        "title": "Start Here - Best of the Channel",
        "description": ("New here? These are the ones people watched most. "
                        "Start at the top."),
    },
}


def _open(req, timeout=120):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))


def access_token():
    d = json.dumps({"refresh_token": os.environ["REFRESH_TOKEN"].strip()}).encode()
    r = urllib.request.Request(TOKEN_URL, data=d, headers={"Content-Type": "application/json"})
    return json.loads(_open(r).read())["access_token"]


def get(url, tok):
    return json.loads(_open(urllib.request.Request(
        url, headers={"Authorization": "Bearer " + tok})).read())


def post(url, tok, body):
    return json.loads(_open(urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + tok,
                 "Content-Type": "application/json"})).read())


def iso_seconds(dur):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def uploads(tok):
    ch = get(API + "/channels?part=snippet,contentDetails&mine=true", tok)
    if not ch.get("items"):
        raise SystemExit("no channel for this token")
    c = ch["items"][0]
    up = c["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        u = API + "/playlistItems?part=contentDetails&maxResults=50&playlistId=" + up
        if page:
            u += "&pageToken=" + page
        for attempt in (1, 2, 3):
            try:
                j = get(u, tok)
                break
            except Exception as e:
                # A single page occasionally comes back 404 for the uploads
                # playlist itself. Retrying works; giving up loses every video
                # after that point.
                if attempt == 3:
                    print("  page failed after 3 tries (%s) - continuing with "
                          "the %d found so far" % (str(e)[:90], len(ids)), flush=True)
                    j = None
                    break
                time.sleep(3)
        if j is None:
            break
        ids += [it["contentDetails"]["videoId"] for it in j.get("items", [])]
        page = j.get("nextPageToken")
        if not page:
            break
    out = []
    for i in range(0, len(ids), 50):
        j = get(API + "/videos?part=snippet,statistics,contentDetails,status&id="
                + ",".join(ids[i:i + 50]), tok)
        for v in j.get("items", []):
            if v["status"]["privacyStatus"] != "public":
                continue      # duplicates hidden by the cleanup stay hidden
            v["_views"] = int(v.get("statistics", {}).get("viewCount", 0) or 0)
            v["_secs"] = iso_seconds(v["contentDetails"].get("duration"))
            out.append(v)
    return c["snippet"]["title"], out


def existing(tok):
    """title -> (playlistId, set of videoIds already in it)."""
    out, page = {}, None
    while True:
        u = API + "/playlists?part=snippet&mine=true&maxResults=50"
        if page:
            u += "&pageToken=" + page
        j = get(u, tok)
        for p in j.get("items", []):
            out[p["snippet"]["title"]] = [p["id"], set()]
        page = j.get("nextPageToken")
        if not page:
            break
    for title, pair in out.items():
        pid, seen, page2 = pair[0], pair[1], None
        while True:
            u = API + "/playlistItems?part=contentDetails&maxResults=50&playlistId=" + pid
            if page2:
                u += "&pageToken=" + page2
            try:
                j = get(u, tok)
            except Exception:
                break
            seen |= {it["contentDetails"]["videoId"] for it in j.get("items", [])}
            page2 = j.get("nextPageToken")
            if not page2:
                break
    return out


def check_channel(actual, expected):
    """Stop before writing if the token is not the channel we were told."""
    if not expected:
        return
    if actual.strip().lower() != expected.strip().lower():
        raise SystemExit(
            "REFUSING TO WRITE."
            "\n  this run is for : %s"
            "\n  the token is    : %s"
            "\nA swapped secret would edit the wrong channel. Fix the secret "
            "rather than removing this check." % (expected, actual))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=30,
                    help="videos to add per run - each insert spends shared quota")
    ap.add_argument("--expect", default="",
                    help="the channel title this run is for - the tool "
                         "refuses to write if the token is a different one")
    a = ap.parse_args()

    tok = access_token()
    name, vids = uploads(tok)
    print("channel: %s  |  %d public videos" % (name, len(vids)), flush=True)
    check_channel(name, a.expect)

    docs = sorted([v for v in vids if v["_secs"] >= DOC_SECONDS],
                  key=lambda v: v["snippet"]["publishedAt"], reverse=True)
    shorts = sorted([v for v in vids if v["_secs"] < DOC_SECONDS],
                    key=lambda v: -v["_views"])[:START_HERE_SIZE]

    want = {"documentaries": docs, "start_here": shorts}
    have = existing(tok)
    print("existing playlists: %s" % (", ".join(have) or "none"), flush=True)

    budget = a.limit
    for key, spec in PLAYLISTS.items():
        picks = want[key]
        if not picks:
            print("\n%s: nothing to put in it yet" % spec["title"])
            continue
        print("\n%s  (%d videos)" % (spec["title"], len(picks)), flush=True)
        for v in picks:
            print("   %6d views  %s" % (v["_views"], v["snippet"]["title"][:52]))
        if not a.apply:
            continue

        if spec["title"] in have:
            pid, already = have[spec["title"]]
        else:
            try:
                p = post(API + "/playlists?part=snippet,status", tok,
                         {"snippet": {"title": spec["title"],
                                      "description": spec["description"]},
                          "status": {"privacyStatus": "public"}})
                pid, already = p["id"], set()
                print("   created %s" % pid, flush=True)
            except Exception as e:
                print("   could not create: %s" % str(e)[:180], flush=True)
                continue

        added = 0
        for v in picks:
            if v["id"] in already:
                continue
            if budget <= 0:
                print("   run limit reached - the rest go in the next run", flush=True)
                break
            try:
                post(API + "/playlistItems?part=snippet", tok,
                     {"snippet": {"playlistId": pid,
                                  "resourceId": {"kind": "youtube#video",
                                                 "videoId": v["id"]}}})
                added += 1
                budget -= 1
            except Exception as e:
                msg = str(e)
                if "quotaExceeded" in msg or "exceeded your" in msg:
                    print("   STOPPED - daily quota spent, shared with the "
                          "uploads. Resets midnight Pacific.", flush=True)
                    return 2
                print("   failed on %s: %s" % (v["id"], msg[:140]), flush=True)
            time.sleep(0.5)
        print("   added %d" % added, flush=True)

    if not (a.apply or a.check):
        print("\n(nothing changed - pass --apply to build them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
