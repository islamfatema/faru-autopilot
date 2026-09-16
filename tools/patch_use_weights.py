# -*- coding: utf-8 -*-
"""Let the measured data choose what publishes next.

The rotation has been ordered by a hand-written formula since the day the
per-channel patterns were first measured. That formula was right at the time
and it is frozen: it cannot notice that a subject family stopped working in
October, because nothing feeds yesterday's numbers back into it.

growth/apply.py writes analytics/weights_<key>.json from the diagnosis of every
video on the channel. This makes the picker read it: subjects the data prefers
play first, subjects already tested and lost play last. If the file is missing -
before the first collection, or if a run fails - the rotation behaves exactly as
it did before.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

HELPER = '''
def learned_weights():
    """What the growth loop measured: subjects to play first, and to hold back.

    Written daily by growth/apply.py from the diagnosis of every video on this
    channel. Missing file means the loop has not run yet, and the rotation
    falls back to the hand-written formula alone.
    """
    p = os.path.join(HERE, "..", "analytics", "weights_%s.json" % CHANNEL_KEY)
    try:
        w = json.load(open(p, encoding="utf-8"))
    except Exception:
        return {"prefer": set(), "avoid": set(), "recovery": False}
    return {"prefer": set(t.lower() for t in w.get("prefer_tags") or []),
            "avoid": set(t.lower() for t in w.get("avoid_tags") or []),
            "recovery": bool(w.get("recovery_mode"))}

'''

OLD_RANK = '''        fit = -_formula.score(CHANNEL_KEY, d) if _formula else 0
        # The hand-written, sourced series runs first and in its own order:
        # each episode ends by naming the next one, so they cannot be shuffled.
        return (0 if d.get("series") else 1,
                d.get("series_n", 0),
                fit,'''
NEW_RANK = '''        fit = -_formula.score(CHANNEL_KEY, d) if _formula else 0
        # What the numbers said yesterday, ahead of what the formula said in
        # September: a subject family this channel has already lost with sorts
        # last, one it wins with sorts first.
        tags = set(t.lower() for t in d.get("tags", []))
        measured = 0
        if tags & _WEIGHTS["avoid"]:
            measured = 1
        elif tags & _WEIGHTS["prefer"]:
            measured = -1
        # The hand-written, sourced series runs first and in its own order:
        # each episode ends by naming the next one, so they cannot be shuffled.
        return (0 if d.get("series") else 1,
                d.get("series_n", 0),
                measured,
                fit,'''

OLD_CALL = "BANK_ORDERED = biased_bank()"
NEW_CALL = '''_WEIGHTS = learned_weights()
if _WEIGHTS["prefer"] or _WEIGHTS["avoid"]:
    print("measured: playing %d preferred subjects first, holding back %d"
          % (len(_WEIGHTS["prefer"]), len(_WEIGHTS["avoid"])), flush=True)
if _WEIGHTS["recovery"]:
    print("measured: this channel is in RECOVERY - the generators have been told "
          "to change the failing variable", flush=True)
BANK_ORDERED = biased_bank()'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def learned_weights" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_RANK, "rank"), (OLD_CALL, "bank build")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))
    s = s.replace(OLD_RANK, NEW_RANK).replace(OLD_CALL, NEW_CALL)
    s = s.replace("def biased_bank():", HELPER.strip("\n") + "\n\n\ndef biased_bank():", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
