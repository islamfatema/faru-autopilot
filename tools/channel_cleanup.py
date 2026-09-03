# -*- coding: utf-8 -*-
"""Find, and optionally repair, the damage the old rotation left on a channel.

The rotation used to consume the script bank faster than it read it, so the same
scripts were published several times over. That is fixed for new uploads, but
the duplicates it already published are still on the channel, and the copies get
essentially no views - YouTube is suppressing them, and they drag the channel's
signal down with them.

Three separate problems, all visible from the API:

  duplicates   the same title published more than once
  wrong CTA    FaRu Fact's descriptions tell viewers to subscribe to History,
               a copy-paste from the other channel's generator
  stray Bangla a Bangla video still live on a channel that is now English only

REPORTS ONLY by default. Nothing is changed unless --apply is passed, and even
then videos are set to `private` rather than deleted, so anything can be undone.

    python tools/channel_cleanup.py                 # report
    python tools/channel_cleanup.py --apply         # fix descriptions + hide dupes

Env: REFRESH_TOKEN (required), CHANNEL_NAME (for the CTA text)
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"


def _open(req, timeout=90):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        print("HTTP %s %s" % (e.code, body), flush=True)
        raise


def access_token():
    d = json.dumps({"refresh_token": os.environ["REFRESH_TOKEN"].strip()}).encode()
    r = urllib.request.Request(TOKEN_URL, data=d, headers={"Content-Type": "application/json"})
    return json.loads(_open(r).read())["access_token"]


def get(url, tok):
    return json.loads(_open(urllib.request.Request(
        url, headers={"Authorization": "Bearer " + tok})).read())


def put(path, body, tok):
    r = urllib.request.Request(
        API + path, data=json.dumps(body).encode("utf-8"), method="PUT",
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    return json.loads(_open(r).read())


def all_videos(tok):
    ch = get(API + "/channels?part=snippet,contentDetails&mine=true", tok)
    if not ch.get("items"):
        raise SystemExit("no channel for this token")
    c = ch["items"][0]
    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
    print("channel: %s" % c["snippet"]["title"], flush=True)

    ids, page = [], None
    while True:
        u = (API + "/playlistItems?part=contentDetails&maxResults=50&playlistId=" + uploads)
        if page:
            u += "&pageToken=" + page
        j = get(u, tok)
        ids += [it["contentDetails"]["videoId"] for it in j.get("items", [])]
        page = j.get("nextPageToken")
        if not page:
            break

    vids = []
    for i in range(0, len(ids), 50):
        chunk = ",".join(ids[i:i + 50])
        j = get(API + "/videos?part=snippet,status,statistics&id=" + chunk, tok)
        vids += j.get("items", [])
    return c["snippet"]["title"], vids


BENGALI = re.compile(r"[ঀ-৿]")


def views(v):
    return int((v.get("statistics") or {}).get("viewCount") or 0)


def published(v):
    return v["snippet"].get("publishedAt", "")


def analyse(videos, wrong_cta):
    by_title = {}
    for v in videos:
        by_title.setdefault(v["snippet"]["title"].strip(), []).append(v)

    # Of each duplicated title keep the best performing copy - it is the one the
    # audience actually found - and hide the rest.
    dupes = []
    for title, group in by_title.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda v: (views(v), published(v)), reverse=True)
        dupes.append((title, group[0], group[1:]))

    bangla = [v for v in videos
              if BENGALI.search(v["snippet"]["title"] + (v["snippet"].get("description") or ""))]

    bad_cta = [v for v in videos
               if wrong_cta and wrong_cta in (v["snippet"].get("description") or "")]

    return dupes, bangla, bad_cta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="make the changes (without this it only reports)")
    ap.add_argument("--max-writes", type=int, default=25,
                    help="stop after this many changes. The daily YouTube quota "
                         "is shared by ALL THREE channels plus the uploads, the "
                         "analytics and the thumbnails - it belongs to the "
                         "Google project, not the channel. A 149 change repair "
                         "on one channel exhausted it for all of them, so this "
                         "is deliberately small and the repair takes days")
    ap.add_argument("--wrong-cta", default="Subscribe to History That Explains the World",
                    help="description text that points at the wrong channel")
    ap.add_argument("--right-cta", default="Subscribe to FaRu Fact for a surprising true fact every day.")
    a = ap.parse_args()

    tok = access_token()
    name, videos = all_videos(tok)
    print("videos on channel: %d\n" % len(videos), flush=True)

    dupes, bangla, bad_cta = analyse(videos, a.wrong_cta)

    extra = sum(len(rest) for _, _, rest in dupes)
    print("DUPLICATED TITLES: %d  (extra copies to hide: %d)" % (len(dupes), extra))
    for title, keep, rest in sorted(dupes, key=lambda d: -len(d[2]))[:15]:
        print("   %-52s keep %s (%d views), hide %s"
              % (title[:52], keep["id"], views(keep),
                 ", ".join("%s (%d views)" % (v["id"], views(v)) for v in rest)))

    print("\nBANGLA VIDEOS STILL LIVE: %d" % len(bangla))
    for v in bangla[:10]:
        print("   %s  %s (%d views)" % (v["id"], v["snippet"]["title"][:46], views(v)))

    print("\nDESCRIPTIONS POINTING AT THE WRONG CHANNEL: %d" % len(bad_cta))

    if not a.apply:
        print("\n(report only - nothing changed. Pass --apply to fix.)")
        return 0

    # The uploads draw on the same daily quota, and exhausting it would stop
    # the channels posting - which is worse than a repair that takes a few days.
    budget = [a.max_writes]

    def spend():
        if budget[0] <= 0:
            return False
        budget[0] -= 1
        return True

    # ---- fix descriptions -------------------------------------------------
    fixed = 0
    for v in bad_cta:
        if not spend():
            print("write budget of %d used - stopping here, run again tomorrow"
                  % a.max_writes, flush=True)
            break
        s = v["snippet"]
        s["description"] = s["description"].replace(a.wrong_cta, a.right_cta)
        try:
            put("/videos?part=snippet", {"id": v["id"], "snippet": {
                "title": s["title"], "description": s["description"],
                "categoryId": s.get("categoryId", "22"),
                "tags": s.get("tags", []),
            }}, tok)
            fixed += 1
        except Exception as e:
            print("  description failed on %s: %s" % (v["id"], str(e)[:120]), flush=True)
        time.sleep(0.4)
    print("descriptions corrected: %d" % fixed)

    # ---- hide duplicate copies -------------------------------------------
    # private, never deleted: a mistake here has to be undoable.
    hidden = 0
    stopped = False
    for _, _, rest in dupes:
        if stopped:
            break
        for v in rest:
            if v["status"]["privacyStatus"] == "private":
                continue
            if not spend():
                print("write budget used - %d duplicates still to hide, run "
                      "again tomorrow" % sum(
                          1 for _, _, r in dupes for x in r
                          if x["status"]["privacyStatus"] != "private"), flush=True)
                stopped = True
                break
            try:
                put("/videos?part=status", {"id": v["id"],
                    "status": {"privacyStatus": "private"}}, tok)
                hidden += 1
            except Exception as e:
                print("  hide failed on %s: %s" % (v["id"], str(e)[:120]), flush=True)
            time.sleep(0.4)
    print("duplicate copies made private: %d" % hidden)

    hb = 0
    for v in bangla:
        if v["status"]["privacyStatus"] == "private":
            continue
        if not spend():
            break
        try:
            put("/videos?part=status", {"id": v["id"],
                "status": {"privacyStatus": "private"}}, tok)
            hb += 1
        except Exception as e:
            print("  hide failed on %s: %s" % (v["id"], str(e)[:120]), flush=True)
        time.sleep(0.4)
    print("bangla videos made private: %d" % hb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
