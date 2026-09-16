# -*- coding: utf-8 -*-
"""Score the first line, because the first line is where the channels are losing.

The first diagnosis of all three channels agreed: the most common named failure
is WEAK_HOOK - people arrive and leave inside a few seconds. That is not a
topic problem and not a title problem; it is the opening caption.

This scores the opening of every banked script on what the retention data on
this project has actually rewarded:

  +2  the first line IS the claim - the strange thing, stated
  +1  it is short enough to land before the viewer decides (<= 9 words)
  +1  it puts the viewer or a number in the first line
  -2  it is a run-up: "this sounds fake", "did you know", "let me tell you",
      naming the subject before saying anything about it
  -1  it opens on a question the video then answers slowly

The score is used two ways: the posting machines play strong openings first,
and the weakest are listed for the generator to rewrite. Nothing is rewritten
automatically here - a hook rewritten by a rule reads like a rule.
"""
import re

FILLER = re.compile(r"^(this sounds fake|you won'?t believe|wait for|did you know|"
                    r"here'?s|let me tell|imagine|picture this|have you ever|"
                    r"i bet you|believe it or not)", re.I)
NUMBERISH = re.compile(r"\d|\bhalf\b|\btwice\b|\bmillion\b|\bbillion\b|\bthousand\b|"
                       r"\bnever\b|\bonly\b|\bevery\b|\bfirst\b|\bolder\b|\blonger\b", re.I)
SECOND_PERSON = re.compile(r"\b(you|your|you're|yours)\b", re.I)
CLAIMY = re.compile(r"\b(is|are|was|were|can|cannot|can'?t|has|have|makes|survived|"
                    r"older|before|beats|costs|hurts|lasts|holds|weighs)\b", re.I)


def first_line(d):
    if d.get("hook"):
        return d["hook"]
    caps = d.get("phrases") or []
    return caps[0] if caps else ""


def score(d):
    """(score, why) for the opening of one script. Higher is better."""
    line = (first_line(d) or "").strip()
    if not line:
        return -3, "no opening line at all"
    words = line.split()
    s, notes = 0, []

    if FILLER.match(line):
        s -= 2
        notes.append("opens on a run-up instead of the fact")
    if CLAIMY.search(line) and not line.endswith("?"):
        s += 2
        notes.append("the first line is the claim")
    if len(words) <= 9:
        s += 1
        notes.append("short enough to land")
    elif len(words) >= 14:
        s -= 1
        notes.append("%d words before anything happens" % len(words))
    if NUMBERISH.search(line) or SECOND_PERSON.search(line):
        s += 1
        notes.append("carries a number or the viewer")
    if line.endswith("?") and len(words) > 8:
        s -= 1
        notes.append("opens on a long question")
    return s, "; ".join(notes)


def weakest(bank, n=25):
    """The banked scripts whose openings should be rewritten first."""
    scored = [(score(d)[0], score(d)[1], d) for d in bank]
    scored.sort(key=lambda t: t[0])
    return scored[:n]
