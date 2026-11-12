# -*- coding: utf-8 -*-
"""Bring over-long scripts into the band by dropping their most redundant line.

Length is the largest measured lever on these channels. At a matched video age
of 4-7 days, over 579 Shorts:

    21-30s   n= 90   median 36 views
    31-40s   n=130   median 32
    41-50s   n=305   median 21
    >50s     n= 52   median 19

and on the 49 days a channel published both a short one and a long one, the
short one won on 35 of them. The rotation now ranks 60-78 spoken words first
and tools/grow.py writes to that band. The problem is the bank already written:
of FaRu Fact's 611 question-shaped scripts - and a question title is what that
channel is ranked on before anything else - exactly **16** are in band. Four
days of stock. The other 595 outrank every in-band script and run 40-50
seconds.

308 of them are 79-90 words: over by one line. 159 come into band by dropping
a single caption and still keep eight.

Which line to drop is the whole question, and this does not ask a model - the
Gemini key is shared with the live app ([[faru-gemini-quota-shared]]) and a
rewrite pass over 595 scripts would starve it. It drops the line that repeats
its neighbours most: for each candidate, the share of its content words that
already appear in the caption before or after it. A line that says nothing new
is the line whose removal costs least.

A caption is not a unit of meaning here - a sentence is, and it often runs
across two or three captions. So only a caption that is a whole sentence
standing by itself may go: it ends on a full stop, the one before it ends on a
full stop, and the one after starts with a capital. Without that rule the first
version chose "empty.", "either." and "in time." - every one the tail of a
sentence that began in the previous caption.

Three more lines are never candidates:

  * the first  - it is the hook, and WEAK_HOOK was the most common diagnosis
    on all three channels
  * the last two - the payoff and the close, which is where the subscribe ask
    and the next-episode line live

Every original is written to analytics/condensed_<key>.json before anything is
changed, so the whole pass can be put back.

**What it actually found, 2026-11-12: 31 scripts across all three banks, not
the 159 the word counts suggested.** Three passes, each rejected by looking at
what it chose:

  1. redundancy alone, against the two neighbours -> 842 scripts, but it was
     dropping "empty.", "either.", "in time.", "tiny meteorites." - every one
     the tail of a sentence that began in the previous caption. A caption is
     not a unit of meaning here.
  2. whole sentences only -> 822, and now it was dropping "It's a tardigrade.",
     "A platypus.", "It's called chronostasis." - the reveal in each script. A
     reveal names the thing the script is about, so its words do appear nearby.
  3. whole sentences whose every content word is already on screen elsewhere,
     measured against the title and the whole script, with the last four
     captions untouchable -> 31, and all of them restate the title verbatim:
     "Earth's core is hotter than the Sun's surface.", "The Eiffel Tower grows
     in the summer."

So the scripts are dense. There is no spare line to cut in almost any of them,
and the way to an in-band bank is tools/grow.py writing to the band, not
trimming what is already written. Keeping this because the negative result is
worth not finding twice.

    python tools/condense.py --key fun                 # show what it would do
    python tools/condense.py --key fun --apply
"""
import argparse
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = {"fun": "autopilot_fun", "us": "autopilot_us", "history": "autopilot_history"}
LO, HI = 60, 78           # 30-39 seconds at the measured 2.0 words a second
MIN_CAPTIONS = 8          # below this a script stops being a script
KEEP_HEAD = 1             # the hook
KEEP_TAIL = 4             # the payoff, the turn into it, and the close
MIN_REDUNDANT = 1.0       # every content word already on screen elsewhere

_STOP = set(("the a an of in on at to for and or but is are was were be been "
             "it its this that these those your you yours we our they them "
             "with without from into over under by as so than then there here "
             "not no very just about more most can could will would has have "
             "had do does did what why how when where which who").split())


def content(line):
    """The words in a caption that carry meaning."""
    t = re.sub(r"[^A-Za-z0-9' ]", " ", str(line)).lower()
    return set(w for w in t.split() if w not in _STOP and len(w) > 2)


def phrases(d):
    return d.get("phrases") if d.get("phrases") is not None else d.get("lines")


def set_phrases(d, v):
    if d.get("phrases") is not None:
        d["phrases"] = v
    else:
        d["lines"] = v


def flat(p):
    """A caption may be a string or a list of two on-screen lines."""
    if isinstance(p, (list, tuple)):
        return " ".join(str(x) for x in p)
    return str(p)


def spoken(ps):
    return sum(len(flat(p).split()) for p in ps)


_ENDS = re.compile(r"[.!?][\"”')]?\s*$")


def standalone(ps, i):
    """Can caption i be removed without leaving a broken sentence?

    The first attempt scored captions on redundancy alone and chose to drop
    "empty.", "either.", "in time." and "tiny meteorites." - every one of them
    the tail of a sentence that began in the caption before it. A caption is
    not a unit of meaning on these channels; a sentence is, and it often runs
    across two or three captions.

    So a caption may only go if it is a whole sentence standing by itself: it
    ends on a full stop, the one before it ends on a full stop, and the one
    after it starts a new sentence with a capital. Then what is left still
    reads.
    """
    me = flat(ps[i]).strip()
    if not _ENDS.search(me):
        return False
    if i > 0 and not _ENDS.search(flat(ps[i - 1]).strip()):
        return False
    if i + 1 < len(ps):
        nxt = flat(ps[i + 1]).strip()
        if nxt and not (nxt[0].isupper() or nxt[0].isdigit() or nxt[0] in "\"“'"):
            return False
    return True


def redundancy(ps, i, title=""):
    """How much of caption i already appears in the one before or after it.

    1.0 means it says nothing its neighbours do not. A line carrying no content
    words at all is not a candidate - that is a fragment, not a spare sentence -
    so it scores -1 and is never chosen.
    """
    own = content(flat(ps[i]))
    if not own:
        return -1.0
    # Against the whole script and the title, not just the two neighbours.
    # "It uses about 20% of your total body energy" repeats the title, which a
    # neighbour-only comparison cannot see - and the title is on screen as the
    # first thing the viewer reads.
    near = content(title or "")
    for j, p in enumerate(ps):
        if j != i:
            near |= content(flat(p))
    return len(own & near) / float(len(own))


def condense(ps, title=""):
    """Drop the most redundant middle caption until in band. (new, dropped)."""
    ps = list(ps)
    dropped = []
    while spoken(ps) > HI and len(ps) - 1 >= MIN_CAPTIONS:
        lo = KEEP_HEAD
        hi = len(ps) - KEEP_TAIL
        if hi <= lo:
            break
        # Only a line that is nearly all repetition. Ranking candidates and
        # taking the best one chose "It's a tardigrade.", "A platypus." and
        # "It's called chronostasis." - the reveal in each of those scripts.
        # They scored high because a reveal names the thing the rest of the
        # script is about, so its words do appear nearby. A line worth losing
        # is one where *every* content word is already on screen somewhere
        # else, which a reveal's never is.
        cand = [j for j in range(lo, hi)
                if standalone(ps, j) and redundancy(ps, j, title) >= MIN_REDUNDANT]
        if not cand:
            break
        i = max(cand, key=lambda j: (redundancy(ps, j, title),
                                     -len(flat(ps[j]).split())))
        dropped.append(ps.pop(i))
        if spoken(ps) < LO:            # went under - put it back and stop
            ps.insert(i, dropped.pop())
            break
    return ps, dropped


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=sorted(DIRS))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 means every one")
    a = ap.parse_args()

    d = os.path.join(ROOT, DIRS[a.key])
    files = sorted(glob.glob(os.path.join(d, "*.json")) +
                   glob.glob(os.path.join(d, "bank", "*.json")))
    ledger = []
    changed = shown = 0
    for path in files:
        try:
            data = json.load(io.open(path, encoding="utf-8"))
        except Exception:
            continue
        items = data if isinstance(data, list) else (
            data.get("items") or data.get("scripts") or [])
        if not isinstance(items, list):
            continue
        dirty = False
        for it in items:
            if not isinstance(it, dict):
                continue
            ps = phrases(it)
            if not ps or spoken(ps) <= HI or len(ps) <= MIN_CAPTIONS:
                continue
            if a.limit and changed >= a.limit:
                break
            new, dropped = condense(ps, it.get("title", ""))
            if not dropped or spoken(new) > HI:
                continue
            ledger.append({"title": it.get("title", ""),
                           "was_words": spoken(ps), "now_words": spoken(new),
                           "dropped": [flat(x) for x in dropped]})
            if shown < 8:
                shown += 1
                print("  %-52s %3d -> %3d words, dropped: %s"
                      % (re.sub(r"#\w+", "", it.get("title", "")).strip()[:52],
                         spoken(ps), spoken(new), flat(dropped[0])[:60]))
            if a.apply:
                set_phrases(it, new)
                dirty = True
            changed += 1
        if dirty:
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                json.dumps(data, ensure_ascii=False, indent=1))

    print("\n%d scripts brought into %d-%d words%s"
          % (changed, LO, HI, "" if a.apply else "  (nothing written - pass --apply)"))
    if a.apply and ledger:
        p = os.path.join(ROOT, "analytics", "condensed_%s.json" % a.key)
        old = []
        if os.path.exists(p):
            try:
                old = json.load(io.open(p, encoding="utf-8"))
            except Exception:
                old = []
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(old + ledger, ensure_ascii=False, indent=1))
        print("every dropped line recorded in analytics/condensed_%s.json" % a.key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
