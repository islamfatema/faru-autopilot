# -*- coding: utf-8 -*-
"""Stop a two-word published title from blocking everything it shares a word with.

near_duplicate() measures overlap against the SHORTER title, which is right for
"Ketchup Was Sold as Medicine" against "Ketchup Was Once Sold as Medicine". But
Rise has published "You Were Built for More Than This", and after stop-words
that title is a single content word: {built}. Any future script containing
"built" overlaps it 1.0 and is silently skipped forever - which is how "People
Paid About 63% More for Boxes They Built Themselves" was about to be dropped.

A title that reduces to one or two content words is too thin to judge a subject
by, so it is compared against the longer title instead: {built} against an
eight-word subject scores 0.125 and nothing is skipped. Real repeats, which
share most of a real subject either way, are unaffected.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

OLD = """    for o in others:
        b = o if isinstance(o, set) else _subject(o)
        if b and len(a & b) / float(min(len(a), len(b))) >= NEAR_DUP:
            return True"""
NEW = """    for o in others:
        b = o if isinstance(o, set) else _subject(o)
        if not b:
            continue
        # A title that reduces to one or two content words ("You Were Built for
        # More Than This" -> {built}) is too thin to stand for a subject: scored
        # against the shorter set it matches everything sharing that one word.
        # Judge those against the longer set instead.
        n = min(len(a), len(b))
        if n < 3:
            n = max(len(a), len(b))
        if len(a & b) / float(n) >= NEAR_DUP:
            return True"""


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "too thin to stand for a subject" in s:
        print("  already patched: %s" % rel)
        return
    if s.count(OLD) != 1:
        raise SystemExit("%s: comparison found %d times" % (rel, s.count(OLD)))
    s = s.replace(OLD, NEW)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
