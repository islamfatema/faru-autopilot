# -*- coding: utf-8 -*-
"""Hide the weaker copy of each documentary that went out twice.

Three documentaries published twice, because the episode picker rotated by
date and was wrong for four episodes a week. That is fixed at the source (the
ledger in longform/makeboard.py). The six videos are still live, and two copies
of one film split its views and read to YouTube as a channel repeating itself.

For each pair, the copy with more views stays public and the other is set to
PRIVATE - never deleted, so it can be restored in Studio in one click. This is
the same treatment the duplicate Shorts were given, which Fatema approved.

    python tools/hide_duplicates.py history --check
    python tools/hide_duplicates.py history --apply

Env: REFRESH_TOKEN with the editing scope, EXPECT_CHANNEL for the write guard.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"

# Keep the one with more views; hide the other. Decided from the live counts on
# 2026-09-11 - recorded here so the choice is visible, not recomputed silently.
HIDE = {
    "history": {
        "BFMSNegKu94": "The Map Mistake... (3 views; kept ikeb6yyu_sA, 19)",
        "WG6YO3bpxaA": "The American Town... (16 views; kept YfEybgT8b84, 26)",
    },
    "fun": {
        "gf9ddMR2RwU": "The Psychology Tricks... (14 views; kept mtHxKQX7Hdo, 17)",
    },
    "us": {},
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", choices=sorted(HIDE))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    todo = HIDE[a.channel]
    if not todo:
        print("nothing to hide on %s" % a.channel)
        return 0

    tok = access_token()
    ch = get(API + "/channels?part=snippet&mine=true", tok)
    name = ch["items"][0]["snippet"]["title"] if ch.get("items") else "?"
    print("channel: %s" % name, flush=True)
    expect = os.environ.get("EXPECT_CHANNEL", "")
    if expect and name.strip().lower() != expect.strip().lower():
        raise SystemExit("REFUSING TO WRITE: this run is for %r, the token is %r"
                         % (expect, name))

    j = get(API + "/videos?part=status,snippet&id=" + ",".join(todo), tok)
    found = {v["id"]: v for v in j.get("items", [])}
    for vid, why in todo.items():
        v = found.get(vid)
        if not v:
            print("  %s  not on this channel - skipped" % vid)
            continue
        st = v["status"]
        print("\n  %s  %s\n    now: %s" % (vid, why, st["privacyStatus"]), flush=True)
        if st["privacyStatus"] == "private":
            print("    already private")
            continue
        if not a.apply:
            continue
        # status is replaced whole by this call, so send back what was read with
        # one field changed - dropping selfDeclaredMadeForKids would reset it.
        st["privacyStatus"] = "private"
        body = json.dumps({"id": vid, "status": st}).encode("utf-8")
        req = urllib.request.Request(
            API + "/videos?part=status", data=body, method="PUT",
            headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
        try:
            _open(req)
            print("    SET PRIVATE", flush=True)
        except Exception as e:
            print("    failed: %s" % str(e)[:200], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
