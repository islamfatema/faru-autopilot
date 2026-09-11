# -*- coding: utf-8 -*-
"""Retitle documentaries that are already published.

Four documentaries exist across the channels. Their view counts three days in:

    The Empire That Ruled a Quarter of the World and Vanished in 30 Years   64
    Why Rome Actually Fell (It Is Not What You Were Taught)                  6
    What Happens When You Start Over at 40                                   2
    The Truth About Motivation Nobody Sells                                  0

The bodies are the same quality. What separates them is that the first title
names something a person can picture and count - a quarter of the world, thirty
years - and the others name a category. On long-form the title and the thumbnail
are the entire click decision, and a title can be changed after publishing.

So this rewrites them in place. The replacement for each video is grounded in
what that video actually says; nothing here claims anything new.

    python tools/retitle.py --check     # show what would change
    python tools/retitle.py --apply

Env: REFRESH_TOKEN with the editing scope (via /api/yt-auth?manage=1). A token
for one channel can only edit that channel's videos; the others are skipped.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"

# videoId -> the new title. Every one is taken from that episode's own script.
NEW_TITLES = {
    # Rise With Fate
    "E18o3PorTsY": "Telling People Your Goal Makes You Less Likely To Do It",
    "y1QHU4mZZ_M": "Founders Over 40 Succeed More Often Than Founders in Their 20s",
    # History That Explains the World - "Why Rome Actually Fell" is the single
    # most written headline on the internet, so it competes with everything.
    "ZFohrZG4DKM": "Rome Did Not Fall in a Year. It Took 300.",
    # FaRu Fact. The title said the signal "isn't invisible" - but it is
    # invisible; the script's actual claim is that it is physical and can be
    # blocked by water, metal and your own body. A title a viewer can prove
    # false in one second is worse than a dull one on a facts channel.
    "vz7fn4f1l6c": "Your Body Blocks Your Wi-Fi. So Does a Fish Tank. 📡 #tech #wifi #physics",
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


def mine(tok):
    """The video ids this token is actually allowed to edit."""
    ch = get(API + "/channels?part=snippet,contentDetails&mine=true", tok)
    if not ch.get("items"):
        raise SystemExit("no channel for this token")
    c = ch["items"][0]
    print("channel: %s" % c["snippet"]["title"], flush=True)
    check_channel(c["snippet"]["title"], EXPECT)
    up = c["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = set(), None
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
        ids |= {it["contentDetails"]["videoId"] for it in j.get("items", [])}
        page = j.get("nextPageToken")
        if not page:
            break
    # Outside the loop, so the retry path that breaks early still returns what
    # it found. Returning None there made the caller crash on "v in owned".
    return ids


EXPECT = os.environ.get("EXPECT_CHANNEL", "")


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
    a = ap.parse_args()

    tok = access_token()
    owned = mine(tok)
    todo = [v for v in NEW_TITLES if v in owned]
    if not todo:
        print("none of the videos to retitle belong to this channel")
        return 0

    changed = 0
    for vid in todo:
        # The update replaces the whole snippet, so the existing one has to be
        # read first - posting a partial snippet wipes the description, the tags
        # and the category, which is a far worse outcome than a weak title.
        j = get(API + "/videos?part=snippet&id=" + vid, tok)
        if not j.get("items"):
            print("%s: not found" % vid)
            continue
        snip = j["items"][0]["snippet"]
        old, new = snip.get("title", ""), NEW_TITLES[vid]
        if old == new:
            print("%s: already correct" % vid)
            continue
        print("\n%s\n  from: %s\n  to:   %s" % (vid, old, new), flush=True)
        if not a.apply:
            continue
        snip["title"] = new
        body = json.dumps({"id": vid, "snippet": snip}).encode("utf-8")
        req = urllib.request.Request(
            API + "/videos?part=snippet", data=body, method="PUT",
            headers={"Authorization": "Bearer " + tok,
                     "Content-Type": "application/json"})
        try:
            _open(req)
            print("  RETITLED", flush=True)
            changed += 1
        except Exception as e:
            msg = str(e)
            if "quotaExceeded" in msg or "exceeded your" in msg:
                print("  STOPPED - daily API quota spent, shared with the uploads. "
                      "Resets midnight Pacific.", flush=True)
                return 2
            print("  failed: %s" % msg[:200], flush=True)

    print("\nretitled: %d%s" % (changed, "" if a.apply else "  (check only)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
