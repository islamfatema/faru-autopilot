# -*- coding: utf-8 -*-
"""Publish and repair the on-formula scripts first.

The briefs govern scripts written from today. The banks hold about two
thousand written before, and nothing in the machine knows which of those are
about the right things. Left alone:

  - the rotation publishes them in bank order, so FaRu Fact keeps posting
    chameleons and forgotten wars while the body scripts wait months
  - expand.py spends the whole Gemini budget lengthening them, because it
    deliberately keeps titles unchanged - it would make "Chameleons Don't
    Change Color To Camouflage" thirty seconds instead of twelve, and that
    video already had its chance at 226 views and zero of anything else

tools/formula.py scores a script against what its own channel measurably
converts on. It separates the known winners from the known duds 43 times out
of 43. This wires that score into two places:

  main_*.py biased_bank()  - on-formula scripts play first
  expand.py                - the repair budget is spent on them first

It is a RANKING in both places, never a filter. Nothing is deleted and nothing
is permanently withheld; a low-scoring script simply waits behind the ones the
numbers favour. The sample behind the FaRu and History patterns is small - one
or two comments per video - and a ranking degrades gracefully if the pattern
turns out to be weaker than it looks, where a filter would not.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAINS = [("autopilot_us/main_us.py", "us"),
         ("autopilot_fun/main_fun.py", "fun"),
         ("autopilot_history/main_history.py", "history")]

IMPORT = '''
# The measured formula for this channel - see tools/formula.py. Optional on
# purpose: a posting run must never fail because a ranking helper moved.
try:
    sys.path.insert(0, os.path.join(HERE, "..", "tools"))
    import formula as _formula
except Exception as _e:
    _formula = None
    print("formula ranking unavailable (%s) - falling back to length only"
          % str(_e)[:60], flush=True)

'''

OLD_RANK = '''        return (0 if overturns_assumption(d) else 1,
                0 if spoken_words(d) >= 78 else 1,
                0 if wt & set(t.lower() for t in d.get("tags", [])) else 1)'''

NEW_RANK = '''        # What the channel actually converts on comes first. Rise gains 11.1
        # subscribers per thousand on a statement about the viewer; FaRu gains
        # 6.2 on the viewer's own body and nothing at all on zoo trivia;
        # History gains most on Rome doing something we assume is modern.
        # Negative so higher scores sort earlier.
        fit = -_formula.score(CHANNEL_KEY, d) if _formula else 0
        return (fit,
                0 if overturns_assumption(d) else 1,
                0 if spoken_words(d) >= 78 else 1,
                0 if wt & set(t.lower() for t in d.get("tags", [])) else 1)'''


def patch_main(rel, key):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "_formula" in s:
        print("  already ranked: %s" % rel)
        return
    if s.count(OLD_RANK) != 1:
        raise SystemExit("%s: rank tuple found %d times" % (rel, s.count(OLD_RANK)))
    s = s.replace(OLD_RANK, NEW_RANK)
    anchor = "def biased_bank():"
    i = s.index(anchor)
    s = s[:i] + IMPORT.lstrip("\n") + "\n" + s[i:]
    write(path, s)


EXP_OLD = '''    todo = [i for i, d in enumerate(bank)
            if too_short(d) and grow.norm_title(d["title"]) not in published]'''

EXP_NEW = '''    todo = [i for i, d in enumerate(bank)
            if too_short(d) and grow.norm_title(d["title"]) not in published]
    # Spend the budget on the scripts this channel actually converts on. The
    # rewrite keeps the title, so lengthening a subject that already failed
    # buys a longer version of a video nobody responded to.
    if formula is not None:
        todo.sort(key=lambda i: -formula.score(key, bank[i]))
        best = formula.score(key, bank[todo[0]]) if todo else 0
        worst = formula.score(key, bank[todo[-1]]) if todo else 0
        print("  ordered by fit to what this channel converts on "
              "(best %d, worst %d)" % (best, worst), flush=True)'''

EXP_IMPORT = '''import grow  # noqa: E402  - reuses the model discovery, budget and validator

try:
    import formula
except Exception as _e:      # a ranking helper must never stop the repair
    formula = None
    print("formula ranking unavailable (%s)" % str(_e)[:60])'''


def patch_expand():
    path = os.path.join(ROOT, "tools", "expand.py")
    s = io.open(path, encoding="utf-8").read()
    if "import formula" in s:
        print("  already ranked: tools/expand.py")
        return
    s = s.replace("import grow  # noqa: E402  - reuses the model discovery, "
                  "budget and validator", EXP_IMPORT, 1)
    if s.count(EXP_OLD) != 1:
        raise SystemExit("expand.py: todo list found %d times" % s.count(EXP_OLD))
    s = s.replace(EXP_OLD, EXP_NEW)
    write(path, s)


def write(path, s):
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % os.path.basename(path))


for rel, key in MAINS:
    patch_main(rel, key)
patch_expand()
print("done")
