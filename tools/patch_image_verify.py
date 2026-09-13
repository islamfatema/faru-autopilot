# -*- coding: utf-8 -*-
"""Never hand a broken image to the renderer.

The scheduled publish run died with "Invalid data found when processing input"
and lost the whole documentary. Something written into the work directory was
not a decodable picture - a Commons file that is really an SVG or a TIFF, a
half-finished download, or a generator response that was an error page with a
JPEG's file size.

Both paths now open what they wrote before believing it: if it does not decode,
the file is deleted and the caller falls back - Commons to the generator, the
generator to the plain colour plate. A missing picture costs one shot; a broken
one costs the film.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = ["autopilot_us", "autopilot_fun", "autopilot_history"]

HELPER = '''
def usable_image(path):
    """True if this file really decodes as a picture.

    A documentary was lost to a file that had a plausible size and was not an
    image at all, so nothing goes to ffmpeg unverified.
    """
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception as e:
        print("  unusable image (%s): %s" % (os.path.basename(path), str(e)[:50]),
              flush=True)
        try:
            os.remove(path)
        except Exception:
            pass
        return False

'''

OLD_CROP = '''        run(["ffmpeg", "-y", "-i", tmp, "-vf",
             "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (w, h, w, h),
             dst_abs])
        os.remove(tmp)'''
NEW_CROP = '''        if not usable_image(tmp):
            return False
        run(["ffmpeg", "-y", "-i", tmp, "-vf",
             "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (w, h, w, h),
             dst_abs])
        os.remove(tmp)
        if not usable_image(dst_abs):
            return False'''

OLD_GEN = '''            if len(data) > 8000:
                open(dst_abs, "wb").write(data); return True'''
NEW_GEN = '''            if len(data) > 8000:
                open(dst_abs, "wb").write(data)
                if usable_image(dst_abs):
                    return True'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def usable_image" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_CROP, "commons crop"), (OLD_GEN, "generator write")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))
    s = s.replace(OLD_CROP, NEW_CROP).replace(OLD_GEN, NEW_GEN)
    s = s.replace("_COMMONS_CACHE = {}", HELPER.strip("\n") + "\n\n\n_COMMONS_CACHE = {}", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for ch in CHANNELS:
    patch(os.path.join(ch, "longform", "docgen2.py"))
print("done")
