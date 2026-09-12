# -*- coding: utf-8 -*-
"""Guarantee the real photographs, instead of hoping the storyboard asks for them.

The first flagship render came back with a hundred shots and not one real
photograph. The reason is in the log: the free Gemini tier answered 429 on three
models in a row, so the storyboard came out of the fallback path - which builds
shots straight from the episode's beats and never writes a "real" field. The
whole point of the change was lost to a rate limit.

So the episode itself now carries the list. A topic may hold "reals": the real,
photographable subjects of that story, named the way a museum would name them.
Any cinematic or document shot that did not ask for a photograph gets one from
that pool, alternating with generated images so the film still varies - and the
pool is the episode's own subject matter, so the picture belongs to the story
whichever shot it lands on.

If a topic has no "reals", nothing changes.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = ["autopilot_us", "autopilot_fun", "autopilot_history"]

HELPER = '''
def apply_real_pool(shots, topic):
    """Put the episode's real subjects into shots that did not ask for one.

    Written because the storyboard writer only fills "real" when the model
    answers; on the free tier it often does not, and the fallback path never
    fills it at all. Every other eligible shot takes the next subject from the
    pool, so the film alternates a photograph of the real thing with a
    generated scene instead of being a hundred generated scenes.
    """
    pool = [str(r).strip() for r in (topic.get("reals") or []) if str(r).strip()]
    if not pool:
        return 0
    used, n = 0, 0
    for s in shots:
        if s.get("real") or s.get("type") not in ("cinematic", "document"):
            continue
        n += 1
        if n % 2:                      # every other eligible shot
            s["real"] = pool[used % len(pool)]
            used += 1
    print("  real subjects: %d shots assigned from a pool of %d"
          % (used, len(pool)), flush=True)
    return used

'''

OLD_CALL = "    # The reason to subscribe, after the episode's own last line has landed."
NEW_CALL = '''    # Photographs of the real thing, for the shots that did not ask for one.
    apply_real_pool(shots, topic)

    # The reason to subscribe, after the episode's own last line has landed.'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def apply_real_pool" in s:
        print("  already patched: %s" % rel)
        return
    if s.count(OLD_CALL) != 1:
        raise SystemExit("%s: anchor found %d times" % (rel, s.count(OLD_CALL)))
    s = s.replace(OLD_CALL, NEW_CALL)
    s = s.replace("def next_episode(", HELPER.strip("\n") + "\n\n\ndef next_episode(", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for ch in CHANNELS:
    patch(os.path.join(ch, "longform", "makeboard.py"))
print("done")
