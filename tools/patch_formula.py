# -*- coding: utf-8 -*-
"""Write each channel's own measured formula into its brief.

Per-video analytics arrived and corrected two things I had told Fatema.

FIRST, I said FaRu Fact's retention was half of Rise's and treated that as a
quality problem. It is a length artifact. Every channel holds a viewer about
twenty seconds, and FaRu's recent uploads are the longest, so the same twenty
seconds reads as 47% instead of 87%. Nothing was wrong with the content.

SECOND, and more useful, I then assumed twenty seconds was a ceiling. It is
not. The longest videos hold the longest and get rewatched:

    Rome Had a Million People 2,000 Years Ago    47s held   191% viewed
    Ancient Roman Concrete Can Heal Itself       33s held   146% viewed
    Our Sun Orbits Faster Than A Bullet          41s held   109% viewed

Over 100% means people watched it twice. So the thirty-second floor Fatema
insisted on is producing the best-performing videos on all three channels, and
the twenty-second average is just the old twelve-second library dragging it
down.

THIRD, subscriber conversion per video says what each channel should be about,
and it is not what any of them is currently about.

    Rise With Fate    Discipline Is Self Respect            11.1 subs/1k
                      Become Obsessed With Your Growth       8.1
                      Protect Your Energy Like Your Life     6.6

    FaRu Fact         Your Skeleton Replaces Itself          6.2 subs/1k
                      Your Brain Sees, Not Your Eyes         5.8
                      Earth Has More Than One Moon           5.7

    History Explains  Rome Had Vending Machines              3.6 subs/1k
                      One Volcano Caused a Year Without Summer 3.5
                      Why Almost Everyone Lives Up North     3.5

FaRu Fact out-converts History nearly two to one - when it points at the
viewer's own body. Its flops are the ones about nothing the viewer owns:
chameleons, the shortest war, trees versus stars. So FaRu does not need
closing, which is what I had recommended. It needs to stop doing zoo trivia
and start doing the viewer.

History's three best converters and both of its most-rewatched videos are Rome.

Every number in the briefs below is that channel's own.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "tools", "grow.py")

BLOCK = """

WHAT THIS CHANNEL SHOULD ACTUALLY BE ABOUT - from its own per-video numbers:

{body}

LENGTH. Do not write short. The longest videos on these channels are the ones
people rewatch - 47 seconds held at 191% viewed, 33 seconds at 146%. Over 100%
means they watched it a second time. Thirty seconds is the floor and forty is
better, as long as every caption carries new information.
"""

BODIES = {
    "us": """    Discipline Is Self Respect              898 views   11.1 subscribers per 1,000
    Become Obsessed With Your Growth        738 views    8.1
    Protect Your Energy Like Your Life      609 views    6.6

  Every one is a statement about the viewer, phrased as something they either
  already believe about themselves or are about to. Not advice, not a tip - a
  line they would repeat. This channel converts at 4.78 per thousand overall
  and these do more than double that, so write more of exactly this.""",
    "fun": """    Your Skeleton Replaces Itself Every Decade   321 views   6.2 subscribers per 1,000
    Your Brain Sees, Not Your Eyes               172 views   5.8
    Earth Has More Than One Moon (Sometimes)     350 views   5.7

  and the ones that reached people and converted nobody:

    Chameleons Don't Change Color To Camouflage  226 views   0 likes  0 comments
    The Shortest War Lasted 38 Minutes           114 views   0        0
    There Are More Trees Than Stars              85 views    0        0

  The pattern is not obscurity - "chameleons don't change colour to camouflage"
  is a perfectly surprising fact and it earned nothing at all. The pattern is
  OWNERSHIP. The winners are about the viewer's own body: their skeleton, their
  brain, their eyes. The losers are about animals in a zoo and wars they have
  never heard of.

  So write about what the viewer IS and what they TOUCH: their body, their
  sleep, their food, their phone, their money, their house, their senses. If the
  subject is not something they own, carry, eat or are made of, do not write it.
  When it works this channel converts better than the history channel does, so
  the format is not the problem - the subjects have been.""",
    "history": """    Rome Had Vending Machines 2,000 Years Ago    839 views   3.6 subscribers per 1,000
    One Volcano Caused a Year Without Summer     848 views   3.5
    Why Almost Everyone Lives in the Northern Half 863 views 3.5

  and the two most rewatched videos on the channel:

    Rome Had a Million People 2,000 Years Ago    756 views   191% viewed
    Ancient Roman Concrete Can Heal Itself       950 views   146% viewed

  Three of the five are Rome. Not "ancient history" - Rome specifically, and
  specifically Rome doing something modern: plumbing, vending machines, concrete
  that outlasts ours, a city of a million people. The viewer's assumption being
  overturned is that the past was primitive.

  Keep writing Rome, and treat any empire the same way: find the thing they had
  that we assume is modern. The flops are the famous facts everyone already
  knows - Berlin Wall, Wright brothers, the moon landing - which collect views
  and earn nothing, because there is nothing left to say about them.""",
}


def main():
    s = io.open(PATH, encoding="utf-8").read()
    if "WHAT THIS CHANNEL SHOULD ACTUALLY BE ABOUT" in s:
        raise SystemExit("already patched")

    for key, body in BODIES.items():
        marker = '    "%s": {' % key
        i = s.index(marker)
        end = s.index("\n        ),\n", i)
        block = BLOCK.format(body=body)
        lit = "".join('\n            %s' % repr(line + "\n")
                      for line in block.strip("\n").split("\n"))
        s = s[:end] + lit + s[end:]
        print("  brief updated: %s" % key)

    ast.parse(s)
    tmp = PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, PATH)
    print("patched tools/grow.py")


main()
