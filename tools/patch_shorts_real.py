# -*- coding: utf-8 -*-
"""Put the real thing in the Shorts as well.

It worked for the documentary: a photograph of the actual Pompeii counter, the
actual Antikythera mechanism, instead of a picture generated from three words.
The Shorts have the same problem and it costs more there, because a Short is
judged in its first second - 76% of FaRu's viewers leave inside it.

A bank entry may now carry "reals": one subject per written shot, or null where
nothing real exists. The subject is photographed by somebody in a museum or on
a beach; we crop it to 9:16 over a blurred copy of itself, so nothing is cut
off and the frame is still full.

Licences are read per file exactly as in the documentary path, and CC BY / CC
BY-SA credits are appended to the Short's description.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

HELPER = '''
# ---------------- real photographs (Wikimedia Commons) ----------------
COMMONS = "https://commons.wikimedia.org/w/api.php"
FREE_LICENCE = ("public domain", "pd-", "cc0", "no restrictions")
CREDIT_LICENCE = ("cc by", "cc-by")
PHOTO_CREDITS = []       # [(file, licence, photographer)] for the description
_PHOTO_CACHE = {}


def _clean(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def real_photo(query, dst):
    """A freely licensed photograph of the real subject, filled to 9:16.

    The photograph is fitted whole over a blurred copy of itself rather than
    cropped to the middle: a museum object photographed in landscape loses its
    subject entirely to a centre crop.
    """
    if query in _PHOTO_CACHE:
        found = _PHOTO_CACHE[query]
    else:
        try:
            url = ("%s?action=query&generator=search&gsrnamespace=6&gsrsearch=%s"
                   "&gsrlimit=10&prop=imageinfo&iiprop=url|extmetadata|size"
                   "&iiurlwidth=1600&format=json"
                   % (COMMONS, urllib.parse.quote(query)))
            req = urllib.request.Request(url, headers={
                "User-Agent": "faru-autopilot/1.0 (shorts; islamfatema04@gmail.com)"})
            pages = None
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=40) as r:
                        pages = (json.loads(r.read()).get("query") or {}).get("pages") or {}
                    break
                except Exception as e:
                    if "429" not in str(e) or attempt == 2:
                        raise
                    time.sleep(6 * (attempt + 1))
            pages = pages or {}
        except Exception as e:
            print("  commons: %s" % str(e)[:60], flush=True)
            return None
        found = []
        for p in pages.values():
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            lic = (meta.get("LicenseShortName", {}).get("value") or "").strip()
            low = lic.lower()
            if any(m in low for m in FREE_LICENCE):
                credit = ""
            elif any(m in low for m in CREDIT_LICENCE):
                credit = _clean(meta.get("Artist", {}).get("value"))[:60]
            else:
                continue
            title = p["title"][5:]
            if "(ia " in title.lower() or "catalogue" in title.lower():
                continue                       # book scans are not shots
            px = (info.get("width") or 0) * (info.get("height") or 0)
            if px < 400000:
                continue
            found.append((px, title, lic, credit, info.get("thumburl") or info.get("url")))
        found.sort(key=lambda c: -c[0])
        _PHOTO_CACHE[query] = found
    if not found:
        return None

    _px, title, lic, credit, src = found[0]
    tmp = dst + ".src"
    try:
        req = urllib.request.Request(src, headers={"User-Agent": "faru-autopilot/1.0"})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
        if len(data) < 20000:
            return None
        open(tmp, "wb").write(data)
        # whole photograph over a blurred fill, so nothing is cropped away
        run(["ffmpeg", "-y", "-i", tmp, "-filter_complex",
             "[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
             "gblur=sigma=28,eq=brightness=-0.06[bg];"
             "[0:v]scale=%d:%d:force_original_aspect_ratio=decrease[fg];"
             "[bg][fg]overlay=(W-w)/2:(H-h)/2" % (W, H, W, H, W, H), dst])
        os.remove(tmp)
        from PIL import Image
        with Image.open(dst) as im:
            im.verify()
    except Exception as e:
        print("  commons photo failed: %s" % str(e)[:60], flush=True)
        return None
    PHOTO_CREDITS.append((title, lic, credit))
    print("  real photo: %s (%s)" % (title[:52], lic), flush=True)
    return dst


def photo_credit_lines():
    """Credit for the photographs used, required by CC BY and CC BY-SA."""
    named = ["%s - %s%s" % (t, l, (", " + c) if c else "")
             for t, l, c in PHOTO_CREDITS]
    if not named:
        return ""
    return ("\\n\\nPhotographs: Wikimedia Commons\\n"
            + "\\n".join("  " + n for n in named[:8]))

'''

OLD_SHOTS = '''    paths = []
    for i, p in enumerate(prompts[:MAX_IMAGES]):'''
NEW_SHOTS = '''    paths = []
    for i, p in enumerate(prompts[:MAX_IMAGES]):
        # A photograph of the real subject where the script names one. This is
        # what changed the documentaries: an image anyone can generate gives a
        # viewer no reason to stay, and the first second is the whole decision.
        want = (reals[i] if reals and i < len(reals) else None)
        if want:
            got = real_photo(want, os.path.join(WORK, "img%d.jpg" % i))
            if got:
                paths.append(got)
                continue'''

OLD_SIG = "def get_shot_images(prompts, n, slot):"
NEW_SIG = "def get_shot_images(prompts, n, slot, reals=None):"

OLD_CALL = '''        imgs = get_shot_images(d["imgs"], len(phrases), idx)'''
NEW_CALL = '''        imgs = get_shot_images(d["imgs"], len(phrases), idx, d.get("reals"))'''

OLD_DESC = '''            + (d.get("desc") or d["narration"])'''
NEW_DESC = '''            + (d.get("desc") or d["narration"]) + photo_credit_lines()'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def real_photo" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_SHOTS, "shot loop"), (OLD_SIG, "signature"),
                      (OLD_CALL, "call"), (OLD_DESC, "description")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))
    s = s.replace(OLD_SHOTS, NEW_SHOTS)
    s = s.replace(OLD_SIG, NEW_SIG)
    s = s.replace(OLD_CALL, NEW_CALL)
    s = s.replace(OLD_DESC, NEW_DESC)
    s = s.replace("def get_shot_images(", HELPER.strip("\n") + "\n\n\ndef get_shot_images(", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
