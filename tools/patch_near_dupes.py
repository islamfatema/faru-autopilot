# -*- coding: utf-8 -*-
"""Refuse to publish the same fact under a different title.

The ledger stops an exact title going out twice. It does nothing about this,
which is what the History bank was about to publish next:

    already published   Ancient Roman Concrete Can Heal Itself      950 views
    picked next         Ancient Romans Used Concrete That Heals Itself

Same fact, reworded. To a viewer - and to YouTube's inauthentic-content
detection - it is the same video again, the exact thing Fatema's first
complaint was about. grow.py deduplicates new scripts by their narration, but
the narrations differ enough to pass while the subject is identical.

Measured across History's unpublished scripts against its published ones,
matching on content words:

    overlap >= 0.80    8 would be held back
    overlap >= 0.60   25
    overlap >= 0.50   47

At 0.60 the pairs are almost all genuine repeats: Ketchup sold as medicine
twice, Harvard older than calculus twice, Anne Frank and Martin Luther King
twice, high heels made for men twice, and "Why the Alphabet Order Is ABC" in
three different wordings. The one borderline case - "The United States Is
Older Than Italy" against "...Than Germany" - is a distinct fact in an
identical frame, and holding it back costs a channel that is trying not to
feel repetitive very little.

So take() and peek() now skip any script whose subject overlaps an already
published one - or one already chosen in the same run - by 0.60 or more. It
is a skip, not a deletion: the scripts stay in the bank.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

HELPER = '''
_DUP_STOP = set(("the a an is are was were of in on to for and or not it its this that "
                 "with you your has have had can could than then more most actually "
                 "really just ago years year").split())
NEAR_DUP = 0.60


def _subject(title):
    """The content words of a title, roughly stemmed, for comparing subjects."""
    t = re.sub(r"#\\w+", " ", title or "").lower()
    out = set()
    for w in re.findall(r"[a-z]+|\\d[\\d,]*", t):
        if w in _DUP_STOP or (len(w) < 3 and not w[0].isdigit()):
            continue
        w = re.sub(r"ies$", "y", w)
        if len(w) > 4:
            w = re.sub(r"(ing|ed|es|s)$", "", w)
        out.add(w)
    return out


def near_duplicate(title, others):
    """True if this title says the same thing as one already out.

    Overlap is measured against the shorter title, so a short title wholly
    contained in a longer one counts - "Ketchup Was Sold as Medicine" against
    "Ketchup Was Once Sold as Medicine".
    """
    a = _subject(title)
    if not a:
        return False
    for o in others:
        b = o if isinstance(o, set) else _subject(o)
        if b and len(a & b) / float(min(len(a), len(b))) >= NEAR_DUP:
            return True
    return False

'''

OLD_TAKE = '''            if key in self.seen or key in self.taken:
                continue
            if not worth_publishing(d):
                continue
            self.taken.add(key)
            self.published.append(key)
            return pos'''
NEW_TAKE = '''            if key in self.seen or key in self.taken:
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

OLD_PEEK = '''            if key in self.seen or key in self.taken:
                continue
            if not worth_publishing(d):
                continue
            return d["title"]'''
NEW_PEEK = '''            if key in self.seen or key in self.taken:
                continue
            if not worth_publishing(d):
                continue
            if near_duplicate(d["title"], self._subjects()):
                continue
            return d["title"]'''

OLD_INIT = '''        self.taken = set()
        self.published = []          # handed out this run, for the ledger'''
NEW_INIT = '''        self.taken = set()
        self.published = []          # handed out this run, for the ledger
        self._taken_subjects = []    # subjects chosen this run
        self._seen_subjects = None   # built lazily from self.seen'''

SUBJECTS = '''
    def _subjects(self):
        """Subjects already out, plus those chosen this run."""
        if self._seen_subjects is None:
            self._seen_subjects = [_subject(t) for t in (self.seen or ())]
        return self._seen_subjects + self._taken_subjects
'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def near_duplicate" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_TAKE, "take"), (OLD_PEEK, "peek"), (OLD_INIT, "init")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))
    s = s.replace(OLD_TAKE, NEW_TAKE).replace(OLD_PEEK, NEW_PEEK).replace(OLD_INIT, NEW_INIT)
    # _subjects() goes right after __init__, before take()
    s = s.replace("    def take(self, i):", SUBJECTS.strip("\n") + "\n\n    def take(self, i):", 1)
    s = s.replace("class Picker:", HELPER.strip("\n") + "\n\n\nclass Picker:", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
