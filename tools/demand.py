# -*- coding: utf-8 -*-
"""What people are actually typing into YouTube, per channel.

Every subject in this project has been chosen from what already did well on
these channels. That is a good signal and a closed loop: it can only ever
suggest more of what has already been made.

Search is the other half, and it is the half that keeps paying. Eight per cent
of FaRu Fact's views come from YouTube search, and unlike the Shorts feed - a
video is served for a few days and then never again - a video that answers a
search keeps being found for years. That is also where the watch hours are.

YouTube's own autocomplete is the demand signal, free and honest: it reflects
what people typed, not what an SEO blog thinks they typed.

    why did rome -> fall, convert to christianity, destroy jerusalem,
                    split in two, leave britain
    how to stop  -> overthinking, procrastinating, hiccups, crying

Seeds are chosen per channel from what that channel measurably converts on -
Rome for History, the viewer's own body for FaRu, the viewer's own situation
for Rise - so the demand this pulls is demand the channel can actually serve.

    python tools/demand.py            # all three, writes analytics/demand_*.json
    python tools/demand.py history
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analytics")

SEEDS = {
    "history": [
        "why did rome", "how did rome", "what did romans", "did romans really",
        "who invented", "why is it called", "what happened to the",
        "how did they build", "why do we still", "what did people do before",
        "how much did it cost to", "how long did it take to",
    ],
    "fun": [
        "why does my body", "what happens when you", "why do humans",
        "is it true that your", "why do we sleep", "what does your brain",
        "why do i always", "how much of your body", "what is in your",
        "why does food", "what happens if you stop", "how long can you",
    ],
    "us": [
        "how to stop", "why do i keep", "how to stay", "what to do when you",
        "is it too late to", "how do people who", "why am i so",
        "how to start when you", "what happens if you quit", "how long does it take to",
    ],
}

# Autocomplete returns song titles and channel names for loose seeds - "your
# body" came back as "your body is a wonderland". These are the give-aways.
JUNK = re.compile(
    r"\b(lyrics?|song|remix|feat|official video|full movie|episode \d+|"
    r"reaction|tiktok|shorts? compilation|mp3|download|karaoke|"
    r"season \d+|ep \d+|trailer)\b", re.I)


def suggest(q, timeout=30):
    u = ("https://suggestqueries.google.com/complete/search"
         "?client=firefox&ds=yt&q=" + urllib.parse.quote(q))
    r = urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}),
        timeout=timeout)
    return json.loads(r.read().decode("utf-8", "replace"))[1]


def harvest(seeds, deepen=True):
    """Seeds, then each seed with a letter appended - the standard way to widen
    autocomplete without a keyword tool. Ordered by how often a phrase turns
    up, because a phrase that several seeds lead to is a phrase with weight."""
    counts, order = {}, []
    queries = list(seeds)
    if deepen:
        # A few letters rather than all twenty-six: the long tail past the
        # first handful is mostly noise and it is twelve times the requests.
        for s in seeds:
            queries += ["%s %s" % (s, c) for c in "abcdehimprstw"]

    for q in queries:
        try:
            for phrase in suggest(q):
                p = phrase.strip().lower()
                if len(p) < 12 or JUNK.search(p):
                    continue
                if p not in counts:
                    order.append(p)
                counts[p] = counts.get(p, 0) + 1
        except Exception as e:
            print("  %-42s failed: %s" % (q[:42], str(e)[:60]), flush=True)
        time.sleep(0.4)          # be a polite guest on a free endpoint

    ranked = sorted(order, key=lambda p: (-counts[p], order.index(p)))
    return [{"query": p, "seen": counts[p]} for p in ranked]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channels", nargs="*", default=list(SEEDS))
    ap.add_argument("--shallow", action="store_true",
                    help="seeds only, no letter expansion")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    for k in [c for c in (a.channels or list(SEEDS)) if c in SEEDS]:
        print("\n=== %s" % k, flush=True)
        rows = harvest(SEEDS[k], deepen=not a.shallow)
        path = os.path.join(OUT, "demand_%s.json" % k)
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps({"queries": rows}, ensure_ascii=False, indent=1))
        print("  %d distinct searches -> %s" % (len(rows), os.path.basename(path)))
        for r in rows[:12]:
            print("     %2d seeds  %s" % (r["seen"], r["query"][:64]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
