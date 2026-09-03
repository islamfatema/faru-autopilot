# -*- coding: utf-8 -*-
"""Put a real thumbnail on the documentaries that published without one.

Custom thumbnails need a phone-verified YouTube channel. Two of the three
channels were not verified, so every documentary they published went out with a
frame YouTube picked at random - and on long-form the thumbnail is the single
biggest determinant of whether anyone clicks at all. The generator was building
the image correctly the whole time; the API was refusing it with a 403.

Once a channel is verified this walks its long-form uploads and sets a proper
thumbnail on each, built from the video's own title.

    python tools/set_thumbnails.py --check      # just test the permission
    python tools/set_thumbnails.py --apply      # set them

Env: REFRESH_TOKEN (needs the editing scope, via /api/yt-auth?manage=1)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Anything this long is a documentary; the Shorts are seconds.
MIN_SECONDS = 240


def _open(req, timeout=120):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError("HTTP %s %s" % (e.code, body[:300]))


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


def long_uploads(tok):
    ch = get(API + "/channels?part=snippet,contentDetails&mine=true", tok)
    if not ch.get("items"):
        raise SystemExit("no channel for this token")
    c = ch["items"][0]
    print("channel: %s" % c["snippet"]["title"], flush=True)
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
        j = get(API + "/videos?part=snippet,contentDetails,status&id=" + ",".join(ids[i:i + 50]), tok)
        for v in j.get("items", []):
            if (v["status"]["privacyStatus"] == "public"
                    and iso_seconds(v["contentDetails"].get("duration")) >= MIN_SECONDS):
                out.append(v)
    return out


def build_thumbnail(title, look, dst):
    """Reuse the documentary thumbnail builder so these match the new ones."""
    words = re.sub(r"[\(\)\[\]]", "", title).split()
    half = max(1, len(words) // 2)
    line1 = " ".join(words[:half])[:22]
    line2 = " ".join(words[half:])[:22]
    spec = {"img": look, "line1": line1, "line2": line2, "badge": "TRUE"}
    tmp = os.path.join(os.path.dirname(dst), "thumb_spec.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    script = os.path.join(ROOT, "autopilot_history", "longform", "thumb.py")
    r = subprocess.run([sys.executable, script, tmp, dst], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dst):
        print("  thumbnail build failed: %s" % (r.stderr or "")[-200:], flush=True)
        return False
    return True


def set_thumbnail(vid, path, tok):
    data = open(path, "rb").read()
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=" + vid,
        data=data, method="POST",
        headers={"Authorization": "Bearer " + tok, "Content-Type": "image/png"})
    _open(req)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="only test whether the channel may set thumbnails at all")
    ap.add_argument("--limit", type=int, default=5,
                    help="the daily quota is shared with the uploads and "
                         "with the other two channels, so a few a day")
    a = ap.parse_args()

    tok = access_token()
    vids = long_uploads(tok)
    print("long-form videos (over %ds): %d\n" % (MIN_SECONDS, len(vids)), flush=True)
    for v in vids[:15]:
        print("   %s  %5ds  %s" % (v["id"], iso_seconds(v["contentDetails"]["duration"]),
                                   v["snippet"]["title"][:52]))
    if not vids:
        return 0

    if not (a.apply or a.check):
        print("\n(nothing changed - pass --check to test permission, --apply to set them)")
        return 0

    work = os.path.join(ROOT, "_thumbs")
    os.makedirs(work, exist_ok=True)

    todo = vids[:1] if a.check else vids[:a.limit]
    done = 0
    for v in todo:
        title = v["snippet"]["title"]
        dst = os.path.join(work, v["id"] + ".png")
        look = (v["snippet"].get("description") or "")[:70] or title
        print("\n%s  %s" % (v["id"], title[:56]), flush=True)
        if not build_thumbnail(title, look + ", cinematic documentary still", dst):
            continue
        try:
            set_thumbnail(v["id"], dst, tok)
            print("  THUMBNAIL SET", flush=True)
            done += 1
        except Exception as e:
            msg = str(e)
            # Both come back as 403 and they mean opposite things. Reporting a
            # spent quota as "not verified" sends someone off to verify a
            # channel that already is - which is exactly the wrong afternoon.
            if "exceeded your" in msg or "quotaExceeded" in msg:
                print("  STOPPED - the daily API quota is spent. It is shared by "
                      "all three channels and the uploads, and it resets at "
                      "midnight Pacific. Run again tomorrow.", flush=True)
                return 2
            if "custom video thumbnails" in msg:
                print("  REFUSED - this channel is not phone verified.", flush=True)
                print("  Verify at https://www.youtube.com/verify_phone_number "
                      "signed in as this channel's owner, then run again.", flush=True)
                return 1
            print("  failed: %s" % msg[:160], flush=True)
        time.sleep(1)

    print("\nthumbnails set: %d" % done)
    return 0


if __name__ == "__main__":
    sys.exit(main())
