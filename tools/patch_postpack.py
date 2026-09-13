# -*- coding: utf-8 -*-
"""Keep every published Short as a ready-to-post file for the other platforms.

YouTube is one feed. The same vertical video is what TikTok, Instagram Reels and
Facebook Reels want, and a new channel usually gets more reach there than on
YouTube - but the videos only ever existed inside a GitHub runner for the four
minutes it took to upload them, and were then thrown away.

Each published Short is now also written to `_work/pack/`:

    01-horseshoe-crabs-are-older-than-trees.mp4
    01-horseshoe-crabs-are-older-than-trees.txt   <- caption + hashtags

The workflow attaches that folder to a dated GitHub release, so every video has
a permanent public link. Two things follow from that: Fatema can post them from
her phone in a few taps, and the Instagram and Facebook publishing APIs - which
fetch a video by URL rather than accepting an upload - have a URL to fetch.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

HELPER = '''
def keep_for_other_platforms(mp4, meta, idx):
    """A copy of the finished Short plus its caption, for TikTok and Reels.

    The caption is not the YouTube description: no funnel paragraph, no source
    list, just the line a person reads under a vertical video, and hashtags
    that work on those platforms.
    """
    try:
        pack = os.path.join(WORK, "pack")
        os.makedirs(pack, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-",
                      re.sub(r"#\\w+", " ", meta["title"]).lower()).strip("-")[:60]
        base = os.path.join(pack, "%02d-%s" % (idx % 100, slug or "short"))
        shutil.copy(mp4, base + ".mp4")
        tags = ["#" + t for t in meta.get("tags", [])][:6]
        caption = re.sub(r"#\\w+", "", meta["title"]).strip()
        io.open(base + ".txt", "w", encoding="utf-8", newline="\\n").write(
            caption + "\\n\\n" + " ".join(tags) + "\\n")
        print("  packed for other platforms: %s.mp4" % os.path.basename(base),
              flush=True)
    except Exception as e:
        # Never let packaging break a publish.
        print("  pack failed: %s" % str(e)[:70], flush=True)

'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def keep_for_other_platforms" in s:
        print("  already patched: %s" % rel)
        return
    anchor = "            pos = picker.take(i)\n            mp4, meta = build_one(pos, next_title=picker.peek())"
    if s.count(anchor) != 1:
        raise SystemExit("%s: main loop found %d times" % (rel, s.count(anchor)))
    s = s.replace(anchor, anchor + "\n            keep_for_other_platforms(mp4, meta, i + 1)")
    s = s.replace("def build_one(", HELPER.strip("\n") + "\n\n\ndef build_one(", 1)
    if "\nimport shutil" not in s and "shutil" not in s.split("\n")[9]:
        pass  # shutil is already imported in the shared header
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
