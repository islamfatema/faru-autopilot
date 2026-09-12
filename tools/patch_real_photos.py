# -*- coding: utf-8 -*-
"""Use a photograph of the real thing where one exists.

Fatema's objection, and it is the right one: the documentaries she is asked to
compare against are built from material nobody else has, and ours are built
from images anyone can generate from the same three words. For ancient subjects
there is no film - nobody shot the Antikythera mechanism being made - but there
are photographs of the object itself, free to use, at resolutions we cannot
match: the mechanism at 5472x3648 in the National Archaeological Museum, the
complaint tablet to Ea-nasir at 4406x7876 in the British Museum.

So a shot may now carry "real": a phrase naming something photographable. When
it does, the renderer looks for a freely licensed photograph on Wikimedia
Commons first, and only generates an image if there is none. Licences are read
from the file's own metadata - public domain and CC0 are used as they are, CC BY
and CC BY-SA are used with the photographer's name collected into credits.json,
which publish.py appends to the video description. Anything else is skipped
rather than guessed at.

The storyboard writer is told to fill "real" whenever the shot is of a real
object, place, building or artwork - which, in a history documentary, is most
of them.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = ["autopilot_us", "autopilot_fun", "autopilot_history"]

# ---------------------------------------------------------------- docgen2.py
HELPER = '''
# ---------------- real photographs (Wikimedia Commons) ----------------
COMMONS = "https://commons.wikimedia.org/w/api.php"
# Licences needing no on-screen credit, and those needing a name in the
# description. Anything else is left alone - a picture is not worth a claim.
FREE_LICENCE = ("public domain", "pd-", "cc0", "no restrictions")
CREDIT_LICENCE = ("cc by", "cc-by")
CREDITS = []            # [(file title, licence, photographer)] for the description


def _strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def commons_photo(query, dst_abs, w=1280, h=720):
    """A freely licensed photograph of the real thing, cropped to the frame.

    Returns True if one was found and written. The largest usable file wins:
    these are museum photographs, often 4000px and wider, which gives the
    camera move real detail to move across instead of an upscaled blur.
    """
    try:
        url = ("%s?action=query&generator=search&gsrnamespace=6&gsrsearch=%s"
               "&gsrlimit=12&prop=imageinfo&iiprop=url|extmetadata|size"
               "&iiurlwidth=2000&format=json"
               % (COMMONS, urllib.parse.quote(query)))
        req = urllib.request.Request(url, headers={
            "User-Agent": "faru-autopilot/1.0 (documentary; islamfatema04@gmail.com)"})
        with urllib.request.urlopen(req, timeout=45) as r:
            pages = (json.loads(r.read()).get("query") or {}).get("pages") or {}
    except Exception as e:
        print("  commons search failed: %s" % str(e)[:70], flush=True)
        return False

    best = None
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName", {}).get("value") or "").strip()
        low = lic.lower()
        if any(m in low for m in FREE_LICENCE):
            credit = ""
        elif any(m in low for m in CREDIT_LICENCE):
            credit = _strip_html(meta.get("Artist", {}).get("value"))[:60]
        else:
            continue
        px = (info.get("width") or 0) * (info.get("height") or 0)
        if px < 400000:                      # too small to move a camera across
            continue
        cand = (px, p["title"][5:], lic, credit, info.get("thumburl") or info.get("url"))
        if not best or cand[0] > best[0]:
            best = cand
    if not best:
        return False

    _px, title, lic, credit, src = best
    tmp = dst_abs + ".src"
    try:
        req = urllib.request.Request(src, headers={"User-Agent": "faru-autopilot/1.0"})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
        if len(data) < 20000:
            return False
        open(tmp, "wb").write(data)
        # fill the frame without distorting the object
        run(["ffmpeg", "-y", "-i", tmp, "-vf",
             "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (w, h, w, h),
             dst_abs])
        os.remove(tmp)
    except Exception as e:
        print("  commons download failed: %s" % str(e)[:70], flush=True)
        return False

    CREDITS.append((title, lic, credit))
    print("  real photo: %s (%s)" % (title[:58], lic), flush=True)
    return True

'''

OLD_FETCH = '''def fetch(prompt, dst_abs, w=1280, h=720):
    prompt = prompt + STYLE_SUFFIX'''
NEW_FETCH = '''def fetch(prompt, dst_abs, w=1280, h=720, real=None):
    """A photograph of the real subject if the shot names one, else an image.

    Generated pictures are the fallback, not the default: they are the part of
    this documentary that anyone with the same three words could produce.
    """
    if real and commons_photo(real, dst_abs, w, h):
        return True
    prompt = prompt + STYLE_SUFFIX'''

OLD_CINE = '''def render_cinematic(idx, prompt, seconds, caption, move, extra=""):
    img = "sc%d.jpg" % idx
    ok = fetch(prompt, os.path.join(WORK, img))'''
NEW_CINE = '''def render_cinematic(idx, prompt, seconds, caption, move, extra="", real=None):
    img = "sc%d.jpg" % idx
    ok = fetch(prompt, os.path.join(WORK, img), real=real)'''

OLD_CALL = '''            clips.append(render_cinematic(i, s["img"], d, s["say"],
                                          s.get("move", moves[i % len(moves)])))'''
NEW_CALL = '''            clips.append(render_cinematic(i, s["img"], d, s["say"],
                                          s.get("move", moves[i % len(moves)]),
                                          real=s.get("real")))'''

OLD_MAPFETCH = '''    ok = fetch(spec.get("img", "antique parchment world map, muted colors, top down, no text"),'''
NEW_MAPFETCH = '''    ok = fetch(spec.get("img", "antique parchment world map, muted colors, top down, no text"),'''

CREDITS_WRITE = '''    json.dump(report, open(os.path.join(WORK, "storyboard_report.json"), "w"), indent=2)'''
CREDITS_WRITE_NEW = '''    json.dump(report, open(os.path.join(WORK, "storyboard_report.json"), "w"), indent=2)
    # Whose photographs are in this film. publish.py puts them in the
    # description; a CC BY picture without its credit is a licence breach, and
    # the credit is also the proof that the material is real.
    json.dump([{"file": t, "licence": l, "by": c} for t, l, c in CREDITS],
              open(os.path.join(WORK, "credits.json"), "w"), indent=1)
    if CREDITS:
        print("== %d real photographs used ==" % len(CREDITS), flush=True)'''

# ---------------------------------------------------------------- makeboard.py
OLD_SCHEMA = '''  "img":  a detailed image prompt for this shot, ending in ", 16:9". Describe a'''
NEW_SCHEMA = '''  "real": ONLY when this shot shows a real object, place, building, artwork,
          document or animal that has been photographed - the name a museum or
          an encyclopaedia would use, 2-6 words, no adjectives: "Antikythera
          mechanism", "Pompeii thermopolium", "Trajan's Column relief",
          "carbonised bread Herculaneum". A photograph of the real thing beats
          any generated picture and is what separates this from a slideshow, so
          fill it whenever it honestly applies. Leave it out for an imagined
          scene (a battle, a crowd, a reconstruction of a lost building).
  "img":  a detailed image prompt for this shot, ending in ", 16:9". Describe a'''

OLD_SHOT = '''        shot = {"type": typ, "move": mv, "say": say, "img": img}'''
NEW_SHOT = '''        shot = {"type": typ, "move": mv, "say": say, "img": img}
        real = str(s.get("real") or "").strip()
        if 3 <= len(real) <= 60:
            shot["real"] = real'''

# ---------------------------------------------------------------- publish.py
OLD_PUB = '''def upload(path, meta, thumb=None):'''
NEW_PUB = '''def image_credits(work_dir):
    """The photographers whose pictures are in this film, for the description."""
    try:
        rows = json.load(open(os.path.join(work_dir, "credits.json"), encoding="utf-8"))
    except Exception:
        return ""
    named = ["%s - %s%s" % (r["file"], r["licence"],
                            (", " + r["by"]) if r.get("by") else "")
             for r in rows if r.get("by")]
    if not rows:
        return ""
    out = ["", "Photographs of the real objects in this film come from Wikimedia "
               "Commons (%d of them)." % len(rows)]
    out += ["  " + n for n in named[:25]]
    return "\\n".join(out)


def upload(path, meta, thumb=None):'''


def patch_docgen(path):
    s = io.open(path, encoding="utf-8").read()
    if "def commons_photo" in s:
        print("  already patched: %s" % path)
        return False
    for old, what in ((OLD_FETCH, "fetch"), (OLD_CINE, "render_cinematic"),
                      (OLD_CALL, "dispatch"), (CREDITS_WRITE, "report write")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (path, what, s.count(old)))
    s = s.replace(OLD_FETCH, NEW_FETCH)
    s = s.replace(OLD_CINE, NEW_CINE)
    s = s.replace(OLD_CALL, NEW_CALL)
    s = s.replace(CREDITS_WRITE, CREDITS_WRITE_NEW)
    s = s.replace("def fetch(", HELPER.strip("\n") + "\n\n\ndef fetch(", 1)
    for mod in ("re", "json", "urllib.parse", "urllib.request"):
        base = mod.split(".")[0]
        if not any(l.strip() in ("import " + mod, "import " + base) or
                   l.startswith("import " + base + ",") for l in s.splitlines()):
            s = "import %s\n" % mod + s
    ast.parse(s)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("  patched %s" % path)
    return True


def patch_makeboard(path):
    s = io.open(path, encoding="utf-8").read()
    if '"real"' in s:
        print("  already patched: %s" % path)
        return False
    for old, what in ((OLD_SCHEMA, "schema"), (OLD_SHOT, "shot dict")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (path, what, s.count(old)))
    s = s.replace(OLD_SCHEMA, NEW_SCHEMA).replace(OLD_SHOT, NEW_SHOT)
    ast.parse(s)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("  patched %s" % path)
    return True


def patch_publish(path):
    s = io.open(path, encoding="utf-8").read()
    if "def image_credits" in s:
        print("  already patched: %s" % path)
        return False
    if s.count(OLD_PUB) != 1:
        raise SystemExit("%s: upload() found %d times" % (path, s.count(OLD_PUB)))
    s = s.replace(OLD_PUB, NEW_PUB)
    ast.parse(s)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("  patched %s" % path)
    return True


for ch in CHANNELS:
    print(ch)
    patch_docgen(os.path.join(ROOT, ch, "longform", "docgen2.py"))
    patch_makeboard(os.path.join(ROOT, ch, "longform", "makeboard.py"))
    patch_publish(os.path.join(ROOT, ch, "longform", "publish.py"))
print("done")
