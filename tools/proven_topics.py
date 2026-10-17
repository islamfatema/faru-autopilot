# -*- coding: utf-8 -*-
"""Make documentaries out of the Shorts the channel already proved.

The documentary topics are invented from a brief. The Shorts are not - the
channel has published hundreds and YouTube has told us, for each one, how
many people wanted it. Those two facts have never been connected.

They should be. The fan-funding gate needs 3,000 public long-form watch hours
and the documentaries take about fourteen views each, while History's Shorts
on "Ancient Romans Used Lead Pipes for Drinking Water" took 1,043 and "Why
America Still Uses Fahrenheit" took 1,069. Those are not guesses about what
an audience wants; they are measurements, on this channel, of this audience.
A twelve-minute film on a subject a Short already proved is the one long-form
topic that comes with evidence attached.

It is also the only honest way to make a Short's success compound. A Short
cannot be re-uploaded and its views do not count toward the watch-hour gate.
Its subject can be used again.

So: take the channel's best-performing Shorts, drop the ones whose subject is
already in the documentary bank, and write a documentary topic for each -
same schema as the rest, marked `lead` so the picker takes them first, with
the measurement kept in the angle so nobody later wonders why these were
chosen.

    python tools/proven_topics.py history --check
    python tools/proven_topics.py history --apply --limit 6

Env: OWNER_GEMINI_KEY, which writes the angle and the beats.
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import grow  # noqa: E402

MIN_VIEWS = 400          # a Short the feed actually carried
PER_REQUEST = 3

PROMPT = """Turn each of these proven YouTube Shorts into a documentary episode
for the channel "{name}".

Each Short below already found an audience on this channel - the view count is
real and is given. The documentary is the long version of that same subject:
same curiosity, far more of it. Do not change the subject to something
adjacent.

For each one return an object with:
  "title":  the documentary title. NOT the Short's title - a longer film needs
            a bigger promise. Under 70 characters, no clickbait, no colon-heavy
            "The Untold Story Of" phrasing.
  "angle":  two sentences on what this episode argues and what evidence it
            uses. Say what is physically there to look at - objects, places,
            documents - because the film is built from images.
  "look":   one sentence describing a real scene to open on, for the thumbnail
            and the first shot. A place or an object, with light and time of
            day. No text, no people's faces.
  "line1":  two or three words for the thumbnail, upper case
  "line2":  two or three words for the thumbnail, upper case
  "badge":  one word, upper case, such as TRUE or 1923
  "tags":   8 to 12 lower-case search tags
  "beats":  10 to 14 one-sentence beats that carry the episode start to finish.
            Open on a specific moment - a person, a date, a place - never on a
            general statement. Each beat must be something that happened or
            something that can be shown, not a theme.

Everything must be true and checkable. If the Short's claim is narrower than a
film needs, widen it with surrounding history, never by inventing.

The Shorts:
{items}

Return ONLY a JSON array of {n} objects. No commentary."""


def proven_shorts(key, min_views):
    """The channel's best Shorts, best first, one per subject."""
    p = os.path.join(ROOT, "analytics", "videos_%s.json" % key)
    vids = json.load(io.open(p, encoding="utf-8"))["videos"]
    rows = []
    for v in vids.values():
        if v.get("kind") != "short":
            continue
        s = v.get("snapshots") or []
        if not s:
            continue
        views = s[-1].get("views") or 0
        if views < min_views:
            continue
        rows.append((views, re.sub(r"#\w+", "", v["title"]).strip()))
    rows.sort(reverse=True)
    # One per subject: two Shorts about Fahrenheit are one documentary.
    seen, out = [], []
    for views, title in rows:
        words = set(w for w in re.sub(r"[^a-z0-9 ]", " ", title.lower()).split()
                    if len(w) > 3)
        # Two words in common, or one distinctive one: "Why America Still
        # Uses Fahrenheit" and "Why Fahrenheit Freezes at 32 Degrees" share
        # only "fahrenheit" and are plainly one film.
        if any(len(words & s) >= 2 or any(len(w) > 6 for w in (words & s))
               for s in seen):
            continue
        seen.append(words)
        out.append((views, title))
    return out


def already_covered(key):
    """Word sets of the documentary topics that exist, to avoid repeating one."""
    d = os.path.join(ROOT, "autopilot_%s" % key, "longform")
    out = []
    import glob
    for f in glob.glob(os.path.join(d, "topics*.json")):
        try:
            for t in json.load(io.open(f, encoding="utf-8")):
                out.append(set(w for w in re.sub(r"[^a-z0-9 ]", " ",
                                                 (t.get("title") or "").lower()).split()
                               if len(w) > 3))
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", choices=["history", "us", "fun"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--min-views", type=int, default=MIN_VIEWS)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    name = {"history": "History That Explains the World",
            "us": "Rise With Fate", "fun": "FaRu Fact"}[a.channel]
    covered = already_covered(a.channel)
    proven = proven_shorts(a.channel, a.min_views)
    todo = []
    for views, title in proven:
        words = set(w for w in re.sub(r"[^a-z0-9 ]", " ", title.lower()).split()
                    if len(w) > 3)
        if any(len(words & c) >= 2 or any(len(w) > 6 for w in (words & c))
               for c in covered):
            continue
        todo.append((views, title))
    print("%s: %d Shorts over %d views, %d of them not already a documentary"
          % (name, len(proven), a.min_views, len(todo)))
    todo = todo[:a.limit]
    for views, title in todo:
        print("    %5d views  %s" % (views, title[:62]))
    if not todo:
        return 0
    if not a.apply:
        print("\n(listing only - pass --apply to write them)")
        return 0

    gkey = (os.environ.get("OWNER_GEMINI_KEY") or "").strip()
    if not gkey:
        raise SystemExit("OWNER_GEMINI_KEY is not set")

    path = os.path.join(ROOT, "autopilot_%s" % a.channel, "longform",
                        "topics_%s.json" % a.channel)
    bank = json.load(io.open(path, encoding="utf-8"))
    added = 0
    for i in range(0, len(todo), PER_REQUEST):
        batch = todo[i:i + PER_REQUEST]
        items = "\n".join("- %r (%d views on this channel)" % (t, v)
                          for v, t in batch)
        try:
            got = grow.parse_array(grow.gemini(
                PROMPT.format(name=name, items=items, n=len(batch)), gkey))
        except Exception as e:
            print("  batch failed: %s" % str(e)[:150])
            continue
        for obj, (views, short_title) in zip(got, batch):
            if not isinstance(obj, dict) or not obj.get("title") or not obj.get("beats"):
                print("  rejected: incomplete episode")
                continue
            if len(obj.get("beats") or []) < 8:
                print("  rejected (%d beats): %s" % (len(obj["beats"]),
                                                     obj["title"][:44]))
                continue
            obj["lead"] = True
            obj["angle"] = ("%s  [Chosen because this channel's Short on the "
                            "same subject took %d views - measured demand, not "
                            "a guess.]" % (obj.get("angle", ""), views))
            bank.insert(0, obj)
            added += 1
            print("  ADDED  %s   (from a %d-view Short)" % (obj["title"][:52], views))
    if added:
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(bank, ensure_ascii=False, indent=1))
    print("\nwrote %d episodes built on proven subjects, marked lead" % added)
    return 0


if __name__ == "__main__":
    sys.exit(main())
