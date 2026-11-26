# -*- coding: utf-8 -*-
"""Write a numbered run of Shorts where each one names the next.

Subscribers are the binding number on all three channels: 142,495 views have
produced 49 subscriber events, 0.34 per thousand, against 2 to 10 on a channel
that works. The placement test answered the easy half of it - where the ask
sits makes no difference - and its own verdict line said to question what is
being offered instead.

What is being offered is a surprising fact and then nothing. There is no
reason to expect the next one to be worth anything, so there is no reason to
subscribe. A numbered run is the cheapest answer to that: episode 3 ends by
naming episode 4, and following the channel is how you get it.

The machine already understands this. `series` and `series_n` change four
things in main_*.py - those scripts sort first, keep their own order, skip the
closing cards, and pass a gentler length gate - and fourteen episodes a
channel were hand-written for it in October. Not one ever published: every
fact in them had already gone out under another title, so the picker refused
them all as repeats, correctly. The shape was right and the material was
spent.

This writes new ones, against everything the bank already holds:

    python tools/series_gen.py fun --episodes 10 --name "Your Body Is Lying"
    python tools/series_gen.py history --episodes 10 --dry

Each episode is checked by the same `valid()` the daily refill uses, so a
series script obeys the caption rule like everything else, and by the same
duplicate-title and shared-wording checks, so it cannot repeat the channel.
"""
import argparse
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grow  # noqa: E402  - the refill's model calls, gates and dedup

ROOT = grow.ROOT

PROMPT = """You write %(count)d Shorts for %(name)s. They are ONE NUMBERED SERIES
called "%(series)s", and they are watched in order.

%(brief)s

%(length_rule)s

EVERY caption is at most 30 CHARACTERS as well as at most five words - they
are burned onto the screen and a longer line runs off the edge. Count the
characters, not only the words.

And the captions TOGETHER must come to at least 28 spoken words. Short
captions are not a short script: eight captions of four words is the shape,
not six of three.

WHAT MAKES THIS A SERIES AND NOT %(count)d SEPARATE VIDEOS:

  - every episode is about the same promise: %(promise)s
  - the LAST TWO captions of every episode except the final one name what is
    coming next, concretely. Not "follow for more" - the actual next subject,
    so that somebody who wants it has to come back. BOTH of those captions
    obey the caption rule above like every other one: at most five words, at
    most 30 characters, one line. For example:
        "Next: your blind spot."
        "You never see it."
  - the final episode's last two captions instead ask the viewer which one
    they did not believe.
  - no episode repeats a fact, a number or a phrase from another one.

Already on this channel - every one of these subjects is SPENT, and an episode
about any of them is wasted work:

%(titles)s

Answer with a JSON array of exactly %(count)d objects, in order, each:
  {"title": "...",
   "img": "a full photo brief: the concrete subject first, then the lighting
and the framing, at least 20 characters",
   "tags": ["lowercase", "single", "words", "three to fifteen"],
   "narration": "the whole thing as one paragraph",
   "phrases": ["...", "..."]}
Nothing before or after the array.
"""


THEME_PROMPT = """You are choosing the subject of a numbered run of Shorts for
%(name)s.

%(brief)s

Here is everything the channel has already made. Choose a run of about ten
videos that it has NOT made, that belongs on this channel, and that a viewer
would want the next one of:

%(titles)s

Answer with one JSON object and nothing else:
  {"name": "the series title, four words or fewer, no numbering",
   "promise": "one sentence: what every episode in the run has in common"}
"""


def choose_theme(cfg, titles, gkey):
    """Ask for a run the channel has not already made.

    A fixed list of themes in a workflow file runs out, and the day it runs
    out nothing says so - the job keeps succeeding and writes nothing. The
    model is already shown the whole bank for the duplicate check, so it can
    pick the gap itself.
    """
    raw = grow.gemini(THEME_PROMPT % {"name": cfg["name"], "brief": cfg["brief"],
                                      "titles": titles}, gkey)
    raw = raw.strip()
    i, j = raw.find("{"), raw.rfind("}")
    d = json.loads(raw[i:j + 1])
    name = str(d.get("name") or "").strip()
    promise = str(d.get("promise") or "").strip()
    if not name or not promise:
        raise ValueError("the model named no series")
    return name, promise


def bank_path(key):
    return os.path.join(ROOT, "autopilot_%s" % key, "scripts_%s.json" % key)


def load_bank(key):
    raw = json.load(io.open(bank_path(key), encoding="utf-8"))
    return (raw, raw["scripts"]) if isinstance(raw, dict) else (None, raw)


def save_bank(key, wrapper, scripts):
    out = wrapper if wrapper is None else dict(wrapper)
    if out is None:
        out = scripts
    else:
        out["scripts"] = scripts
    io.open(bank_path(key), "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, ensure_ascii=False, indent=1))


def next_series_number(scripts, name):
    """Series numbering is global per channel, not per name - the picker sorts
    on series_n alone, so two runs sharing a number would interleave."""
    used = [d.get("series_n") or 0 for d in scripts if d.get("series")]
    return max(used) + 1 if used else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("key", choices=["fun", "us", "history"])
    ap.add_argument("--episodes", type=int, default=10)
    ap.add_argument("--name", default="")
    ap.add_argument("--promise", default="")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    gkey = (os.environ.get("OWNER_GEMINI_KEY")
            or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not gkey:
        print("no Gemini key in OWNER_GEMINI_KEY")
        return 2

    cfg = grow.CHANNELS[a.key]
    wrapper, scripts = load_bank(a.key)
    done = grow.published_count(a.key, scripts)
    print("%s: %d scripts, %d published" % (a.key, len(scripts), done))

    floor, rule = grow.length_rule(a.key)
    grow._SPOKEN_FLOOR = floor

    # The whole bank, as far as it fits. The dedup checks every script the
    # channel has ever written, but the model only avoids what it is
    # shown - given the newest 400 of 1,393 it proposed eleven subjects
    # the channel had already published and one survived.
    recent = [d["title"] for d in scripts[-300:]]
    older = [d["title"] for d in scripts[:-300]]
    if len(older) > 700:
        older = random.sample(older, 700)
    titles = "\n".join("- " + t for t in recent + older)
    series, promise = a.name, a.promise
    if not series:
        try:
            series, promise = choose_theme(cfg, titles, gkey)
            print("the model chose: %s - %s" % (series, promise[:90]))
        except Exception as e:
            print("could not choose a theme (%s)" % str(e)[:120])
            return 1
    promise = promise or ("every episode overturns something the viewer is "
                          "sure about, on the same subject family")

    prompt = PROMPT % {"count": a.episodes, "name": cfg["name"], "series": series,
                       "brief": cfg["brief"], "length_rule": rule,
                       "promise": promise, "titles": titles}

    try:
        items = grow.parse_array(grow.gemini(prompt, gkey))
    except Exception as e:
        print("the model did not answer: %s" % str(e)[:200])
        return 1

    # The chain is the whole point, so the run has to be contiguous. Episode 3
    # ends by naming episode 4; if 4 is thrown out as a repeat and 5 is kept
    # and renumbered, episode 3 promises something that never arrives - which
    # is worse than not promising anything. So: judge them in order, and keep
    # the longest unbroken stretch that survived.
    seen_titles = {grow.norm_title(d["title"]) for d in scripts}
    seen_shingles = [grow.shingles(d.get("narration", "")) for d in scripts[-600:]]
    start_n = next_series_number(scripts, series)
    runs, cur = [], []
    for i, d in enumerate(items):
        why = grow.valid(d)
        if not why and grow.norm_title(d["title"]) in seen_titles:
            why = "this channel has published it"
        if not why and grow.too_similar(d.get("narration", ""), seen_shingles):
            why = "reuses wording already on the channel"
        if why:
            print("  episode %d rejected (%s)" % (i + 1, why))
            if cur:
                runs.append(cur)
                cur = []
            continue
        seen_titles.add(grow.norm_title(d["title"]))
        seen_shingles.append(grow.shingles(d.get("narration", "")))
        cur.append(d)
    if cur:
        runs.append(cur)
    kept = max(runs, key=len) if runs else []
    for n, d in enumerate(kept):
        d["series"] = "%s #%d" % (series, n + 1)
        d["series_n"] = start_n + n
    if kept:
        # The last one of the run was written expecting another after it. Its
        # closing two captions name an episode that is not coming, so they are
        # replaced with the close the final episode was meant to have.
        last = kept[-1]
        if len(last.get("phrases") or []) >= 4:
            last["phrases"] = last["phrases"][:-2] + ["Which one did you doubt?",
                                                      "Tell me below."]

    print("%d of %d episodes kept, as one unbroken run"
          % (len(kept), len(items)))
    for d in kept:
        print("   %-28s %s" % (d["series"], d["title"][:46]))
    if not kept:
        return 1
    # A run of two is not a series - it is two videos with an odd caption at
    # the end promising something that never arrives.
    if len(kept) < 4:
        print("Fewer than four survived, which is not a run worth promising. "
              "Nothing written.")
        return 1
    if a.dry:
        print("[dry] nothing written")
        return 0
    save_bank(a.key, wrapper, scripts + kept)
    print("written to %s" % bank_path(a.key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
