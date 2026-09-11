# -*- coding: utf-8 -*-
"""Give the viewer a reason to subscribe: tell them what is next.

The measured problem is not reach, it is return:

    FaRu Fact, 28 days:   11,321 views from people who are not subscribed
                              65 views from people who are

People watch and do not come back, because nothing tells them there is anything
to come back for. Every video ends on a question - which earns comments - and
some end on "send this to..." - which earns shares. None of them gives a reason
to subscribe. The description says "subscribe", and nobody opens a Shorts
description.

The strongest reason to follow is a specific thing you will otherwise miss. The
machine already knows what the next video is - the picker has the ranked bank
and the ledger - so every video now closes by naming it:

    Next: Your Brain Can't Actually Feel Pain
    Follow so you catch it.

It is different on every video, because the next title is different, so it does
not become the repeated canned line that made the old endings feel identical.
If the next title will not fit two caption lines it is not truncated into
something that reads oddly aloud - the line becomes "Follow for tomorrow's".
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

HELPER = '''
LINE_MAX = 34      # the caption renderer's width per line


def _clean_title(t):
    """The title as a person would say it: no hashtags, no emoji."""
    t = re.sub(r"#\\w+", " ", t or "")
    t = "".join(ch for ch in t if ord(ch) < 0x2190 or ch in "'")
    return " ".join(t.replace("!", "").split())


def _wrap(text, width=LINE_MAX, lines=2):
    """Wrap at word boundaries into at most `lines` lines, or None if it will
    not fit. A title cut mid-thought reads strangely when it is spoken."""
    out, cur = [], ""
    for w in text.split():
        nxt = (cur + " " + w).strip()
        if len(nxt) <= width:
            cur = nxt
        else:
            out.append(cur)
            cur = w
            if len(out) >= lines:
                return None
    if cur:
        out.append(cur)
    return out if len(out) <= lines else None


def next_up_captions(next_title):
    """Two closing captions naming the next video, the reason to subscribe."""
    t = _clean_title(next_title) if next_title else ""
    wrapped = _wrap("Next: " + t) if t else None
    if wrapped:
        return ["\\n".join(wrapped), "Follow so you catch it."]
    return ["Follow for tomorrow's."]

'''

PEEK = '''
    def peek(self):
        """The title that will publish after the one just taken - without
        taking it. Used to tell the viewer what is coming next."""
        if self.seen is None:
            return None
        for d in BANK_ORDERED:
            key = norm_title(d["title"])
            if key in self.seen or key in self.taken:
                continue
            if not worth_publishing(d):
                continue
            return d["title"]
        return None
'''

OLD_TAKE = '''        raise RuntimeError("no unpublished script currently meets the quality bar "
                           "- the generator needs to catch up before posting again")'''

OLD_BUILD_SIG = "def build_one(idx):"
NEW_BUILD_SIG = "def build_one(idx, next_title=None):"

OLD_ENDER = '''    if not phrases[-1].rstrip().endswith("?"):
        phrases = phrases + [ENDERS[idx % len(ENDERS)]]'''
NEW_ENDER = '''    if not phrases[-1].rstrip().endswith("?"):
        phrases = phrases + [ENDERS[idx % len(ENDERS)]]
    # The reason to subscribe. 11,321 of FaRu's views in a month came from
    # people not subscribed and 65 from people who were - nobody comes back,
    # because nothing tells them there is a next thing to come back for.
    phrases = phrases + next_up_captions(next_title)'''

OLD_CALL = "            mp4, meta = build_one(picker.take(i))"
NEW_CALL = '''            pos = picker.take(i)
            mp4, meta = build_one(pos, next_title=picker.peek())'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def next_up_captions" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_TAKE, "take() tail"), (OLD_BUILD_SIG, "build_one"),
                      (OLD_ENDER, "ender"), (OLD_CALL, "main call")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))
    s = s.replace(OLD_TAKE, OLD_TAKE + "\n" + PEEK.rstrip("\n"))
    s = s.replace(OLD_BUILD_SIG, NEW_BUILD_SIG)
    s = s.replace(OLD_ENDER, NEW_ENDER)
    s = s.replace(OLD_CALL, NEW_CALL)
    s = s.replace(NEW_BUILD_SIG, HELPER.strip("\n") + "\n\n\n" + NEW_BUILD_SIG, 1)
    if "\nimport re" not in s and "import re," not in s and ", re" not in s:
        s = s.replace("import os", "import os\nimport re", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
