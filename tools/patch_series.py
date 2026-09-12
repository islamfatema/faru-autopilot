# -*- coding: utf-8 -*-
"""Let a hand-written, sourced Short go out exactly as it was written.

The 42 scripts in the week-one package are not what the generator produces.
Each one is a checked fact with a named source, a designed first frame, its own
ending and its own line naming the next episode in the series. The machine, as
it stands, would do four things to them:

  * refuse them - worth_publishing wants 78 spoken words (the 30-second floor),
    and these are written to the 15-22 second brief at 54-62;
  * append a canned ender on top of the ending they already have;
  * append "Next: <whatever the picker peeks at>", replacing a line that names
    the actual next episode in the series;
  * generate every image from one prompt, when each one carries a prompt per
    shot.

So a bank entry may now carry "series": the series name and number. That flag,
and only that flag, changes those four behaviours:

    series floor       6 captions, 50 spoken words (about 20 seconds)
    endings            left alone - the script wrote its own
    next-up            left alone - the script names the next episode
    images             one per prompt in "imgs", cycled over the captions
    description        "desc" is used in place of the narration paragraph

Series entries also sort to the front of the rotation, ahead of the formula
ordering, so the seven days run in order and finish before the generated bank
resumes.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

# 1. rotation: the series runs first, in its own order
OLD_RANK = """        fit = -_formula.score(CHANNEL_KEY, d) if _formula else 0
        return (fit,"""
NEW_RANK = """        fit = -_formula.score(CHANNEL_KEY, d) if _formula else 0
        # The hand-written, sourced series runs first and in its own order:
        # each episode ends by naming the next one, so they cannot be shuffled.
        return (0 if d.get("series") else 1,
                d.get("series_n", 0),
                fit,"""

# 2. the quality gate knows about the shorter, deliberate form
OLD_GATE = '''def worth_publishing(d):
    caps = d.get("phrases") or []'''
NEW_GATE = '''def worth_publishing(d):
    caps = d.get("phrases") or []
    if d.get("series"):
        # Written to the 15-22 second brief on purpose, with a checked source
        # behind every line. The 30-second floor exists to keep ten-second
        # recitations off the channel; it should not throw these out.
        spoken = sum(len(p.replace(chr(10), " ").split()) for p in caps)
        return len(caps) >= 6 and spoken >= 50'''

# 3. endings and next-up: the script wrote its own
OLD_END = """    if not phrases[-1].rstrip().endswith("?"):
        phrases = phrases + [ENDERS[idx % len(ENDERS)]]"""
NEW_END = """    if not d.get("series") and not phrases[-1].rstrip().endswith("?"):
        phrases = phrases + [ENDERS[idx % len(ENDERS)]]"""

OLD_NEXT = "    phrases = phrases + next_up_captions(next_title)"
NEW_NEXT = """    if not d.get("series"):
        phrases = phrases + next_up_captions(next_title)"""

# 4. one image per shot when the script carries a shot list
HELPER = '''
def get_shot_images(prompts, n, slot):
    """One image per written shot, cycled if there are more captions than shots.

    get_images() varies one prompt by camera angle, which is right for a script
    that only names its subject. A series episode names four shots - what is in
    frame, how it is lit, how it cuts - so each one is generated from its own
    prompt and held for its share of the captions.
    """
    paths = []
    for i, p in enumerate(prompts[:MAX_IMAGES]):
        got = _generated(i, p)
        if not got:
            urls = _photos(" ".join(p.split()[:8]), 1)
            if urls:
                try:
                    got = _download(urls[0], os.path.join(WORK, "img%d.jpg" % i))
                except Exception:
                    got = None
        if got:
            paths.append(got)
    if not paths:
        return get_images(prompts[0], n, slot)
    # Hold each shot across its share of the captions, in the written order.
    base = list(paths)
    return [base[i * len(base) // n] for i in range(n)]

'''

OLD_IMG = "    imgs = get_images(d.get(\"img\", "
NEW_IMG_TMPL = """    if d.get("imgs"):
        imgs = get_shot_images(d["imgs"], len(phrases), idx)
    else:
        imgs = get_images(d.get("img", %s"""

# 5. the description the script wrote
OLD_DESC = '            + d["narration"]'
NEW_DESC = '            + (d.get("desc") or d["narration"])'


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def get_shot_images" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_RANK, "rank"), (OLD_GATE, "gate"), (OLD_END, "ender"),
                      (OLD_NEXT, "next-up"), (OLD_IMG, "images"), (OLD_DESC, "description")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))

    s = s.replace(OLD_RANK, NEW_RANK)
    s = s.replace(OLD_GATE, NEW_GATE)
    s = s.replace(OLD_END, NEW_END)
    s = s.replace(OLD_NEXT, NEW_NEXT)
    s = s.replace(OLD_DESC, NEW_DESC)

    # the imgs line keeps its channel-specific default prompt; rebuild it
    lines = s.splitlines(True)
    for i, line in enumerate(lines):
        if line.startswith(OLD_IMG):
            rest = line[len(OLD_IMG):]
            lines[i] = (NEW_IMG_TMPL % rest).rstrip("\n") + "\n"
            break
    s = "".join(lines)
    s = s.replace("def build_one(", HELPER.strip("\n") + "\n\n\ndef build_one(", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
