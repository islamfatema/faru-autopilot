# -*- coding: utf-8 -*-
"""Lengthen the scripts already in the banks so they clear the 30 second floor.

Fatema's requirement is plain: no video under 30 seconds. The publisher now
enforces it - worth_publishing() refuses anything under 78 spoken words rather
than post another twelve second clip. That is the right rule, and applying it
revealed the real damage:

    us        bank  685   passes the 30s gate:  1
    fun       bank  707   passes the 30s gate: 15
    history   bank  616   passes the 30s gate:  6

Twenty-two usable scripts against thirty videos a day. Every channel runs dry
inside a day and goes silent, which is worse than the short videos were.

Writing 1,900 replacement scripts is not the answer - the existing ones are
sound, they are simply too short. Each already carries the thing that is hard to
produce: a title that overturns something the viewer believes. So this expands
what is there rather than inventing more. One request carries several scripts,
so a run repairs far more than a generating run could, and the subjects the
channels already rank for are kept.

The first live run repaired nothing at all. Every batch came back as:

    batch failed: Expecting ',' delimiter: line 71 column 4 (char 3334)

which was my fault - the prompt asked for captions split with a backslash-n and
the model obliged with a real newline inside a JSON string, which is not legal
JSON, and one character killed a batch of eight finished scripts. Captions are
now requested as lists of lines, so there is no escape sequence to get wrong,
and the parser repairs raw newlines anyway before giving up.

Rules it holds to:
  - the title, tags and image prompt are never touched, so a script that has
    already been published stays recognisable and the ledger stays valid
  - published scripts are skipped entirely; there is no point paying for a
    rewrite of something that cannot go out again
  - anything that comes back failing grow.valid() leaves the original in place
  - the bank is written after every batch, so a run that is cut short keeps
    everything it finished

    python tools/expand.py us --limit 400
    python tools/expand.py            # all three, budget split evenly

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

import grow  # noqa: E402  - reuses the model discovery, budget and validator

# Five fits inside the 8k output token ceiling with room to spare. Eight came
# back truncated often enough to lose whole batches.
PER_REQUEST = 5


def spoken(d):
    return sum(len((p or "").replace("\n", " ").split()) for p in (d.get("phrases") or []))


def too_short(d):
    return spoken(d) < 78 or len(d.get("phrases") or []) < 10


PROMPT = """You rewrite scripts for a YouTube Shorts channel called "{name}".

{brief}

Each script below is good but TOO SHORT - the finished video runs about twelve
seconds, and the channel now refuses anything under thirty. Rewrite each one so
it runs 30-38 seconds, keeping what it is about.

Hard rules for every script:
- Keep "title", "tags" and "img" EXACTLY as given. Do not reword them.
- Rewrite "phrases": 10 to 13 captions, 80 to 100 spoken words in total.
  Never fewer than 78 words - that is a hard floor, not a target.
- Each caption is a LIST of one or two short strings, one per line on screen.
  No single line over 34 characters.
  Example: ["You were told", "to work harder."]
- Rewrite "narration" to match the new captions, 80 to 100 words.

Hard rules for the shape - this is what makes the extra seconds worth watching:
- Caption 1 states the belief the viewer already holds. No throat clearing, no
  "did you know", no greeting. Straight into it.
- HOLD THE ANSWER. Captions 2 to 4 build the tension. Do not resolve early.
- The middle carries one concrete, checkable detail - a number, a date, a name
  of a place, something a viewer could look up. This is what makes a comment.
- Near the end, one thing the viewer can do today, phrased as an instruction.
- The last caption is a question worth arguing with. Not "what do you think".

Do not pad. Extra words that say nothing lose the viewer faster than a short
video does. Every added caption must carry new information.

Scripts to rewrite:
{items}

Return ONLY a JSON array of {n} objects, in the same order, each with keys:
title, tags, img, narration, phrases. No markdown fence, no commentary.
"""


def parse_lenient(raw):
    """grow.parse_array, but survives a real newline inside a string.

    The model is asked for captions as lists of lines precisely so this cannot
    happen. It happened anyway on every request of the first live run, and a
    single stray newline destroyed a batch of finished scripts along with the
    quota that bought them.
    """
    try:
        return grow.parse_array(raw)
    except Exception:
        pass
    i, j = raw.find("["), raw.rfind("]")
    if i < 0 or j < 0:
        raise ValueError("no JSON array in response")
    out, instring, escaped = [], False, False
    for ch in raw[i:j + 1]:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            instring = not instring
        if instring and ch == "\n":
            out.append("\\n")          # the bug, escaped the way it should be
            continue
        if instring and ch == "\r":
            continue
        out.append(ch)
    return json.loads("".join(out))


def join_lines(d):
    """Captions arrive as lists of lines; the renderer wants one string each."""
    caps = d.get("phrases")
    if isinstance(caps, list):
        d["phrases"] = ["\n".join(str(x) for x in c) if isinstance(c, list) else c
                        for c in caps]
    return d


def load_published(key):
    p = os.path.join(ROOT, grow.CHANNELS[key]["dir"], "published_%s.json" % key)
    try:
        return set(grow.norm_title(t) for t in json.load(io.open(p, encoding="utf-8")))
    except Exception:
        return set()


def expand(key, limit, dry, gkey):
    cfg = grow.CHANNELS[key]
    path = os.path.join(ROOT, cfg["dir"], cfg["bank"])
    bank = json.load(io.open(path, encoding="utf-8"))
    published = load_published(key)

    before = sum(1 for d in bank if not too_short(d))
    todo = [i for i, d in enumerate(bank)
            if too_short(d) and grow.norm_title(d["title"]) not in published]
    print("%s: %d scripts, %d already clear 30s, %d unpublished and too short"
          % (key, len(bank), before, len(todo)), flush=True)
    if not todo:
        return 0

    todo = todo[:limit]
    fixed = 0
    for start in range(0, len(todo), PER_REQUEST):
        idxs = todo[start:start + PER_REQUEST]
        items = json.dumps([bank[i] for i in idxs], ensure_ascii=False, indent=1)
        prompt = PROMPT.format(name=cfg["name"], brief=cfg["brief"],
                               items=items, n=len(idxs))
        try:
            out = parse_lenient(grow.gemini(prompt, gkey))
        except grow.BudgetSpent as e:
            print("  stopping: %s" % e, flush=True)
            break
        except Exception as e:
            print("  batch failed: %s" % str(e)[:180], flush=True)
            time.sleep(4)
            continue

        # The model is asked to return them in order, but it is not trustworthy
        # about that, so match on the title it was told to keep unchanged.
        by_title = {}
        for d in out:
            if isinstance(d, dict) and isinstance(d.get("title"), str):
                by_title[grow.norm_title(d["title"])] = d

        for i in idxs:
            orig = bank[i]
            cand = by_title.get(grow.norm_title(orig["title"]))
            if cand is None:
                continue
            cand = join_lines(dict(cand))
            # Keep the parts that must not drift, whatever came back.
            cand = {"title": orig["title"], "tags": orig["tags"], "img": orig["img"],
                    "narration": cand.get("narration"), "phrases": cand.get("phrases")}
            why = grow.valid(cand)
            if why:
                print("  keep original (%s)" % why, flush=True)
                continue
            bank[i] = cand
            fixed += 1

        # Written after every batch. A run killed by the job timeout once threw
        # away 113 finished scripts because the only write was at the end.
        if fixed and not dry:
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                json.dumps(bank, ensure_ascii=False, indent=1))
        print("  %d/%d repaired so far" % (fixed, len(todo)), flush=True)
        time.sleep(2)

    after = sum(1 for d in bank if not too_short(d))
    print("%s: clears 30s %d -> %d (+%d)%s"
          % (key, before, after, fixed, " [dry]" if dry else ""), flush=True)
    return fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channels", nargs="*", default=list(grow.CHANNELS))
    ap.add_argument("--limit", type=int, default=400,
                    help="most scripts to repair per channel this run")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    gkey = (os.environ.get("OWNER_GEMINI_KEY") or "").strip()
    if not gkey:
        print("no OWNER_GEMINI_KEY - nothing to do")
        return 0

    picked = [k for k in (a.channels or list(grow.CHANNELS)) if k in grow.CHANNELS]
    # Split the request budget evenly, otherwise the first channel spends the
    # whole allowance and the other two stay stuck at a day of runway.
    share = max(1, grow.REQUEST_BUDGET // max(1, len(picked)))
    total = 0
    for n, k in enumerate(picked):
        grow._cap = share * (n + 1)
        try:
            total += expand(k, a.limit, a.dry, gkey)
        except Exception as e:
            print("%s FAILED: %s" % (k, str(e)[:200]), flush=True)
    print("TOTAL REPAIRED %d (budget %d requests)" % (total, grow.REQUEST_BUDGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
