# -*- coding: utf-8 -*-
"""Point the Shorts at the documentaries.

Where the money actually is, measured on these channels today:

    History   150 Shorts, 25,481 views    long-form: 2 videos
    Rise      229 Shorts, 26,808 views    long-form: 2 videos
    FaRu      135 Shorts,  5,762 views    long-form: 0 videos

Shorts pay roughly $0.02 per thousand views. Fifty eight thousand views is
therefore about a dollar. Long-form on a US history or money audience pays
$8-15 per thousand, and only long-form accumulates the watch hours that open
the Partner Programme in the first place.

So the Shorts are not the product. They are the only traffic these channels
have - roughly 2,700 views a day on History alone - and until now not one of
those views was pointed at a documentary. The description sold the app and
never mentioned that the channel has a twelve minute film on the same subject.

This wires the funnel:

  - publish.py records every documentary it uploads in the channel's
    featured_long.json, which the workflow commits back
  - main_*.py reads that file and opens every Shorts description with a link
    to the newest one

If the file is missing the line is simply omitted, so a channel with no
documentary yet is unaffected and nothing can break the posting run.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHANNELS = [("autopilot_us", "main_us.py"),
            ("autopilot_fun", "main_fun.py"),
            ("autopilot_history", "main_history.py")]

# ---------------------------------------------------------------- publish.py
PUB_OLD = '''    print("UPLOADED https://youtu.be/%s" % vid, flush=True)'''

PUB_NEW = '''    print("UPLOADED https://youtu.be/%s" % vid, flush=True)
    record_featured(vid, meta.get("title", ""))'''

PUB_FUNC = '''
def record_featured(vid, title):
    """Tell the Shorts machine which documentary to send viewers to.

    The Shorts are the only traffic these channels have and they pay almost
    nothing - about two cents per thousand views. The documentaries pay several
    dollars per thousand and are what accumulates watch hours. Linking one to
    the other is free, so every Short published after this points at the newest
    film. The Shorts run reads this file; if it is absent it just omits the line.
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(os.path.dirname(here), "featured_long.json")
        json.dump({"id": vid, "title": title,
                   "url": "https://youtu.be/%s" % vid},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("featured long-form recorded: %s" % vid, flush=True)
    except Exception as e:
        print("could not record the featured video: %s" % str(e)[:120], flush=True)


'''

# ---------------------------------------------------------------- main_*.py
MAIN_FUNC = '''
def featured_long():
    """The newest documentary on this channel, or None.

    Every Short carries a link to it. This is the whole funnel: Shorts bring
    the traffic and pay about two cents a thousand, the documentaries pay
    several dollars a thousand and build the watch hours that open the Partner
    Programme. Written by longform/publish.py on each upload.
    """
    try:
        d = json.load(io.open(os.path.join(HERE, "featured_long.json"),
                              encoding="utf-8"))
        if d.get("url") and d.get("title"):
            return d
    except Exception:
        pass
    return None


def featured_line():
    f = featured_long()
    if not f:
        return ""
    return "\\u25b6 FULL DOCUMENTARY: %s\\n   %s\\n\\n" % (f["title"][:70], f["url"])


'''


def patch_publish(rel):
    path = os.path.join(ROOT, rel, "longform", "publish.py")
    s = io.open(path, encoding="utf-8").read()
    if "def record_featured" in s:
        print("  publish.py already patched")
        return
    if s.count(PUB_OLD) != 1:
        raise SystemExit("%s: UPLOADED line found %d times" % (path, s.count(PUB_OLD)))
    s = s.replace(PUB_OLD, PUB_NEW)
    # Insert the helper above upload() so it is defined before use.
    marker = "def upload("
    i = s.index(marker)
    s = s[:i] + PUB_FUNC.lstrip("\n") + s[i:]
    write(path, s)


def patch_main(rel, name):
    path = os.path.join(ROOT, rel, name)
    s = io.open(path, encoding="utf-8").read()
    if "def featured_line" in s:
        print("  %s already patched" % name)
        return

    marker = "def build_one("
    i = s.index(marker)
    s = s[:i] + MAIN_FUNC.lstrip("\n") + s[i:]

    # The link goes first. A Shorts description is collapsed to one line in the
    # app, so anything below the fold is not read at all.
    old = '    desc = ("'
    if s.count(old) != 1:
        raise SystemExit("%s: desc assignment found %d times" % (name, s.count(old)))
    s = s.replace(old, '    desc = (featured_line() + "', 1)

    if "import io" not in s:
        s = s.replace("import os, sys, json,", "import io, os, sys, json,", 1)
    write(path, s)


def write(path, s):
    # Validate before writing. Opening in "w" truncates the file before it
    # validates its own arguments, which is how main_us.py became zero bytes.
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % os.path.basename(path))


for rel, name in CHANNELS:
    print(rel)
    patch_publish(rel)
    patch_main(rel, name)
print("done")
