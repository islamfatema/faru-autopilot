# -*- coding: utf-8 -*-
"""Put a clickable subscribe button inside the video.

Fatema asked for a subscribe button on the video itself that a viewer can just
click. On Shorts YouTube already draws one - the channel avatar with Subscribe
beside it, over the player - and nothing can be added inside that. On
long-form there is a place for exactly this and it has never been used: the
branding watermark, a small image YouTube overlays in the corner of every
video on the channel, which subscribes the viewer in one click.

That is the half where it matters anyway. The fan-funding gate needs 3,000
public long-form watch hours, every long-form view is a view from someone
willing to sit through more than a minute, and those are the people worth
asking.

What it does not do: it does not appear on Shorts, and on phones it shows only
in some layouts. So this is worth doing because it is permanent and free, not
because it will move this month's numbers - 93% of these channels' views are
Shorts.

The image is drawn here rather than shipped, so there is nothing to keep in
the repository and it matches whatever the channel is called.

    python tools/watermark.py history --check
    python tools/watermark.py history --apply

Env: YT_REFRESH_TOKEN_MANAGE - watermarks.set needs the editing scope.
"""
import argparse
import io
import json
import os
import struct
import sys
import urllib.error
import urllib.request
import zlib

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"
SIZE = 150          # YouTube scales it down; square is what it expects


def _open(req, timeout=120):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        raise RuntimeError("HTTP %s -> %s" % (e.code, body))


def access_token():
    # Either name. thumbnails.yml calls this from the branding step, which
    # sets REFRESH_TOKEN; standalone callers set YT_REFRESH_TOKEN_MANAGE. It
    # read only the second for two days, printed "not set", and stopped behind
    # a `|| true` while the run went green.
    for var in ("YT_REFRESH_TOKEN_MANAGE", "REFRESH_TOKEN"):
        refresh = (os.environ.get(var) or "").strip()
        if refresh:
            break
    if not refresh:
        raise SystemExit("neither YT_REFRESH_TOKEN_MANAGE nor REFRESH_TOKEN is "
                         "set - watermarks.set needs a token carrying the "
                         "editing scope")
    req = urllib.request.Request(
        TOKEN_URL, data=json.dumps({"refresh_token": refresh}).encode(),
        headers={"Content-Type": "application/json"})
    with _open(req) as r:
        j = json.loads(r.read())
    if not j.get("access_token"):
        raise RuntimeError("no access_token in response")
    return j["access_token"]


# ---------------------------------------------------------------- the image
# A PNG writer, because Pillow is not installed on this machine and the image
# is a rounded square with a play triangle - a few hundred pixels of flat
# colour, which is less code to write than a dependency is to add.
def _png(pixels, w, h):
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)

    def chunk(tag, data):
        c = tag + data
        return (struct.pack(">I", len(data)) + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def badge(path, rgb=(204, 0, 0)):
    """A red rounded square with a white play triangle, on transparency."""
    w = h = SIZE
    r = SIZE * 0.22                     # corner radius
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            # rounded-rectangle test
            dx = max(r - x, 0, x - (w - 1 - r))
            dy = max(r - y, 0, y - (h - 1 - r))
            inside = (dx * dx + dy * dy) <= r * r
            # a play triangle, centred, pointing right
            tx, ty = x - w * 0.40, y - h * 0.5
            tri = (tx >= 0 and tx <= w * 0.30
                   and abs(ty) <= (w * 0.30 - tx) * 0.82)
            if not inside:
                row += [0, 0, 0, 0]
            elif tri:
                row += [255, 255, 255, 255]
            else:
                row += [rgb[0], rgb[1], rgb[2], 235]
        rows.append(row)
    with open(path, "wb") as f:
        f.write(_png(rows, w, h))
    return path


def current(tok):
    j = _open(urllib.request.Request(
        "%s/channels?part=snippet&mine=true" % API,
        headers={"Authorization": "Bearer " + tok}))
    return json.loads(j.read())["items"][0]["snippet"]["title"]


def set_watermark(tok, channel_id, png_path):
    """Show it for the whole video, so it is there whenever someone decides.

    No `timing` and no `position`. A durationMs of "0" is zero milliseconds,
    not "the whole video" - that is what omitting timing means - and it is
    what made this come back 400 "Invalid Value" with no field named. The
    default position is the bottom right corner, which is where it was being
    asked to go anyway, so sending it only adds a field that can be rejected.
    """
    meta = json.dumps({
        # All three are required - removing them to find the invalid one got
        # 400 "Required" the next day. The invalid one was durationMs: "0",
        # which is zero milliseconds. Ten minutes covers a six-minute
        # documentary with room over; there is no value meaning "forever",
        # and Shorts never show a watermark at all.
        "timing": {"type": "offsetFromStart", "offsetMs": "3000",
                   "durationMs": "600000"},
        "position": {"type": "corner", "cornerPosition": "bottomRight"},
        "targetChannelId": channel_id,
    }).encode()
    blob = open(png_path, "rb").read()
    b = b"--f\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n" + meta
    b += b"\r\n--f\r\nContent-Type: image/png\r\n\r\n" + blob + b"\r\n--f--\r\n"
    req = urllib.request.Request(
        "%s/watermarks/set?channelId=%s" % (UPLOAD, channel_id), data=b,
        headers={"Authorization": "Bearer " + tok,
                 "Content-Type": "multipart/related; boundary=f",
                 "Content-Length": str(len(b))}, method="POST")
    with _open(req) as r:
        r.read()
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", choices=["fun", "us", "history"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--expect", default="")
    a = ap.parse_args()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "_watermark_%s.png" % a.channel)
    badge(out)
    print("drew %s (%d bytes)" % (out, os.path.getsize(out)))
    if not a.apply:
        print("(drawn only - pass --apply to set it on the channel)")
        return 0

    tok = access_token()
    name = current(tok)
    print("channel: %s" % name)
    if a.expect and a.expect.strip().lower() not in name.strip().lower():
        raise SystemExit("REFUSING: token is for %r, expected %r" % (name, a.expect))
    j = json.loads(_open(urllib.request.Request(
        "%s/channels?part=id&mine=true" % API,
        headers={"Authorization": "Bearer " + tok})).read())
    cid = j["items"][0]["id"]
    set_watermark(tok, cid, out)
    print("WATERMARK SET - a one-click subscribe button now sits in the corner "
          "of every long-form video on this channel")
    return 0


if __name__ == "__main__":
    sys.exit(main())
