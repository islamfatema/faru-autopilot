# -*- coding: utf-8 -*-
"""Score a script against what that channel measurably converts on.

The briefs now tell the generator what each channel should be about. That only
governs scripts written from today. The banks still hold roughly two thousand
older ones, and expand.py deliberately keeps every title unchanged - so left
alone it spends the whole Gemini budget making "Chameleons Don't Change Color
To Camouflage" thirty seconds long instead of twelve. That video already had
its chance: 226 views, zero likes, zero comments.

So the bank needs ordering by subject, not only by length. This scores a script
against the pattern its own channel converts on:

    Rise With Fate    a statement about the viewer          11.1 subs/1,000
    FaRu Fact         the viewer's own body or possessions   6.2
    History Explains  Rome doing something we assume modern  3.6

A caution that belongs in the code rather than only in my head: FaRu's and
History's samples are small - one or two comments, a handful of likes per
video. The body pattern and the Rome pattern are the strongest signals present,
but they are not proven the way the collision rule was. The validation at the
bottom of this file prints how well the score actually separates the known
winners from the known duds, so the claim can be checked rather than believed.

    python tools/formula.py            # run the validation
"""
import re

# ---- Rise With Fate -------------------------------------------------------
# Every top converter is a line the viewer would repeat about themselves.
US_SELF = re.compile(
    r"\b(you|your|yourself|you're|youre)\b", re.I)
US_ABSTRACT = re.compile(
    r"\b(people|society|everyone|humans|the world|they say)\b", re.I)
# "Discipline Is Self Respect" is the single best converter on the channel and
# contains no "you" at all - it is an identity equation about an inner quality,
# which is the same move in a different grammar. Without this the top performer
# scored zero and tied with the duds.
US_QUALITY = re.compile(
    r"\b(discipline|respect|energy|growth|focus|patience|doubt|fear|excuses?|"
    r"standards?|obsessed|obsession|consistency|ego|comfort|pain|silence|"
    r"habits?)\b", re.I)
# The duds are about somebody else, or a metaphor with no owner at all:
# "They Laughed, Then They Copied", "Burn The Boats", "Sweep The Floor".
US_THIRD = re.compile(
    r"^\s*(they|he|she|nobody|everybody|burn|sweep|water|weigh)\b", re.I)

# ---- FaRu Fact ------------------------------------------------------------
# The winners are the viewer's own body. The duds are animals in a zoo and
# wars nobody remembers.
FUN_OWNED = re.compile(
    r"\b(your|you)\b.{0,30}\b(body|brain|eyes?|skin|bones?|skeleton|blood|"
    r"heart|stomach|tongue|nose|ears?|muscles?|teeth|hair|sleep|memory|"
    r"lungs?|liver|cells?|dna|voice|hands?|feet)\b"
    r"|\b(your (phone|food|water|money|house|home|bed|coffee|shower|breath))\b",
    re.I)
FUN_SELF_ANY = re.compile(r"\byour?\b", re.I)
FUN_ZOO = re.compile(
    r"\b(chameleons?|flamingos?|wombats?|butterfl(y|ies)|bees?|ants?|"
    r"octopus|penguins?|koalas?|giraffes?|sloths?|snails?)\b", re.I)
FUN_FARAWAY = re.compile(
    r"\b(war|battle|empire|dynasty|century|medieval|treaty|king|queen)\b", re.I)

# ---- History That Explains the World --------------------------------------
# Three of five best converters and both most-rewatched videos are Rome, and
# specifically Rome doing something we assume is modern.
HIST_ROME = re.compile(r"\b(rome|roman|romans|caesar|colosseum|pompeii)\b", re.I)
HIST_MODERN = re.compile(
    r"\b(vending|plumbing|concrete|apartment|fast food|takeaway|shopping|"
    r"traffic|central heating|sunscreen|advertis|graffiti|delivery|"
    r"million people|recycling|newspaper|password|strike|insurance)\b", re.I)
# Famous enough that everybody already knows it - collects views, earns nothing.
HIST_EXHAUSTED = re.compile(
    r"\b(berlin wall|wright brothers|moon landing|titanic|hitler|"
    r"world war (one|two|i|ii)|columbus|pyramids? of giza)\b", re.I)


def _text(d):
    return " ".join([d.get("title", ""), d.get("narration", "")] +
                    list(d.get("phrases") or []))


def score(channel, d):
    """Higher is better. Zero or below means write something else instead."""
    t = _text(d)
    title = d.get("title", "")
    s = 0

    if channel == "us":
        s += 3 if US_SELF.search(title) else 0
        s += 1 if US_SELF.search(t) else 0
        s += 3 if US_QUALITY.search(title) else 0
        s -= 2 if US_ABSTRACT.search(title) else 0
        s -= 3 if US_THIRD.search(title) else 0

    elif channel == "fun":
        # The two best converters on this channel are the viewer's own body.
        s += 4 if FUN_OWNED.search(t) else 0
        s += 1 if FUN_SELF_ANY.search(title) else 0
        # 226 views and nothing to show for it.
        s -= 3 if FUN_ZOO.search(title) else 0
        s -= 2 if FUN_FARAWAY.search(title) else 0

    elif channel == "history":
        s += 3 if HIST_ROME.search(t) else 0
        s += 2 if HIST_MODERN.search(t) else 0
        # The penalty reads the TITLE only. Scored against the whole script it
        # fired on passing mentions - three pyramid scripts were sent to the
        # back of the rotation because their narration happened to say
        # "Columbus" once, and one of the channel's own engagement winners is
        # "The Last Mammoths Died While the Pyramids Stood". What a video is
        # ABOUT is what its title says it is about.
        s -= 4 if HIST_EXHAUSTED.search(title) else 0

    return s


# ---------------------------------------------------------------- validation
# Real titles with their real 28-day numbers. A rule that cannot separate these
# is not worth applying to two thousand scripts.
WINNERS = {
    "us": ["Discipline Is Self Respect",
           "Become Obsessed With Your Growth",
           "Protect Your Energy Like Your Life",
           "You Will Never Feel Ready",
           "Your Excuses Are Comfortable Lies"],
    "fun": ["Your Skeleton Replaces Itself Every Decade!",
            "Your Brain Sees, Not Your Eyes!",
            "Your Tongue Cannot Taste Dry Food",
            "Your Stomach Gets a New Lining Every Few Days"],
    "history": ["Rome Had Vending Machines 2,000 Years Ago",
                "Rome Had a Million People 2,000 Years Ago",
                "Ancient Roman Concrete Can Heal Itself",
                "Roman Concrete Gets Stronger in Seawater"],
}
DUDS = {
    "us": ["They Laughed, Then They Copied",
           "Burn The Boats, Commit Fully",
           "Sweep The Floor Before Sunset"],
    "fun": ["Chameleons Don't Change Color To Camouflage!",
            "The Shortest War Lasted 38 Minutes",
            "A Group of Flamingos Is Called a Flamboyance",
            "Bees Can Recognise Human Faces"],
    "history": ["Berlin Was Split by a Wall Until 1989",
                "The Wright Brothers' First Flight Was Shorter",
                "We Reached the Moon 66 Years After the First Flight"],
}


def _validate():
    total_ok = total = 0
    for ch in ("us", "fun", "history"):
        w = [score(ch, {"title": t, "narration": t}) for t in WINNERS[ch]]
        d = [score(ch, {"title": t, "narration": t}) for t in DUDS[ch]]
        # Every winner should outscore every dud.
        pairs = [(a, b) for a in w for b in d]
        ok = sum(1 for a, b in pairs if a > b)
        total_ok += ok
        total += len(pairs)
        print("%-8s winners %-22s duds %-18s  separated %d/%d"
              % (ch, w, d, ok, len(pairs)))
    print("\noverall: %d of %d winner/dud pairs ordered correctly (%.0f%%)"
          % (total_ok, total, 100.0 * total_ok / total))
    if total_ok < total:
        print("Not perfect. Applied as a RANKING, not a filter - a script that "
              "scores low is published last, never deleted.")


if __name__ == "__main__":
    _validate()
