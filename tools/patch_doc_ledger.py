# -*- coding: utf-8 -*-
"""Never publish the same documentary twice.

Reading the run logs for what actually uploaded:

    History  The American Town You Can Only Reach Through Another Country  x2
    History  The Map Mistake That Gave Away an Entire Country              x2
    FaRu     The Psychology Tricks Used on You Every Day                   x2

The exact complaint Fatema opened this project with - "why am I seeing the same
post again and again" - now on the long-form, where each repeat is twelve
minutes of production spent splitting one video's views in two.

The Shorts were fixed with a ledger after "Mount Everest Isn't Earth's Highest
Point" went out twice. The documentaries never got one. pick_topic() chooses by
date:

    second_half = 1 if today.weekday() >= 4 else 0     # Fri/Sat/Sun
    idx = week * 2 + second_half

That is correct for two episodes a week and wrong for four. Monday and
Wednesday both land on second_half 0, so they get the same index; Friday and
Sunday both get 1. And every time grow_topics.py adds an episode, len(topics)
changes and the modulo remaps every index at once. Positional rotation cannot
survive either change, and the channels now have both.

So the picker takes the first episode in bank order that the ledger has not
recorded, publish.py records each title as it uploads, and the workflow commits
the ledger. If every episode has been used it stops rather than repeat.

Seeded from the logs. Two Rise episodes were renamed in the bank after they
published - "The Truth About Motivation Nobody Sells" is now "Telling People
Your Goal Makes You Less Likely To Do It" - so both names go in, or the picker
would treat the renamed entry as new and publish it a second time.
"""
import ast
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEED = {
    "autopilot_history": [
        "The Empire That Ruled a Quarter of the World and Vanished in 30 Years",
        "Why Rome Actually Fell (It Is Not What You Were Taught)",
        "Rome Did Not Fall in a Year. It Took 300.",
        "The American Town You Can Only Reach Through Another Country",
        "The Map Mistake That Gave Away an Entire Country",
    ],
    "autopilot_us": [
        "Bankrupt at 65 With Nothing Left But One Recipe",
        "The Man Who Failed Until He Was 65",
        "The Truth About Motivation Nobody Sells",
        "Telling People Your Goal Makes You Less Likely To Do It",
        "What Happens When You Start Over at 40",
        "Founders Over 40 Succeed More Often Than Founders in Their 20s",
    ],
    "autopilot_fun": [
        "Everything You Believe About the Human Body Is Slightly Wrong",
        "The Everyday Things That Are Older Than You Think",
        "The Psychology Tricks Used on You Every Day",
    ],
}

PICK_OLD_START = "def pick_topic(topics, offset=0):"

PICK_NEW = '''LEDGER = os.path.join(HERE, "published_docs.json")


def _norm(t):
    """Lower case, letters and digits only, so a changed emoji or a trailing
    hashtag does not make an episode look new."""
    import re as _re
    t = _re.sub(r"#\\w+", " ", t or "").lower()
    return " ".join(_re.sub(r"[^a-z0-9 ]+", " ", t).split())


def read_doc_ledger():
    try:
        return set(_norm(t) for t in json.load(io.open(LEDGER, encoding="utf-8")))
    except Exception:
        return set()


def pick_topic(topics, offset=0):
    """The first episode, in bank order, that has never been published.

    This used to rotate by date - week * 2, plus one from Friday - which is
    right for two episodes a week and wrong for four: Monday and Wednesday got
    the same index, and so did Friday and Sunday. Adding episodes to the bank
    changed len(topics) and remapped every index besides. Three documentaries
    went out twice before it was noticed.

    A ledger cannot drift: it records what actually uploaded. If every episode
    has been used, stop - a missed slot costs a day, a repeat costs the channel.
    """
    done = read_doc_ledger()
    for idx, t in enumerate(topics):
        if _norm(t.get("title")) not in done:
            print("ledger: %d episodes already published, choosing the first "
                  "that is not" % len(done), flush=True)
            return t, idx
    raise SystemExit("every episode in the bank has been published - "
                     "run grow_topics.py before publishing another")'''

PUB_OLD = '''    record_featured(vid, meta.get("title", ""))'''
PUB_NEW = '''    record_featured(vid, meta.get("title", ""))
    record_published(meta.get("title", ""))'''

PUB_FUNC = '''
def record_published(title):
    """Add this episode to the ledger the picker reads, so it is never chosen
    again. The picker used to rotate by date and published three documentaries
    twice; the ledger is what stops that."""
    if not title:
        return
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "published_docs.json")
    try:
        cur = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
        if title not in cur:
            cur.append(title)
        tmp = path + ".tmp"
        json.dump(cur, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        print("ledger: recorded %r" % title[:60], flush=True)
    except Exception as e:
        print("could not record the episode: %s" % str(e)[:120], flush=True)


'''


def write(path, s):
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)


def patch_makeboard(d):
    path = os.path.join(ROOT, d, "longform", "makeboard.py")
    s = io.open(path, encoding="utf-8").read()
    if "def read_doc_ledger" in s:
        print("  %s makeboard already patched" % d)
        return
    i = s.index(PICK_OLD_START)
    j = s.index("\n\n\n", i)
    s = s[:i] + PICK_NEW + s[j:]
    if "\nimport io" not in s and "import io," not in s and ", io" not in s:
        s = "import io\n" + s
    if "\nHERE" not in s and "HERE =" not in s:
        s = s.replace("import os", "import os\nHERE = os.path.dirname(os.path.abspath(__file__))", 1)
    write(path, s)
    print("  patched %s/longform/makeboard.py" % d)


def patch_publish(d):
    path = os.path.join(ROOT, d, "longform", "publish.py")
    s = io.open(path, encoding="utf-8").read()
    if "def record_published" in s:
        print("  %s publish already patched" % d)
        return
    if s.count(PUB_OLD) != 1:
        raise SystemExit("%s: record_featured call found %d times" % (d, s.count(PUB_OLD)))
    s = s.replace(PUB_OLD, PUB_NEW)
    s = s.replace("def upload(", PUB_FUNC.lstrip("\n") + "def upload(", 1)
    write(path, s)
    print("  patched %s/longform/publish.py" % d)


def seed(d, titles):
    path = os.path.join(ROOT, d, "longform", "published_docs.json")
    cur = json.load(io.open(path, encoding="utf-8")) if os.path.exists(path) else []
    for t in titles:
        if t not in cur:
            cur.append(t)
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(cur, ensure_ascii=False, indent=1))
    print("  seeded %s with %d episodes" % (d, len(cur)))


for d, titles in SEED.items():
    patch_makeboard(d)
    patch_publish(d)
    seed(d, titles)
print("done")
