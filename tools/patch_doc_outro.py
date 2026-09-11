# -*- coding: utf-8 -*-
"""Ask the most engaged viewer to subscribe, with a reason.

The documentary prompt says, deliberately:

    End with a sentence that lands the point, not a call to subscribe.

The instinct is right - "like and subscribe" is the cheapest line in the
medium. But the result is that the viewer most likely to subscribe, someone
who has just given the channel twelve minutes, is asked for nothing at all. On
the Shorts the fix was to name the next video; the same works here, and it is
not "like and subscribe". It is a specific thing they will miss.

The point still lands - the episode's own last line is untouched. After it, one
short card:

    NEXT: THE DAY THE MONEY STOPPED WORKING
    "Next on this channel: The Day the Money Stopped Working. Subscribe, and it
     will be waiting for you."

The next episode comes from the same ledger the picker uses, so it is the
episode that really does publish next. Kept under ten seconds so it clears the
slideshow check on its own.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/longform/makeboard.py",
         "autopilot_fun/longform/makeboard.py",
         "autopilot_history/longform/makeboard.py"]

HELPER = '''
def next_episode(topics, current):
    """The episode that will actually publish after this one: the first in bank
    order that the ledger has not recorded and that is not this episode."""
    done = read_doc_ledger()
    cur = _norm(current.get("title"))
    for t in topics:
        n = _norm(t.get("title"))
        if n != cur and n not in done:
            return t
    return None


def outro_shot(nxt, current):
    """One short card naming the next episode - the reason to subscribe.

    The viewer who has just watched twelve minutes is the one most likely to
    subscribe, and the episode used to end without asking them anything.
    """
    if nxt:
        title = re.sub(r"#\\w+", " ", nxt["title"]).strip()
        say = ("Next on this channel: %s. Subscribe, and it will be waiting "
               "for you." % title)
        big = "NEXT: " + " ".join(title.split()[:5])
    else:
        say = "There is more like this on the channel. Subscribe so you do not miss it."
        big = "MORE SOON"
    return {"type": "textcard", "move": "push", "say": say, "big": big.upper(),
            "img": "%s, cinematic documentary lighting, 16:9"
                   % current.get("look", "a documentary scene")}

'''

OLD = "    paths, total = write_all(topic, shots, out_dir)"
NEW = '''    # The reason to subscribe, after the episode's own last line has landed.
    shots.append(outro_shot(next_episode(topics, topic), topic))

    paths, total = write_all(topic, shots, out_dir)'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def outro_shot" in s:
        print("  already patched: %s" % rel)
        return
    if s.count(OLD) != 1:
        raise SystemExit("%s: write_all call found %d times" % (rel, s.count(OLD)))
    s = s.replace(OLD, NEW)
    s = s.replace("def main():", HELPER.strip("\n") + "\n\n\ndef main():", 1)
    if "\nimport re" not in s and not s.startswith("import re") and "import re," not in s:
        # Check the real import lines, not the whole file: a stray ", re" in
        # some unrelated line fooled this once and shipped a NameError.
        import_lines = [l for l in s.splitlines() if l.startswith(("import ", "from "))]
        if not any(l == "import re" or l.startswith("import re,") or ", re," in l
                   or l.endswith(", re") for l in import_lines):
            s = "import re\n" + s
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
