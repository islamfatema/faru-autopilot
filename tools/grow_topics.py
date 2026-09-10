# -*- coding: utf-8 -*-
"""Write new documentary episodes, so the long-form cadence can be raised.

Watch hours are the gate. Not subscribers - those arrive on their own once the
Shorts work - but the 4,000 hours, and the measured relationship is blunt:

    History Explains   4 documentaries a week   90.7 watch hours in 28 days
    Rise With Fate     2 a week                 57.4
    FaRu Fact          2 a week                 19.5

Shorts contribute almost none of that. Seventy-five thousand views across the
three channels produced 167 hours between them; one twelve-minute documentary
watched a thousand times produces a hundred.

So Rise and FaRu should publish four a week like History does. They cannot,
because between them they hold twenty-two episodes - five weeks - and nothing
in this project writes new ones. grow.py grows the Shorts banks only. That gap
is why the cadence has never been raised.

This writes episodes in the same schema makeboard.py already reads: title,
angle, look, thumbnail lines, tags, and eight beats of 40-50 words each. The
title rules come from what actually happened to the four documentaries that
are published:

    The Empire That Ruled a Quarter of the World, Vanished in 30 Years   231
    Rome Did Not Fall in a Year. It Took 300.                             10
    Founders Over 40 Succeed More Often Than Founders in Their 20s         4
    Telling People Your Goal Makes You Less Likely To Do It               16

    python tools/grow_topics.py history --target 40
    python tools/grow_topics.py                      # all three

Env: OWNER_GEMINI_KEY, GEMINI_REQUEST_BUDGET (shared with the live app).
"""
import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import grow  # noqa: E402  - model discovery, request budget, backoff, parser

PER_REQUEST = 2          # eight beats each; two is what fits the output ceiling

BANKS = {
    "us": ("autopilot_us/longform/topics_us.json", "Rise With Fate",
           "long-form motivation for a US audience - one person's story or one "
           "body of evidence, told honestly, no shouting and no poster quotes"),
    "fun": ("autopilot_fun/longform/topics_fun.json", "FaRu Fact",
            "long-form about surprising true things, weighted towards the "
            "viewer's own body, food, sleep, money and the objects they use "
            "every day"),
    "history": ("autopilot_history/longform/topics_history.json",
                "History That Explains the World",
                "long-form history for a US audience - empires, money, "
                "inventions, and especially the past doing something we assume "
                "is modern"),
}

PROMPT = """Write {n} documentary episodes for a YouTube channel.

Channel: {name} - {brief}.

THE TITLE DECIDES EVERYTHING. Four episodes are published and their view counts
three days in were 231, 16, 10 and 4. The one that worked was called "The Empire
That Ruled a Quarter of the World and Vanished in 30 Years". The ones that did
not were called "Why Rome Actually Fell" and "The Truth About Motivation Nobody
Sells".

So every title must name something a person can picture and count - a number, a
span of years, a scale - and it must be something the episode actually says. Do
not write a category ("The Truth About X", "Why X Happened", "The Story of X").

Each episode is an object with exactly these keys:
  title    under 70 characters, concrete, carrying a number or a countable scale
  angle    one sentence on what this episode argues, not what it covers
  look     a scene for the thumbnail image - a place or object, never a person
  line1    2-3 words for the thumbnail, upper case
  line2    2-3 words for the thumbnail, upper case
  badge    "TRUE"
  tags     6-8 lowercase single words, no hashes
  beats    EXACTLY 8 strings, 40-55 words each, in order. Shorter than 20
           words is a fragment and is rejected.

The eight beats are the whole film, so they carry the work:
  1  open on the concrete scene, not on context. No "throughout history".
  2  the thing the viewer assumes, stated plainly
  3-4 what actually happened, with dates and numbers a viewer could check
  5  the turn - the part that is not in the popular version
  6  why it went the way it did, mechanism not moral
  7  what it means now, for the person watching, in their own life
  8  the honest limit - what this does NOT prove. No triumphant ending.

Every number must be real. If you are not sure of a figure, write the episode
without it rather than inventing one.

These titles already exist, do not repeat their subjects:
{titles}

Return ONLY a JSON array of {n} objects. No commentary."""


def valid(d, seen):
    if not isinstance(d, dict):
        return "not an object"
    for k in ("title", "angle", "look", "line1", "line2", "tags", "beats"):
        if k not in d:
            return "missing " + k
    if not isinstance(d["title"], str) or not (12 <= len(d["title"]) <= 75):
        return "title length %d" % len(str(d.get("title")))
    if grow.norm_title(d["title"]) in seen:
        return "duplicate subject"
    if not isinstance(d["beats"], list) or len(d["beats"]) != 8:
        return "beats count %d" % len(d.get("beats") or [])
    for b in d["beats"]:
        if not isinstance(b, str):
            return "a beat is not text"
        n = len(b.split())
        # Measured against the banks that already produce twelve-minute films:
        # the median beat is 25-27 words, so a floor of 25 was throwing away
        # half of what came back for matching the existing corpus exactly. The
        # ask stays high because a richer outline gives makeboard more to work
        # with; the floor only catches beats that are genuinely a fragment.
        if not (18 <= n <= 80):
            return "a beat runs %d words" % n
    if not isinstance(d["tags"], list) or not (4 <= len(d["tags"]) <= 10):
        return "tags count"
    # The lesson from the published four: a title naming a category collects
    # nothing. Require something countable in it.
    if not any(c.isdigit() for c in d["title"]) and not any(
            w in d["title"].lower() for w in
            ("quarter", "half", "twice", "every", "million", "billion",
             "thousand", "hundred", "first", "last", "only", "never", "more")):
        return "title names a category, not something countable"
    return None


def grow_bank(key, target, dry, gkey):
    rel, name, brief = BANKS[key]
    path = os.path.join(ROOT, rel)
    bank = json.load(io.open(path, encoding="utf-8"))
    start = len(bank)
    if start >= target:
        print("%s: %d episodes, already at %d" % (key, start, target))
        return 0

    seen = set(grow.norm_title(d["title"]) for d in bank)
    added, attempts = 0, 0
    while len(bank) < target and attempts < 10:
        attempts += 1
        need = min(PER_REQUEST, target - len(bank))
        titles = "\n".join("- " + d["title"] for d in bank[-40:])
        try:
            items = grow.parse_array(grow.gemini(PROMPT.format(
                n=need, name=name, brief=brief, titles=titles), gkey))
        except grow.BudgetSpent as e:
            print("  stopping: %s" % e, flush=True)
            break
        except Exception as e:
            print("  batch failed: %s" % str(e)[:170], flush=True)
            time.sleep(4)
            continue

        for d in items:
            why = valid(d, seen)
            if why:
                print("  reject (%s)" % why, flush=True)
                continue
            d = {"title": d["title"], "angle": d["angle"], "look": d["look"],
                 "line1": str(d["line1"])[:14].upper(),
                 "line2": str(d["line2"])[:14].upper(),
                 "badge": "TRUE",
                 "tags": [str(t).lower().lstrip("#") for t in d["tags"]][:8],
                 "beats": d["beats"]}
            bank.append(d)
            seen.add(grow.norm_title(d["title"]))
            added += 1
            print("  + %s" % d["title"][:64], flush=True)

        # Written after every batch: a run killed by the job timeout should
        # keep what it finished.
        if added and not dry:
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                json.dumps(bank, ensure_ascii=False, indent=1))
        time.sleep(2)

    print("%s: %d -> %d (+%d)%s" % (key, start, len(bank), added,
                                    " [dry]" if dry else ""), flush=True)
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channels", nargs="*", default=list(BANKS))
    ap.add_argument("--target", type=int, default=40,
                    help="grow each bank to at least this many episodes")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    gkey = (os.environ.get("OWNER_GEMINI_KEY") or "").strip()
    if not gkey:
        print("no OWNER_GEMINI_KEY - nothing to do")
        return 0

    picked = [k for k in (a.channels or list(BANKS)) if k in BANKS]
    # Fewest episodes first: the free tier runs out partway through, and the
    # channel closest to running dry should be the one that gets the requests.
    picked.sort(key=lambda k: len(json.load(io.open(
        os.path.join(ROOT, BANKS[k][0]), encoding="utf-8"))))
    share = max(1, grow.REQUEST_BUDGET // max(1, len(picked)))
    total = 0
    for n, k in enumerate(picked):
        grow._cap = share * (n + 1)
        try:
            total += grow_bank(k, a.target, a.dry, gkey)
        except Exception as e:
            print("%s FAILED: %s" % (k, str(e)[:200]), flush=True)
    print("TOTAL EPISODES ADDED %d" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
