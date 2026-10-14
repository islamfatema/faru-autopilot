# -*- coding: utf-8 -*-
"""Hide the duplicate uploads, keeping the best copy of each.

Between 4 and 11 October History published the same documentary twenty-four
times: the ledger commit that stops the picker repeating never reached the
repository, and the workflow was quiet about the failure (see the --autostash
fix in autopost_doc*.yml). The bug is closed; the twenty-four videos are not.

Twenty-four copies of one thirteen-minute film is the exact shape YouTube's
duplicate-content rules are written for, on the only channel of the three that
is growing, and monetisation review is the whole point of this project.

So: for every title that appears more than once, the copy with the most views
stays public and the rest go private. Private, not deleted - it is reversible,
and nothing is destroyed. Their contribution to public watch time is about five
hours of History's two hundred and fifty-seven.

    python tools/hide_duplicates.py --key history            # show the plan
    python tools/hide_duplicates.py --key history --apply    # do it

Needs a refresh token carrying youtube.force-ssl in YT_REFRESH_TOKEN_MANAGE,
which only the runners have.
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://www.googleapis.com/youtube/v3"


def _open(req, timeout=60):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        raise RuntimeError("HTTP %s on %s -> %s" % (e.code, req.full_url, body))


def access_token():
    refresh = (os.environ.get("YT_REFRESH_TOKEN_MANAGE") or "").strip()
    if not refresh:
        raise SystemExit("YT_REFRESH_TOKEN_MANAGE is not set - this needs a "
                         "token carrying youtube.force-ssl")
    req = urllib.request.Request("https://faru-pwa.vercel.app/api/yt-token",
                                 data=json.dumps({"refresh_token": refresh}).encode(),
                                 headers={"Content-Type": "application/json"})
    with _open(req) as r:
        j = json.loads(r.read())
    if not j.get("access_token"):
        raise RuntimeError("no access_token in response")
    return j["access_token"]


def norm(t):
    t = re.sub(r"#\w+", " ", t or "").lower()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", t).split())


def groups(key):
    """{normalised title: [(views, video_id, title, privacy_unknown)]} for every
    title this channel uploaded more than once, newest copy last."""
    p = os.path.join(ROOT, "analytics", "videos_%s.json" % key)
    vids = json.load(io.open(p, encoding="utf-8"))["videos"]
    by = {}
    for vid, v in vids.items():
        last = (v.get("snapshots") or [{}])[-1]
        by.setdefault(norm(v["title"]), []).append(
            (last.get("views") or 0, vid, v["title"], v["published"][:10]))
    return {k: sorted(g, reverse=True) for k, g in by.items() if len(g) > 1}


def set_private(vid, token):
    req = urllib.request.Request(
        "%s/videos?part=status" % API,
        data=json.dumps({"id": vid, "status": {"privacyStatus": "private"}}).encode(),
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json"},
        method="PUT")
    with _open(req) as r:
        return json.loads(r.read()).get("status", {}).get("privacyStatus")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    dup = groups(a.key)
    if not dup:
        print("%s: no duplicate titles" % a.key)
        return 0
    # What a previous run already hid. The analytics file does not record
    # privacy, so without this every run would re-send a PUT for all of them at
    # 50 quota units each, out of the pool the uploads share.
    ledger_path = os.path.join(ROOT, "analytics", "hidden_%s.json" % a.key)
    try:
        already = set(json.load(io.open(ledger_path, encoding="utf-8")))
    except Exception:
        already = set()
    hide = []
    for k, g in sorted(dup.items()):
        keep = g[0]
        rest = [r for r in g[1:] if r[1] not in already]
        if not rest:
            continue
        print("\n%r - %d copies" % (keep[2][:58], len(g)))
        print("    keep    %s  %5d views  %s" % (keep[1], keep[0], keep[3]))
        for views, vid, title, pub in rest:
            print("    hide    %s  %5d views  %s" % (vid, views, pub))
            hide.append(vid)
    if already:
        print("\n%d already hidden by an earlier run" % len(already))
    print("%d videos to make private" % len(hide))
    if not hide:
        return 0
    if not a.apply:
        print("(dry run - pass --apply to do it)")
        return 0

    token = access_token()
    done = failed = 0
    for vid in hide:
        try:
            got = set_private(vid, token)
            print("  %s -> %s" % (vid, got), flush=True)
            done += 1
        except Exception as e:
            print("  %s FAILED: %s" % (vid, str(e)[:160]), flush=True)
            failed += 1
        time.sleep(0.4)
    if done:
        io.open(ledger_path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(sorted(already | set(hide)), indent=1))
    print("\nmade private: %d, failed: %d" % (done, failed))
    return 1 if failed and not done else 0


if __name__ == "__main__":
    sys.exit(main())
