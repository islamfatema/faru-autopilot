# -*- coding: utf-8 -*-
"""How many Shorts this channel still owes today. Prints one number.

The day's target is a number of videos, and it has been carried by a list of
cron times - which is not the same thing. GitHub skips a newly added schedule
for a day or more every single time one is added here, and a free-tier cron
can queue an hour or two behind its slot or not run at all. Each miss is
silent: the workflow simply does not start, so nothing is red and the day is
just short.

So the run asks instead of assuming: count what this channel has actually
published since midnight UTC, subtract it from the target, and make up the
difference - capped, so a day of missed slots does not dump ten videos into
one hour and so an unreadable API cannot cause a flood.

    python tools/remaining_today.py --key us --target 10 --cap 3

Reads the local ledger first, which is committed after every run and is what
survives a spent API quota, and tops it up with the channel's own uploads
playlist when a token is available. The two are unioned, never trusted alone:
the ledger can miss an upload that happened in a run that died before its
commit, and the API can be unreadable exactly when the quota is gone.
"""
import argparse
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"
TOKEN_ENV = {"us": "YT_REFRESH_TOKEN_US", "fun": "YT_REFRESH_TOKEN",
             "history": "YT_REFRESH_TOKEN_HISTORY"}


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def from_analytics(key):
    """Videos this channel published today, as the analytics snapshot saw it.

    A day behind by design, so it is only ever a floor - never a reason to
    publish less than the ledger already proves.
    """
    p = os.path.join(ROOT, "analytics", "videos_%s.json" % key)
    try:
        d = json.load(io.open(p, encoding="utf-8"))["videos"]
    except Exception:
        return 0
    t = today()
    return sum(1 for v in d.values() if (v.get("published") or "").startswith(t))


def from_api(key):
    """What the channel itself says went out today. None when unreadable."""
    rt = os.environ.get(TOKEN_ENV.get(key, ""), "").strip()
    if not rt:
        return None
    try:
        body = urllib.parse.urlencode({"refresh_token": rt}).encode()
        with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body),
                                    timeout=45) as r:
            tok = json.load(r)["access_token"]
        hdr = {"Authorization": "Bearer " + tok}

        def get(url):
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr),
                                        timeout=45) as r:
                return json.load(r)

        ch = get(API + "/channels?part=contentDetails&mine=true")
        up = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        j = get(API + "/playlistItems?part=contentDetails&maxResults=50&playlistId=" + up)
        t = today()
        return sum(1 for it in j.get("items", [])
                   if (it["contentDetails"].get("videoPublishedAt") or "").startswith(t))
    except Exception as e:
        print("could not read the channel (%s)" % str(e)[:80], file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--target", type=int, default=10)
    ap.add_argument("--cap", type=int, default=3)
    a = ap.parse_args()

    done = from_analytics(a.key)
    live = from_api(a.key)
    cap = a.cap
    if live is not None:
        done = max(done, live)
    else:
        # The channel could not be read, and the analytics file is a day
        # behind, so "0 published today" is not a fact - it is the absence of
        # one. Catching up on a number that might be wrong, ten times a day,
        # is how a shared upload quota gets spent in an afternoon. Take one.
        cap = 1
    left = max(0, a.target - done)
    # The cap is what stops an unreadable channel, or a genuinely missed day,
    # from putting the whole target out in one hour - which is both the worst
    # shape for the feed and the fastest way to spend the shared upload quota.
    print(min(left, cap))
    print("%s: %d of %d published today, %d left, this run takes %d"
          % (a.key, done, a.target, left, min(left, cap)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
