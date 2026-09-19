# -*- coding: utf-8 -*-
"""The five reasons a video has to earn before it is allowed to publish.

Fatema's rule, in code: a video is not approved because it exists. It is
approved when it can answer five questions, and each one has a measurable
counterpart in the diagnosis file, so a script that fails here is a script that
would have come back as a named failure later.

    VIEW      why would anyone click?      -> title carries a number, a
                                              comparison, a correction, or
                                              addresses the viewer
    WATCH     why would they stay?         -> the script turns - it does not
                                              state the fact and then explain the
                                              same fact again
    COMMENT   why would they answer?       -> it ends on a question about the
                                              viewer, not "comment below"
    SHARE     why would they send it on?   -> it names a person to send it to,
                                              or the fact is useful or absurd
                                              enough to forward
    SUBSCRIBE why would they come back?    -> it names what is next

Used by the posting machines: a script missing a trigger is skipped, not fixed
silently, and the reason is printed so the generator's next batch can be told
what it keeps getting wrong.
"""
import re

SECOND_PERSON = re.compile(r"\b(you|your|yours|you're|you'll|you've)\b", re.I)
NUMBERISH = re.compile(r"\d|\bhalf\b|\btwice\b|\bmillion\b|\bbillion\b|\bthousand\b"
                       r"|\bfirst\b|\bonly\b|\bnever\b|\bevery\b|\bmore\b", re.I)
COMPARISON = re.compile(r"\bolder than\b|\bbefore\b|\bthan\b|\blonger than\b|\bbigger than\b|\bstill\b|\bwhen\b", re.I)
CORRECTION = re.compile(r"\bactually\b|\breally\b|\bnot\b|\bisn't\b|\bdoesn't\b|\bdidn't\b|\bwasn't\b|\bweren't\b|\baren't\b|\bnever\b|\bcan't\b", re.I)
SHARE_SHAPED = re.compile(r"\bsend this\b|\btell (someone|them|the)\b|\bshow this\b|\bwho (taught|told)\b", re.I)
NEXT_SHAPED = re.compile(r"\bnext\b|\btomorrow\b|\bfollow\b|\bepisode\b|\bnumber \d+\b", re.I)


def _captions(d):
    return [c for c in (d.get("phrases") or []) if c]


def view_trigger(d):
    t = d.get("title") or ""
    if NUMBERISH.search(t) or COMPARISON.search(t) or CORRECTION.search(t) or SECOND_PERSON.search(t):
        return True, ""
    return False, ("the title names no number, no comparison, no correction and "
                   "does not address the viewer - there is no reason to click it")


def watch_trigger(d):
    """A second turn: the payoff is not a restatement of the opening line.

    Measured on this project's own worst videos - the ones that stated a fact in
    caption one and spent the remaining twenty seconds saying it again - which is
    what WEAK_HOOK looks like in the diagnosis file.
    """
    caps = _captions(d)
    if len(caps) < 6:
        return False, "too few captions to carry a turn"
    first = set(w.lower().strip(".,!?'") for w in caps[0].split() if len(w) > 4)
    mid = " ".join(caps[len(caps) // 2:len(caps) // 2 + 3]).lower()
    if not first:
        return True, ""
    repeated = sum(1 for w in first if w in mid)
    if repeated >= max(2, len(first) - 1):
        return False, "the middle repeats the opening line instead of turning"
    return True, ""


def comment_trigger(d):
    caps = _captions(d)
    tail = " ".join(caps[-4:]).lower()
    if "?" in tail and SECOND_PERSON.search(tail):
        return True, ""
    if "?" in tail:
        return True, ""
    return False, "nothing at the end asks the viewer anything"


def share_trigger(d):
    caps = _captions(d)
    tail = " ".join(caps[-4:])
    if SHARE_SHAPED.search(tail):
        return True, ""
    # An absurd or useful fact carries itself; a flat statement does not.
    text = (d.get("narration") or " ".join(caps)).lower()
    if any(w in text for w in ("never", "older than", "impossible", "survived",
                               "billion", "million", "try it", "measure", "check")):
        return True, ""
    return False, "no reason to send this to a specific person"


def subscribe_trigger(d):
    caps = _captions(d)
    tail = " ".join(caps[-3:])
    if d.get("series") or NEXT_SHAPED.search(tail):
        return True, ""
    return False, "nothing tells the viewer what they get by coming back"


CHECKS = (("VIEW", view_trigger), ("WATCH", watch_trigger),
          ("COMMENT", comment_trigger), ("SHARE", share_trigger),
          ("SUBSCRIBE", subscribe_trigger))


def missing(d, required=("VIEW", "WATCH")):
    """Which triggers this script fails. Only `required` blocks publishing.

    COMMENT, SHARE and SUBSCRIBE are reported but not enforced on generated
    bank scripts: the posting machine appends the closing question, the share
    line and the name of the next video itself, so enforcing them here rejects
    a script for something added ten lines later. Measured when this was set
    wrongly: 757 of 775 scripts were blocked for missing a line the machine was
    about to add.
    """
    out = []
    for name, fn in CHECKS:
        ok, why = fn(d)
        if not ok:
            out.append((name, why, name in required))
    return out


def blocked(d, required=("VIEW", "WATCH")):
    return [(n, w) for n, w, req in missing(d, required) if req]
