# -*- coding: utf-8 -*-
"""Search Commons once per subject, and use a different photograph each time.

An episode carries about ten real subjects and assigns them to eighteen shots,
so the same search runs twice. Commons rate-limits bursts - measured, the
eleventh search in a row returns 429 - and each retry sleeps six, twelve, then
eighteen seconds, which is how a render that used to take forty minutes went
past an hour.

Searching once and keeping the candidate list fixes both problems at once: half
the requests disappear, and the second shot on a subject takes the *second*
photograph rather than the same one again, so a repeated subject does not look
like a repeated frame.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = ["autopilot_us", "autopilot_fun", "autopilot_history"]

OLD_HEAD = '''def commons_photo(query, dst_abs, w=1280, h=720):'''
NEW_HEAD = '''_COMMONS_CACHE = {}      # query -> candidates, newest search wins
_COMMONS_TAKEN = {}      # query -> how many of those have been used


def commons_photo(query, dst_abs, w=1280, h=720):'''

OLD_SEARCH = '''    try:
        url = ("%s?action=query&generator=search&gsrnamespace=6&gsrsearch=%s"'''
NEW_SEARCH = '''    if query in _COMMONS_CACHE:
        return _commons_use(query, dst_abs, w, h)
    try:
        url = ("%s?action=query&generator=search&gsrnamespace=6&gsrsearch=%s"'''

OLD_PICK = '''    best = None
    for p in pages.values():'''
NEW_PICK = '''    found = []
    for p in pages.values():'''

OLD_CAND = '''        px = (info.get("width") or 0) * (info.get("height") or 0)
        if px < 400000:                      # too small to move a camera across
            continue
        cand = (px, p["title"][5:], lic, credit, info.get("thumburl") or info.get("url"))
        if not best or cand[0] > best[0]:
            best = cand
    if not best:
        return False

    _px, title, lic, credit, src = best
    tmp = dst_abs + ".src"'''
NEW_CAND = '''        px = (info.get("width") or 0) * (info.get("height") or 0)
        if px < 400000:                      # too small to move a camera across
            continue
        found.append((px, p["title"][5:], lic, credit,
                      info.get("thumburl") or info.get("url")))
    if not found:
        return False
    found.sort(key=lambda c: -c[0])          # biggest first
    _COMMONS_CACHE[query] = found
    return _commons_use(query, dst_abs, w, h)


def _commons_use(query, dst_abs, w, h):
    """Download the next unused photograph of this subject."""
    found = _COMMONS_CACHE.get(query) or []
    if not found:
        return False
    i = _COMMONS_TAKEN.get(query, 0)
    if i >= len(found):
        i = 0                                 # exhausted: start again
    _COMMONS_TAKEN[query] = i + 1
    _px, title, lic, credit, src = found[i]
    tmp = dst_abs + ".src"'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "_COMMONS_CACHE" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_HEAD, "head"), (OLD_SEARCH, "search"),
                      (OLD_PICK, "pick"), (OLD_CAND, "candidate")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))
    s = s.replace(OLD_HEAD, NEW_HEAD).replace(OLD_SEARCH, NEW_SEARCH)
    s = s.replace(OLD_PICK, NEW_PICK).replace(OLD_CAND, NEW_CAND)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for ch in CHANNELS:
    patch(os.path.join(ch, "longform", "docgen2.py"))
print("done")
