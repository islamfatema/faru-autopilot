# -*- coding: utf-8 -*-
"""Put the real thing on the thumbnail too.

The thumbnail is the whole click decision, and ours is a generated painting of
roughly the right subject. A photograph of the actual thermopolium counter in
Pompeii, or of the Antikythera mechanism in its case, is sharper, stranger and
demonstrably real - and it is the same free material the film is now built
from.

thumb.json may carry "real": the first entry of the episode's own reals list.
The generator tries Commons first and falls back to generating, so an episode
without one behaves exactly as before.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = ["autopilot_us", "autopilot_fun", "autopilot_history"]

# ---------------------------------------------------------------- thumb.py
HELPER = '''
COMMONS = "https://commons.wikimedia.org/w/api.php"
FREE_LICENCE = ("public domain", "pd-", "cc0", "no restrictions", "cc by", "cc-by")


def fetch_real(query, dst):
    """A freely licensed photograph of the real subject, largest first."""
    try:
        url = ("%s?action=query&generator=search&gsrnamespace=6&gsrsearch=%s"
               "&gsrlimit=10&prop=imageinfo&iiprop=url|extmetadata|size"
               "&iiurlwidth=1600&format=json"
               % (COMMONS, urllib.parse.quote(query)))
        req = urllib.request.Request(url, headers={
            "User-Agent": "faru-autopilot/1.0 (thumbnail; islamfatema04@gmail.com)"})
        pages = (json.loads(urllib.request.urlopen(req, timeout=45).read())
                 .get("query") or {}).get("pages") or {}
    except Exception as e:
        print("commons thumb search failed:", str(e)[:60])
        return False
    best = None
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        lic = ((info.get("extmetadata") or {}).get("LicenseShortName", {})
               .get("value") or "").lower()
        if not any(m in lic for m in FREE_LICENCE):
            continue
        wpx, hpx = info.get("width") or 0, info.get("height") or 0
        if wpx < 1100 or hpx < 600:          # a thumbnail is 1280x720
            continue
        cand = (wpx * hpx, info.get("thumburl") or info.get("url"))
        if not best or cand[0] > best[0]:
            best = cand
    if not best:
        return False
    try:
        req = urllib.request.Request(best[1], headers={"User-Agent": "faru-autopilot/1.0"})
        data = urllib.request.urlopen(req, timeout=90).read()
        if len(data) < 20000:
            return False
        open(dst, "wb").write(data)
        print("thumbnail uses a real photograph")
        return True
    except Exception as e:
        print("commons thumb download failed:", str(e)[:60])
        return False

'''

OLD_BUILD = '''def build(img_prompt, line1, line2, out, badge=None):
    tmp = os.path.join(HERE, "_thumb_src.jpg")
    base = Image.open(tmp).convert("RGB").resize((W,H), Image.LANCZOS) if (fetch(img_prompt, tmp) and os.path.exists(tmp)) \\
           else Image.new("RGB",(W,H),(14,27,42))'''
NEW_BUILD = '''def build(img_prompt, line1, line2, out, badge=None, real=None):
    tmp = os.path.join(HERE, "_thumb_src.jpg")
    # A photograph of the real object beats a painting of roughly that object,
    # and it is the same free material the film itself is built from.
    got = (real and fetch_real(real, tmp)) or fetch(img_prompt, tmp)
    base = Image.open(tmp).convert("RGB").resize((W,H), Image.LANCZOS) if (got and os.path.exists(tmp)) \\
           else Image.new("RGB",(W,H),(14,27,42))'''

OLD_MAIN = '''    build(cfg["img"], cfg["line1"], cfg.get("line2",""), sys.argv[2], cfg.get("badge"))'''
NEW_MAIN = '''    build(cfg["img"], cfg["line1"], cfg.get("line2",""), sys.argv[2],
          cfg.get("badge"), cfg.get("real"))'''

# ---------------------------------------------------------------- makeboard.py
OLD_THUMB = '''    thumb = {'''
NEW_THUMB = '''    # The episode's first real subject, so the thumbnail can be a photograph
    # of the thing the film is about.
    _reals = [r for r in (topic.get("reals") or []) if str(r).strip()]
    thumb = {
        "real": _reals[0] if _reals else None,'''


def patch_thumb(path):
    s = io.open(path, encoding="utf-8").read()
    if "def fetch_real" in s:
        print("  already patched: %s" % path)
        return
    for old, what in ((OLD_BUILD, "build"), (OLD_MAIN, "main")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (path, what, s.count(old)))
    s = s.replace(OLD_BUILD, NEW_BUILD).replace(OLD_MAIN, NEW_MAIN)
    s = s.replace("def fetch(prompt, dst):", HELPER.strip("\n") + "\n\n\ndef fetch(prompt, dst):", 1)
    ast.parse(s)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("  patched %s" % path)


def patch_board(path):
    s = io.open(path, encoding="utf-8").read()
    if '"real": _reals[0]' in s:
        print("  already patched: %s" % path)
        return
    if s.count(OLD_THUMB) != 1:
        raise SystemExit("%s: thumb spec found %d times" % (path, s.count(OLD_THUMB)))
    s = s.replace(OLD_THUMB, NEW_THUMB)
    ast.parse(s)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("  patched %s" % path)


for ch in CHANNELS:
    patch_thumb(os.path.join(ROOT, ch, "longform", "thumb.py"))
    patch_board(os.path.join(ROOT, ch, "longform", "makeboard.py"))
print("done")
