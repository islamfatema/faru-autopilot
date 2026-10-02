# -*- coding: utf-8 -*-
"""A quality gate must never stop the channel from publishing.

What happened, measured on 1 October: History published 6 Shorts in ten days
instead of 50, Rise 11 instead of 50, and the 28-day view totals fell with them -
History 43,611 to 27,137, Rise 17,764 to 4,863. The cause was not YouTube. It
was the gates added on 15 September: with 573 unpublished scripts in History's
bank, not one cleared VIEW and WATCH, so every run ended with "no unpublished
script currently meets the quality bar" and nothing went out.

A gate that can silence a channel is worse than the weak video it was built to
stop. They now rank instead of block, in tiers, and the run says which tier it
had to fall back to:

    tier 0   everything: length floor, five triggers, no near-duplicates
    tier 1   drop the trigger gate - the title is weaker, the video is real
    tier 2   drop the length floor too, keeping 6 captions and 50 spoken words

Near-duplicates are never relaxed: publishing the same fact twice is the one
failure that cannot be undone by the next upload.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

OLD_GATE = '''def worth_publishing(d):
    caps = d.get("phrases") or []'''
NEW_GATE = '''def worth_publishing(d, tier=0):
    """Is this script publishable at this tier?

    tier 0 is everything. Higher tiers drop one gate each, and exist because a
    gate that empties the schedule costs more than the video it blocked: on
    1 October, with 573 unpublished scripts in the bank, not one cleared tier 0
    and the channel published six Shorts in ten days.
    """
    caps = d.get("phrases") or []
    if tier >= 2:
        # last resort: a real video, shorter than the floor, still a whole thought
        spoken = sum(len(p.replace(chr(10), " ").split()) for p in caps)
        return len(caps) >= 6 and spoken >= 50'''
OLD_TRIG = '''    if _triggers is not None:
        bad = _triggers.blocked(d)'''
NEW_TRIG = '''    if _triggers is not None and tier == 0:
        bad = _triggers.blocked(d)'''

OLD_TAKE = '''            if key in self.seen or key in self.taken:
                continue
            if not worth_publishing(d):
                continue
            # The same fact under another title - "Ancient Romans Used Concrete
            # That Heals Itself" after "Ancient Roman Concrete Can Heal Itself"
            # had already gone out. Checked against this run's picks too.
            if near_duplicate(d["title"], self._subjects()):
                continue
            self.taken.add(key)
            self.published.append(key)
            self._taken_subjects.append(_subject(d["title"]))
            return pos'''
NEW_TAKE = '''            if key in self.seen or key in self.taken:
                continue
            if not worth_publishing(d, self.tier):
                continue
            # The same fact under another title - "Ancient Romans Used Concrete
            # That Heals Itself" after "Ancient Roman Concrete Can Heal Itself"
            # had already gone out. Checked against this run's picks too. This
            # one is never relaxed: a duplicate is the only failure the next
            # upload cannot make up for.
            if near_duplicate(d["title"], self._subjects()):
                continue
            self.taken.add(key)
            self.published.append(key)
            self._taken_subjects.append(_subject(d["title"]))
            return pos'''

OLD_RAISE = '''        raise RuntimeError("no unpublished script currently meets the quality bar "
                           "- the generator needs to catch up before posting again")'''
NEW_RAISE = '''        # Nothing at this tier. Relax one gate and look again rather than
        # publishing nothing: an empty schedule is what actually cost the
        # channels their reach in late September.
        if self.tier < 2:
            self.tier += 1
            print("  nothing clears tier %d - falling back to tier %d (%s)"
                  % (self.tier - 1, self.tier,
                     "without the trigger gate" if self.tier == 1
                     else "without the length floor"), flush=True)
            return self.take(i)
        raise RuntimeError("no unpublished script left at all - the generator "
                           "needs to catch up before posting again")'''

OLD_INIT = '''        self.taken = set()
        self.published = []          # handed out this run, for the ledger'''
NEW_INIT = '''        self.taken = set()
        self.tier = 0                # 0 = every gate; raised only when nothing passes
        self.published = []          # handed out this run, for the ledger'''

OLD_PEEK_GATE = '''            if not worth_publishing(d):
                continue
            if near_duplicate(d["title"], self._subjects()):
                continue
            return d["title"]'''
NEW_PEEK_GATE = '''            if not worth_publishing(d, self.tier):
                continue
            if near_duplicate(d["title"], self._subjects()):
                continue
            return d["title"]'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def worth_publishing(d, tier=0)" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_GATE, "gate"), (OLD_TRIG, "trigger check"),
                      (OLD_TAKE, "take"), (OLD_RAISE, "raise"), (OLD_INIT, "init"),
                      (OLD_PEEK_GATE, "peek")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))
    s = (s.replace(OLD_GATE, NEW_GATE).replace(OLD_TRIG, NEW_TRIG)
          .replace(OLD_TAKE, NEW_TAKE).replace(OLD_RAISE, NEW_RAISE)
          .replace(OLD_INIT, NEW_INIT).replace(OLD_PEEK_GATE, NEW_PEEK_GATE))
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
