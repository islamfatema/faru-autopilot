# -*- coding: utf-8 -*-
"""Point the generators at what people are actually searching for.

Every subject so far has been chosen from what already worked on these
channels. That is a real signal and a closed loop - it can only ever propose
more of what has already been made, and it says nothing about the enormous
number of people who are looking for something these channels have never
covered.

tools/demand.py now pulls YouTube's own autocomplete: 115 distinct searches for
History, 114 for FaRu, 99 for Rise. Real phrases, typed by real people:

    why did rome fall / why did rome split in two / why did rome leave britain
    why does my body ache when i'm sick / what happens when you stop smoking
    how to stop overthinking / how to stop being lazy / how to stop procrastinating

This puts them in front of the generator. It matters more than it looks: the
Shorts feed serves a video for a few days and then never again, while a video
that answers a search is found for years. Search is already 8% of FaRu Fact's
views without a single video having been written for it on purpose.
"""
import ast
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOADER = '''
def search_demand(key, n=25):
    """What people typed into YouTube, from tools/demand.py.

    Optional by design: if the file is missing the generator carries on with
    the channel's own history, which is what it did before this existed.
    """
    p = os.path.join(ROOT, "analytics", "demand_%s.json" % key)
    try:
        rows = json.load(io.open(p, encoding="utf-8"))["queries"]
    except Exception:
        return ""
    picks = [r["query"] for r in rows[:n]]
    if not picks:
        return ""
    return (
        "\\n\\nWHAT PEOPLE ARE ACTUALLY SEARCHING FOR ON YOUTUBE RIGHT NOW.\\n"
        "These are real phrases from YouTube's own autocomplete. A video that\\n"
        "answers one of them is found for years; a video that only suits the\\n"
        "Shorts feed is served for a few days and then never again. Search is\\n"
        "already 8% of this channel's views with nothing written for it on\\n"
        "purpose. Where one of these fits the channel, write it - keeping every\\n"
        "other rule above.\\n\\n"
        + "".join("    %s\\n" % q for q in picks))

'''


def patch_grow():
    p = os.path.join(ROOT, "tools", "grow.py")
    s = io.open(p, encoding="utf-8").read()
    if "def search_demand" in s:
        print("  grow.py already patched")
        return
    s = s.replace("def grow(key_name, target, dry, gkey):",
                  LOADER.strip("\n") + "\n\ndef grow(key_name, target, dry, gkey):", 1)
    old = '''        prompt = PROMPT.format(name=cfg["name"], brief=cfg["brief"],'''
    new = '''        prompt = PROMPT.format(name=cfg["name"],
                               brief=cfg["brief"] + search_demand(key_name),'''
    if s.count(old) != 1:
        raise SystemExit("grow.py: prompt call found %d times" % s.count(old))
    s = s.replace(old, new)
    write(p, s)


def patch_topics():
    p = os.path.join(ROOT, "tools", "grow_topics.py")
    s = io.open(p, encoding="utf-8").read()
    if "def search_demand" in s:
        print("  grow_topics.py already patched")
        return
    s = s.replace("def valid(d, seen):",
                  LOADER.strip("\n") + "\n\ndef valid(d, seen):", 1)
    old = '''            items = grow.parse_array(grow.gemini(PROMPT.format(
                n=need, name=name, brief=brief, titles=titles), gkey))'''
    new = '''            items = grow.parse_array(grow.gemini(PROMPT.format(
                n=need, name=name, brief=brief + search_demand(key),
                titles=titles), gkey))'''
    if s.count(old) != 1:
        raise SystemExit("grow_topics.py: prompt call found %d times" % s.count(old))
    s = s.replace(old, new)
    write(p, s)


def write(path, s):
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % os.path.basename(path))


patch_grow()
patch_topics()
print("done")
