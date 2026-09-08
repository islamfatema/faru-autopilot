# -*- coding: utf-8 -*-
"""Put the documentary link on the videos that already have the reach.

The funnel was wired into the generator, so every Short published from now on
opens its description with a link to the channel's documentary. That does
nothing for the 350 videos already up, and those are where the traffic is:

    Sharks Are Older Than Trees                        1,077 views   0 comments
    Oxford University Is Older Than the Aztec Empire      997 views   0 comments
    Ancient Roman Concrete Can Heal Itself                950 views   0 comments
    Anne Frank and Martin Luther King Were Born the Same  932 views   0 comments

Thirty-nine videos on the history channel alone have over 150 views, and their
descriptions point nowhere. That is the entire discovery the channel has
managed, spent.

This rewrites the description of already-published Shorts so the documentary
link sits at the top, where a collapsed Shorts description still shows it. The
rest of the description is preserved exactly - only the link block is added, or
replaced if an older one is already there.

    python tools/relink.py --check
    python tools/relink.py --apply --limit 25

Env: REFRESH_TOKEN with the editing scope (/api/yt-auth?manage=1).

The daily API quota is a single pool shared with the uploads and the other two
channels, so the limit is deliberately small. Highest-view videos go first,
because that is where the same edit is worth the most.
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
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MARK = "▶ FULL DOCUMENTARY:"
# Anything this long is a documentary itself and must not link to another one.
MIN_DOC_SECONDS = 240


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


def iso_seconds(dur):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def featured(channel_key):
    p = os.path.join(ROOT, "autopilot_%s" % channel_key, "featured_long.json")
    try:
        d = json.load(open(p, encoding="utf-8"))
        if d.get("url") and d.get("title"):
            return d
    except Exception:
        pass
    return None


def uploads(tok):
    ch = get(API + "/channels?part=snippet,contentDetails&mine=true", tok)
    if not ch.get("items"):
        raise SystemExit("no channel for this token")
    c = ch["items"][0]
    name = c["snippet"]["title"]
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
                continue          # duplicates hidden earlier stay hidden
            if iso_seconds(v["contentDetails"].get("duration")) >= MIN_DOC_SECONDS:
                continue          # this IS a documentary
            v["_views"] = int(v.get("statistics", {}).get("viewCount", 0) or 0)
            out.append(v)
    out.sort(key=lambda v: -v["_views"])
    return name, out


def rewrite(desc, block):
    """Add or replace the link block, leaving everything else untouched."""
    body = desc or ""
    if body.startswith(MARK):
        # Drop the old block: it runs to the first blank line after the URL.
        parts = body.split("\n\n", 1)
        body = parts[1] if len(parts) > 1 else ""
    return block + body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", help="us, fun or history - which featured_long.json to use")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=25,
                    help="the quota is shared with the uploads, so a few a day")
    ap.add_argument("--min-views", type=int, default=0,
                    help="skip videos below this - the same edit is worth more "
                         "on a video that is already being served")
    a = ap.parse_args()

    f = featured(a.channel)
    if not f:
        print("no featured documentary recorded for %s yet - nothing to link to"
              % a.channel)
        return 0
    block = "%s %s\n   %s\n\n" % (MARK, f["title"][:70], f["url"])

    tok = access_token()
    name, vids = uploads(tok)
    print("channel: %s" % name, flush=True)

    todo = [v for v in vids
            if v["_views"] >= a.min_views
            and not (v["snippet"].get("description") or "").startswith(MARK)]
    print("public Shorts: %d | missing the link: %d | linking to: %s"
          % (len(vids), len(todo), f["title"][:50]), flush=True)

    if not (a.apply or a.check):
        print("\n(nothing changed - pass --check to preview, --apply to write)")
        return 0

    done = 0
    for v in todo[:(1 if a.check else a.limit)]:
        snip = v["snippet"]
        print("\n%s  %6d views  %s" % (v["id"], v["_views"], snip["title"][:48]), flush=True)
        if a.check:
            print("  would prepend: %s" % block.strip().replace("\n", " | "))
            continue
        # The update replaces the whole snippet, so every field has to be sent
        # back - a partial snippet wipes the tags and the category, which is a
        # far worse outcome than a description that points nowhere.
        new = {"title": snip["title"],
               "description": rewrite(snip.get("description"), block),
               "categoryId": snip.get("categoryId", "22")}
        if snip.get("tags"):
            new["tags"] = snip["tags"]
        if snip.get("defaultLanguage"):
            new["defaultLanguage"] = snip["defaultLanguage"]
        body = json.dumps({"id": v["id"], "snippet": new}).encode("utf-8")
        req = urllib.request.Request(
            API + "/videos?part=snippet", data=body, method="PUT",
            headers={"Authorization": "Bearer " + tok,
                     "Content-Type": "application/json"})
        try:
            _open(req)
            print("  LINKED", flush=True)
            done += 1
        except Exception as e:
            msg = str(e)
            if "quotaExceeded" in msg or "exceeded your" in msg:
                print("  STOPPED - daily quota spent. It is shared with the "
                      "uploads and the other channels; resets midnight Pacific.",
                      flush=True)
                break
            print("  failed: %s" % msg[:180], flush=True)
        time.sleep(1)

    print("\nlinked: %d of %d still missing it" % (done, len(todo)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
