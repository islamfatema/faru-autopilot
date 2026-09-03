# -*- coding: utf-8 -*-
"""Keep every channel's script bank ahead of what it publishes.

The channels were posting 10 videos a day from banks of 64-93 scripts, so the
rotation wrapped inside a week and the same video went up four times. YouTube
stops showing a channel that does that, which is what flattened the views.

Cutting the posting rate fixed the symptom. This fixes the cause: the bank grows
faster than it is consumed, so the rotation never comes back around. Each run
asks Gemini for new scripts, shows it every title already in the bank so it does
not repeat one, and refuses anything that comes back too similar to existing
material.

    python tools/grow.py us [--target 400] [--dry]

Posting never depends on this. It writes to the bank between runs; if Gemini is
down the bank simply does not grow that day and the channels keep publishing.
"""
import argparse
import io
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CHANNELS = {
    "us": {
        "dir": "autopilot_us",
        "bank": "scripts_us.json",
        "name": "Rise With Fate",
        "brief": (
            "Short-form motivation for a US audience. Direct, warm, spoken by a "
            "deep male narrator. Second person - talk to one person, not a crowd. "
            "No religion, no politics, no named people. Earned, not shouty."
        ),
    },
    "fun": {
        "dir": "autopilot_fun",
        "bank": "scripts_fun.json",
        "name": "FaRu Facts",
        "brief": (
            "Short-form surprising facts in English for a US audience. One fact "
            "per video, explained so the viewer understands WHY it is true, not "
            "just that it is. Verifiable, mainstream-sourced facts only - no "
            "urban legends, no 'scientists say', no health or medical claims."
        ),
    },
    "history": {
        "dir": "autopilot_history",
        "bank": "scripts_history.json",
        "name": "History That Explains the World",
        "brief": (
            "Short-form history for a US audience: a past event that explains "
            "something the viewer sees today. Calm documentary voice. Accurate "
            "and specific - real dates, real places. No conspiracy framing, no "
            "moralising, no living political figures."
        ),
    },
}

BATCH = 5          # scripts per request; small batches keep quality up
GROW_PER_RUN = 15  # comfortably more than the 10 a day a channel publishes
HARD_CAP = 1200

# The app and this generator share one free Gemini key, and a free key has a
# daily request quota. Running this without a ceiling drained it and left the
# live app unable to answer a customer - the generator starving the product is a
# far worse outcome than a bank that grows slowly. Spend a fixed slice and stop.
REQUEST_BUDGET = int(os.environ.get("GEMINI_REQUEST_BUDGET", "40"))
_spent = 0
_throttled = 0   # consecutive requests that only ever came back 429
_cap = REQUEST_BUDGET   # raised one channel's share at a time, so each gets a turn

# Preference order. Hardcoding names has bitten this project before - model ids
# are retired without warning and every call starts returning 404 - so this is
# only a preference and the real list is discovered from the API at startup.
PREFER = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-3.5-flash",
          "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]
_models = []


# ---------------------------------------------------------------- gemini
def discover(key):
    """Ask the API which models this key can actually use."""
    global _models
    if _models:
        return _models
    try:
        u = ("https://generativelanguage.googleapis.com/v1beta/models"
             "?pageSize=200&key=" + key)
        with urllib.request.urlopen(u, timeout=60) as r:
            d = json.load(r)
        live = set()
        for m in d.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                live.add(m["name"].split("/")[-1])
        _models = [m for m in PREFER if m in live]
        # anything flash-shaped is an acceptable fallback if none of the
        # preferred names survived
        if not _models:
            _models = sorted(m for m in live
                             if "flash" in m and not any(
                                 x in m for x in ("image", "tts", "thinking", "omni")))
        print("  models: %s" % ", ".join(_models[:4]), flush=True)
    except Exception as e:
        print("  model discovery failed (%s), using preferences" % str(e)[:90], flush=True)
        _models = list(PREFER)
    return _models


class BudgetSpent(Exception):
    """The share of the daily Gemini quota this tool is allowed has run out."""


def gemini(prompt, key, timeout=180):
    global _spent, _throttled
    if _spent >= _cap:
        raise BudgetSpent("request budget reached (%d of %d used)" % (_spent, REQUEST_BUDGET))
    # A per-minute limit is worth waiting out. A spent daily quota is not, and
    # the two look identical from the status code - so after a few requests that
    # only ever come back rate limited, stop rather than sleep through the rest
    # of the job for nothing.
    if _throttled >= 3:
        raise BudgetSpent("rate limited on %d requests in a row - quota looks spent "
                          "for today" % _throttled)
    _spent += 1
    last = ""
    for model in discover(key):
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 1.0, "maxOutputTokens": 8192},
        }).encode("utf-8")
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               "%s:generateContent?key=%s" % (model, key))
        # The free tier limits requests per minute, and a 429 is a "wait", not a
        # failure - dropping to the next model on one just burns the quota faster.
        rate_limited = False
        for wait in (0, 20, 45):
            if wait:
                print("  rate limited, waiting %ds" % wait, flush=True)
                time.sleep(wait)
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    d = json.load(r)
                _throttled = 0
                return d["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                last = "%s: HTTP %s" % (model, e.code)
                if e.code != 429:
                    break
                rate_limited = True
            except Exception as e:
                last = "%s: %s" % (model, str(e)[:120])
                break
        print("  gemini %s" % last, flush=True)
        if rate_limited:
            _throttled += 1
    raise RuntimeError("all gemini models failed: " + last)


# ---------------------------------------------------------------- dedup
def norm_title(t):
    t = re.sub(r"#\w+", " ", t or "")
    t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
    return " ".join(t.split())


def shingles(text, n=5):
    w = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split()
    return set(tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1)))


def too_similar(cand, existing_shingles, thresh=0.18):
    """Reject a script that reuses a run of wording from one already in the bank.

    A shared five-word run is not a coincidence in writing this short, and near
    duplicates are what got the channels suppressed in the first place.
    """
    s = shingles(cand)
    if not s:
        return True
    for other in existing_shingles:
        if not other:
            continue
        overlap = len(s & other) / float(min(len(s), len(other)))
        if overlap >= thresh:
            return True
    return False


# ---------------------------------------------------------------- validation
def valid(d):
    if not isinstance(d, dict):
        return "not an object"
    for k in ("title", "tags", "img", "narration", "phrases"):
        if k not in d:
            return "missing " + k
    if not isinstance(d["title"], str) or not (10 <= len(d["title"]) <= 95):
        return "title length"
    if not isinstance(d["tags"], list) or not (3 <= len(d["tags"]) <= 15):
        return "tags count"
    if any(not isinstance(t, str) or not t or " " in t for t in d["tags"]):
        return "tag format"
    if not isinstance(d["img"], str) or len(d["img"]) < 20:
        return "img prompt"
    words = len((d.get("narration") or "").split())
    if not (35 <= words <= 110):
        return "narration %d words" % words
    if not isinstance(d["phrases"], list) or not (8 <= len(d["phrases"]) <= 13):
        return "phrases count %d" % len(d.get("phrases") or [])
    # The finished video is these captions read aloud. At roughly 2.6 words a
    # second, under ~55 words lands below 22 seconds - which is where every
    # video published so far has been sitting.
    spoken = sum(len(p.replace("\n", " ").split()) for p in d["phrases"])
    if spoken < 55:
        return "only %d spoken words - the video would run under 22s" % spoken
    for p in d["phrases"]:
        if not isinstance(p, str) or not p.strip():
            return "empty phrase"
        for line in p.split("\n"):
            if len(line) > 34:
                return "caption line too long: %r" % line[:40]
    return None


PROMPT = """You write scripts for a YouTube Shorts channel called "{name}".

{brief}

Here are real scripts from the channel so you can match the format and voice
exactly. Copy the STRUCTURE, never the content:

{examples}

Write {n} NEW scripts.

THE MOST IMPORTANT RULE - what separates this channel's hits from its flops.

Every script must OVERTURN AN ASSUMPTION the viewer already holds, and the title
must contain the collision. This is not a style preference; it is what the
channel's own numbers say. Its best performing videos:

  "Sharks Existed Before Trees"                    732 views
  "The Ottoman Empire Existed Until 1922"        1,043 views
  "Oxford University Is Older Than the Aztec Empire" 991 views
  "You Will Never Feel Ready"                      320 views

Its worst, all published the same way on the same channel:

  "Penguins Can Drink Saltwater"                      0 views
  "Napoleon Was Once Attacked by Rabbits"             0 views
  "Fall Seven Times, Stand Up Eight"                  1 view

The losers are true and mildly interesting. The winners tell you that something
you were sure of is wrong. "Sharks are older than trees" works because everyone
assumes trees came first. "Penguins drink saltwater" contradicts nothing, so
nobody stops scrolling.

So for each script, before writing it, answer privately: what does the viewer
currently believe, and how does this fact collide with it? If there is no
collision, pick a different fact. Prefer comparisons - older than, longer than,
survived past, closer than - because a comparison makes the collision explicit
in the title itself.

THE SHAPE OF THE CAPTIONS - this is what decides whether anyone reacts.

A fact stated plainly gets "oh, ok" and a scroll. What gets a comment is being
told you are wrong and then being shown it. So every script runs this order:

  1. THE COLLISION. Flat, no preamble. "Sharks are older than trees."
  2. NAME THE BELIEF IT BREAKS, in the viewer's own head. "You were taught the
     forests came first." Say the wrong thing out loud - that is the moment
     someone stops scrolling, because you just described their own head.
  3. HOLD THE ANSWER BACK. Do not explain yet. Make it stranger first: raise
     the stakes, say how long everyone believed it, point out why it seems
     impossible. Two or three captions of "and it gets worse" before any
     resolution. This is the single biggest lever on whether people watch to
     the end - an answer given on caption three ends the video at caption
     three, whatever comes after it.
  4. THE PROOF, arriving around the middle, with one checkable specific - a
     date, a number, a name. Vague is forgettable and unshareable.
     "Trees: 350 million years. Sharks: 400."
  5. THE SECOND TWIST. One more turn they did not see coming, ideally one they
     can check themselves - "pinch your nose and eat an onion; it tastes like
     an apple". The first fact earns attention; something they can test earns
     the share, because now they have a reason to show someone.
  6. THE OPENING. Close on something arguable or unresolved, never "subscribe"
     and never a yes/no question. "Did you know this?" gets no reply. "What
     else were we taught wrong?" gets a comment section.

WORKED EXAMPLE - the same fact, weak then strong:

  WEAK (answer on line 3, nothing left to wonder about):
    You think your heart is on the left side?
    Most people believe it sits there.
    But your heart is almost in the center.
    It's behind your breastbone...

  STRONG (the answer waits, and the ending is testable):
    Put your hand where you think your heart is.
    Almost everyone points to the left.
    Almost everyone is wrong - and has been
    since they were four years old.
    Your heart is not on the left side of your chest.
    It sits almost dead centre, behind the breastbone,
    between the two lungs.
    Only its lower tip leans left - which is where
    the beat is loudest, which is why everyone points there.
    You have been feeling the corner of it your whole life.
    And about one person in ten thousand has it
    mirrored on the right, and never finds out.
    So - what else did everyone teach you wrong?

Write it so a person could say it out loud to a friend and get a reaction. If
reading it back produces no feeling - surprise, disbelief, "wait, what" - the
fact is wrong for this channel, however true it is. "Penguins can drink
saltwater" is true and got zero views. "Sharks existed before trees" is true and
got 732, because it told someone they were wrong.

Hard rules:
- Every one must be about a completely different subject from the others and
  from everything in the list of existing titles below.
- narration: 60-110 words. This goes in the description, not into the video.
- phrases: 9-12 on-screen captions. THESE ARE WHAT GETS SPOKEN AND SHOWN, and
  together they must take 25-35 seconds to say aloud - roughly 70-90 words in
  total. Every video this channel has published so far runs about 12 seconds,
  far too short to hold anyone or to earn any watch time, and the cause is
  captions of three or four words. Give each one a real clause.
  Each LINE inside a caption must still be at most 30 characters - use \\n for a
  line break, and two lines per caption is normal. They are burned onto the
  video, so a line that runs long is cut off.
- img: one detailed image-generation prompt describing a scene, ending with
  "vertical 9:16". Describe a PLACE or OBJECT, never a specific real person.
- title: under 90 characters, ending with 2-3 relevant hashtags.
- tags: 6-10 single words, lowercase, no spaces, no # symbol.

These titles already exist. Do not write anything on these subjects:
{titles}

Return ONLY a JSON array of {n} objects with keys: title, tags, img, narration,
phrases. No markdown fence, no commentary.
"""


def parse_array(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n", "", raw)
        raw = re.sub(r"\n```$", "", raw.strip())
    i, j = raw.find("["), raw.rfind("]")
    if i < 0 or j < 0:
        raise ValueError("no JSON array in response")
    return json.loads(raw[i:j + 1])


def grow(key_name, target, dry, gkey):
    cfg = CHANNELS[key_name]
    path = os.path.join(ROOT, cfg["dir"], cfg["bank"])
    bank = json.load(io.open(path, encoding="utf-8"))
    start = len(bank)

    want = min(HARD_CAP, max(target, start + GROW_PER_RUN))
    if start >= want:
        print("%s: %d scripts, already at target %d" % (key_name, start, want))
        return 0

    seen_titles = set(norm_title(d["title"]) for d in bank)
    seen_shingles = [shingles(d.get("narration", "")) for d in bank]

    added, attempts = 0, 0
    while len(bank) < want and attempts < 12:
        attempts += 1
        need = min(BATCH, want - len(bank))
        examples = json.dumps(random.sample(bank, min(3, len(bank))),
                              ensure_ascii=False, indent=1)
        titles = "\n".join("- " + d["title"] for d in bank[-160:])
        prompt = PROMPT.format(name=cfg["name"], brief=cfg["brief"],
                               examples=examples, n=need, titles=titles)
        try:
            items = parse_array(gemini(prompt, gkey))
        except BudgetSpent as e:
            # Stop cleanly and keep what was written. The bank grows again
            # tomorrow; the live app keeps its share of the quota today.
            print("  stopping: %s" % e, flush=True)
            break
        except Exception as e:
            print("  batch failed: %s" % str(e)[:180], flush=True)
            time.sleep(4)
            continue

        for d in items:
            why = valid(d)
            if why:
                print("  reject (%s)" % why, flush=True)
                continue
            nt = norm_title(d["title"])
            if nt in seen_titles:
                print("  reject (duplicate title)", flush=True)
                continue
            if too_similar(d.get("narration", ""), seen_shingles):
                print("  reject (too similar to an existing script)", flush=True)
                continue
            d = {"title": d["title"], "tags": [t.lower().lstrip("#") for t in d["tags"]],
                 "img": d["img"], "narration": d["narration"], "phrases": d["phrases"]}
            bank.append(d)
            seen_titles.add(nt)
            seen_shingles.append(shingles(d["narration"]))
            added += 1
        time.sleep(2)

    if added and not dry:
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(bank, ensure_ascii=False, indent=1))
    print("%s: %d -> %d (+%d)%s" % (key_name, start, len(bank), added,
                                    " [dry]" if dry else ""))
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channels", nargs="*", default=list(CHANNELS),
                    help="which channels to grow (default: all)")
    ap.add_argument("--target", type=int, default=0,
                    help="grow until the bank holds at least this many scripts")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    gkey = (os.environ.get("OWNER_GEMINI_KEY") or "").strip()
    if not gkey:
        print("no OWNER_GEMINI_KEY - nothing to do")
        return 0

    global _cap
    picked = [k for k in (a.channels or list(CHANNELS)) if k in CHANNELS]
    for k in (a.channels or []):
        if k not in CHANNELS:
            print("unknown channel:", k)

    # Share the budget evenly. Without this the first channel can spend the whole
    # allowance and the other two never grow at all.
    share = max(1, REQUEST_BUDGET // max(1, len(picked)))
    total = 0
    for n, k in enumerate(picked):
        _cap = share * (n + 1)
        try:
            total += grow(k, a.target, a.dry, gkey)
        except Exception as e:
            print("%s FAILED: %s" % (k, str(e)[:200]), flush=True)
    print("TOTAL ADDED %d (budget %d requests)" % (total, REQUEST_BUDGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
