# -*- coding: utf-8 -*-
"""Tell the generator what actually earned a like, a comment or a share.

Everything the generator was optimising for was reach. The brief carried view
counts, the tag bias came from view counts, and the collision rule was measured
in view counts. None of that is what Fatema asked for - she asked for videos
people like, comment on and share.

The first engagement measurement is in, and it says something the view data
never did.

Rise With Fate is by a distance the most engaged channel, and its ceiling is
much higher than the other two:

    Discipline Is Self Respect            895 views   79 likes   5 comments
    Water The Grass Where You Stand       214 views   21 likes   2 comments
    Stop Explaining, Start Producing      163 views    9 likes   4 comments

against its own flops, which are not low-view videos at all:

    Burn The Boats, Commit Fully          761 views    8 likes   0 comments
    They Laughed, Then They Copied        321 views    3 likes   0 comments

Seven hundred and sixty one views and eight likes. The reach was there and the
video did not earn anything. So reach is not the problem being solved here.

The same split runs through the history channel, and it is the clearest finding
in the data:

    Napoleon Was Once Attacked by Rabbits          110 views  4 likes  2 comments
    The Last Mammoths Died While the Pyramids Stood 80 views  9 likes
    There Are More Pyramids in Sudan Than in Egypt  82 views  8 likes

    Berlin Was Split by a Wall Until 1989          207 views  1 like   0 comments
    The Wright Brothers' First Flight Was Shorter  294 views  2 likes  0 comments
    We Reached the Moon 66 Years After First Flight 177 views 1 like   0 comments

Every flop is something the viewer already knew. A well known fact still gets
served to feeds - that is why the view counts are respectable - but nobody likes
a video for telling them what they learned at school, and nobody comments on it
because there is nothing to add and nothing to argue with.

That is the rule this writes into every brief: obscure is not enough, and
famous is fatal. The fact has to be something the viewer can dispute, add to, or
send to a specific person who is wrong about it.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "tools", "grow.py")

COMMON = """

WHAT EARNS A LIKE, A COMMENT OR A SHARE - measured on this channel, {month}:

{examples}

The pattern is the same on every channel here, and it is not about reach. The
videos that earned nothing were not short of views; they were short of stakes.
Every single one of them told the viewer something they already knew.

So the test for a subject is not "is this obscure". It is:

  1. Can the viewer DISPUTE it? Something they can push back on earns a comment.
     Something indisputable earns silence.
  2. Can the viewer ADD to it? If the subject invites "my grandfather did that"
     or "same thing happened to me", the comments write themselves.
  3. Is there a SPECIFIC PERSON the viewer would send this to? Not "people who
     like history" - an actual person they can picture being wrong about this.

If a subject fails all three, do not write it, however interesting it is. A
famous fact is the worst possible choice: it will be served to feeds, it will
collect views, and it will earn nothing at all.
"""

EXAMPLES = {
    "us": """    Discipline Is Self Respect            895 views   79 likes   5 comments
    Water The Grass Where You Stand       214 views   21 likes   2 comments
    Stop Explaining, Start Producing      163 views    9 likes   4 comments
    Nobody Is Coming To Save You           51 views    7 likes

  and the ones that reached people and earned nothing:

    Burn The Boats, Commit Fully          761 views    8 likes   0 comments
    They Laughed, Then They Copied        321 views    3 likes   0 comments
    Sweep The Floor Before Sunset          47 views    0 likes   0 comments""",
    "history": """    Napoleon Was Once Attacked by Rabbits          110 views  4 likes  2 comments
    The Last Mammoths Died While the Pyramids Stood 80 views  9 likes
    There Are More Pyramids in Sudan Than in Egypt  82 views  8 likes
    The Slinky Was Meant for Warships              127 views  9 likes  1 comment

  and the ones that reached people and earned nothing:

    Berlin Was Split by a Wall Until 1989          207 views  1 like   0 comments
    The Wright Brothers' First Flight Was Shorter  294 views  2 likes  0 comments
    We Reached the Moon 66 Years After First Flight 177 views 1 like   0 comments""",
    "fun": """    The Great Pyramid Was Tallest Until Medieval Times  40 views  1 like  2 comments
    Edison Didn't Invent the Lightbulb                  60 views  4 likes
    Earth Has More Than One Moon (Sometimes)           251 views  9 likes  1 comment
    Ants Don't Have Lungs                               50 views  3 likes

  and the ones that reached people and earned nothing:

    Pineapples Take Two Years to Grow                   56 views  0 likes  0 comments
    There Are More Trees Than Stars in the Galaxy       79 views  0 likes  0 comments
    Your Stomach Gets a New Lining Every Few Days       54 views  0 likes  0 comments""",
}


def main():
    s = io.open(PATH, encoding="utf-8").read()
    if "WHAT EARNS A LIKE" in s:
        raise SystemExit("already patched")

    n = 0
    for key, ex in EXAMPLES.items():
        # Each brief is a run of adjacent string literals ending just before the
        # closing paren of the dict entry. Append one more literal to it.
        marker = '    "%s": {' % key
        i = s.index(marker)
        # the brief value ends at the first "\n        ),\n" after the marker
        end = s.index("\n        ),\n", i)
        block = COMMON.format(month="September 2026", examples=ex)
        lit = "".join('\n            %s' % repr(line + "\n")
                      for line in block.strip("\n").split("\n"))
        s = s[:end] + lit + s[end:]
        n += 1

    ast.parse(s)
    tmp = PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, PATH)
    print("patched %d channel briefs" % n)


main()
