# -*- coding: utf-8 -*-
"""Post a finished Short to Instagram Reels and Facebook Reels.

YouTube is one feed, and on a channel this size it is the slowest one: a new
vertical video usually reaches more people on Reels than in the Shorts feed,
and it is the same file. Both APIs fetch the video by URL rather than accepting
an upload, which is why every published Short is attached to a GitHub release
first - that release asset is the URL passed in here.

    python tools/crosspost_meta.py --video-url https://... --caption-file x.txt

Secrets, set as repository secrets and passed in as environment variables:

    IG_USER_ID        Instagram *Business* or Creator account id (not the handle)
    IG_ACCESS_TOKEN   long-lived token with instagram_content_publish
    FB_PAGE_ID        Facebook Page id
    FB_PAGE_TOKEN     Page access token with pages_manage_posts

Missing a pair simply skips that platform, so this is safe to wire in before
the tokens exist. Nothing here posts anywhere Fatema has not connected herself:
the tokens are the consent.
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
RUPLOAD = "https://rupload.facebook.com/video-upload/v21.0"


def call(url, data=None, headers=None, method=None, timeout=120):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        raise RuntimeError("%s -> %s" % (url.split("?")[0], raw[:300]))
    try:
        return json.loads(raw)
    except ValueError:
        return {"raw": raw}


def post_instagram(video_url, caption):
    """Reels are a two-step publish: create a container, wait, then publish."""
    uid = os.environ.get("IG_USER_ID", "").strip()
    tok = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not (uid and tok):
        print("instagram: no credentials, skipped")
        return None

    made = call("%s/%s/media" % (GRAPH, uid),
                {"media_type": "REELS", "video_url": video_url,
                 "caption": caption, "share_to_feed": "true", "access_token": tok})
    cid = made.get("id")
    if not cid:
        raise RuntimeError("instagram: no container id in %s" % made)

    # Instagram downloads and transcodes the file; publishing before it has
    # finished fails with a misleading error, so wait for FINISHED.
    for attempt in range(30):
        time.sleep(10)
        st = call("%s/%s?fields=status_code,status&access_token=%s" % (GRAPH, cid, tok))
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError("instagram: transcode failed: %s" % st)
        print("  instagram: %s (%d)" % (code, attempt + 1), flush=True)
    else:
        raise RuntimeError("instagram: container never finished")

    out = call("%s/%s/media_publish" % (GRAPH, uid),
               {"creation_id": cid, "access_token": tok})
    print("instagram: published %s" % out.get("id"))
    return out.get("id")


def post_facebook(video_url, caption):
    """Facebook Reels: start a session, hand it the URL, then finish."""
    page = os.environ.get("FB_PAGE_ID", "").strip()
    tok = os.environ.get("FB_PAGE_TOKEN", "").strip()
    if not (page and tok):
        print("facebook: no credentials, skipped")
        return None

    start = call("%s/%s/video_reels" % (GRAPH, page),
                 {"upload_phase": "start", "access_token": tok})
    vid = start.get("video_id")
    if not vid:
        raise RuntimeError("facebook: no video_id in %s" % start)

    call("%s/%s" % (RUPLOAD, vid), method="POST",
         headers={"Authorization": "OAuth " + tok, "file_url": video_url},
         timeout=600)

    out = call("%s/%s/video_reels" % (GRAPH, page),
               {"video_id": vid, "upload_phase": "finish",
                "video_state": "PUBLISHED", "description": caption,
                "access_token": tok})
    print("facebook: published %s (%s)" % (vid, out))
    return vid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-url", required=True)
    ap.add_argument("--caption-file")
    ap.add_argument("--caption", default="")
    a = ap.parse_args()

    caption = a.caption
    if a.caption_file and os.path.exists(a.caption_file):
        caption = io.open(a.caption_file, encoding="utf-8").read().strip()
    caption = caption[:2100]

    failed = 0
    for name, fn in (("instagram", post_instagram), ("facebook", post_facebook)):
        try:
            fn(a.video_url, caption)
        except Exception as e:
            failed += 1
            # One platform failing must not stop the other, and neither should
            # stop the YouTube pipeline that called this.
            print("%s FAILED: %s" % (name, str(e)[:300]), flush=True)
    return 0 if failed < 2 else 0      # never fail the publishing workflow


if __name__ == "__main__":
    sys.exit(main())
