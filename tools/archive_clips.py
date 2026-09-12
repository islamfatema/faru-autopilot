# -*- coding: utf-8 -*-
"""Find real public-domain film for a documentary, instead of generating a picture.

Fatema's complaint is the right one: the videos she was shown as the target -
DW's, with ten and twenty million views - are made of footage nobody else has.
Ours are made of images anyone can generate from the same three words, which is
exactly why there is no reason to watch them and why the median video takes
single-digit views.

The one thing available here that cannot be mass-produced is the public domain:
newsreels, government films, NASA, Prelinger. A 1944 newsreel of the advance on
Rome is real film of a real thing, it is free to use, and no other AI channel
is cutting it into their episode because it takes work to find.

Film only exists for the last hundred-odd years, and most of these episodes are
about things nobody filmed. For those there is the second half of this tool:
photographs of the real object, from Wikimedia Commons, with the licence read
from the file's own metadata - the actual Antikythera mechanism in its case,
the actual complaint tablet in the British Museum. Also something no generator
produces, because it is a photograph of a thing that exists.

    python tools/archive_clips.py "advance on rome 1944"
    python tools/archive_clips.py --stills "Antikythera mechanism" --limit 5

Prints, for each hit: identifier, year, licence, and the direct MP4 the
storyboard renderer can download. Only items whose licence or collection marks
them public domain (or CC0 / CC-BY) are returned - a rights check is the whole
point, not a formality. Nothing is downloaded unless --download is given.
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "faru-autopilot/1.0 (documentary footage search)"}
SEARCH = "https://archive.org/advancedsearch.php"
META = "https://archive.org/metadata/"

# Collections whose material is public domain or freely licensed by policy.
# Free-text search on archive.org returns YouTube mirrors and television rips
# whose rights are somebody else's problem, so the search is restricted to
# collections that are public domain or freely licensed by policy. A clip is
# only usable if we can say why.
FREE_COLLECTIONS = [
    "universal_newsreels",       # 1929-1967 newsreels, public domain
    "prelinger",                 # Prelinger Archives - ephemeral film
    "nasa",                      # NASA - US federal, public domain
    "FedFlix",                   # US government films
    "publicmovies",              # public domain feature films
    "computerchronicles",
    "nasa_techdocs",
]
FREE_LICENCE_MARKS = ("publicdomain", "creativecommons.org/publicdomain",
                      "creativecommons.org/licenses/by/", "cc0")
VIDEO_EXT = (".mp4", ".m4v", ".ogv", ".webm", ".mpeg", ".mpg", ".mov", ".avi")
VIDEO_FORMATS = ("MPEG4", "h.264", "Ogg Video", "WebM", "MPEG2", "512Kb MPEG4",
                 "HiRes MPEG4", "QuickTime")


def _get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def search(query, limit=8):
    """Public-domain film matching a query, newest metadata first."""
    q = ('(%s) AND mediatype:(movies) AND collection:(%s)'
         % (query, " OR ".join(FREE_COLLECTIONS)))
    url = ("%s?q=%s&fl[]=identifier&fl[]=title&fl[]=year&fl[]=licenseurl"
           "&fl[]=collection&rows=%d&page=1&output=json"
           % (SEARCH, urllib.parse.quote(q), limit * 4))
    docs = _get(url)["response"]["docs"]
    out = []
    for d in docs:
        if len(out) >= limit:
            break
        why = free_because(d)
        if not why:
            continue
        d["rights"] = why
        out.append(d)
    return out


def free_because(doc):
    """Why this item may be used, or None. Never guess - no reason, no clip."""
    lic = (doc.get("licenseurl") or "").lower()
    for mark in FREE_LICENCE_MARKS:
        if mark in lic:
            return "licence: " + lic
    cols = doc.get("collection") or []
    if isinstance(cols, str):
        cols = [cols]
    for c in cols:
        if c in set(FREE_COLLECTIONS):
            return "collection: " + c
    return None


def files(identifier):
    """The playable video files in an item, largest first."""
    m = _get(META + identifier)
    out = []
    for f in m.get("files", []):
        name = f.get("name", "")
        if name.lower().endswith(VIDEO_EXT) or f.get("format") in VIDEO_FORMATS:
            out.append({"name": name,
                        "size": int(f.get("size") or 0),
                        "url": "https://archive.org/download/%s/%s"
                               % (identifier, urllib.parse.quote(name))})
    out.sort(key=lambda f: -f["size"])
    return out


COMMONS = "https://commons.wikimedia.org/w/api.php"
# Licences that need no on-screen credit. CC BY and BY-SA are usable too but
# oblige an attribution line, so they are reported separately rather than mixed
# in silently.
FREE_STILL = ("public domain", "pd-", "cc0", "no restrictions")
CREDIT_STILL = ("cc by", "cc-by")


def stills(query, limit=6):
    """Photographs of the real object, with the licence each file declares."""
    url = ("%s?action=query&generator=search&gsrnamespace=6&gsrsearch=%s"
           "&gsrlimit=%d&prop=imageinfo&iiprop=url|extmetadata|size"
           "&iiurlwidth=1600&format=json"
           % (COMMONS, urllib.parse.quote(query), limit * 3))
    pages = (_get(url).get("query") or {}).get("pages") or {}
    out = []
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName", {}).get("value") or "").strip()
        low = lic.lower()
        if any(m in low for m in FREE_STILL):
            need = ""
        elif any(m in low for m in CREDIT_STILL):
            # Commons returns the author as HTML; a credit line has to be
            # readable in a YouTube description, not marked up.
            need = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value") or "").strip()[:60]
        else:
            continue                      # unknown or non-free: not worth the risk
        out.append({"title": p["title"][5:],
                    "licence": lic,
                    "credit": need,
                    "width": info.get("width"),
                    "height": info.get("height"),
                    "url": info.get("thumburl") or info.get("url")})
    out.sort(key=lambda d: -((d["width"] or 0) * (d["height"] or 0)))
    return out[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="*", help="free text, e.g. 'advance on rome 1944'")
    ap.add_argument("--topic", help="documentary title to search for")
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--stills", action="store_true",
                    help="photographs of the real object (Wikimedia Commons) "
                         "instead of film - for anything nobody filmed")
    ap.add_argument("--download", metavar="DIR",
                    help="download the best file of each hit into DIR")
    a = ap.parse_args()

    query = " ".join(a.query) or a.topic
    if not query:
        raise SystemExit("give a query or --topic")

    if a.stills:
        found = stills(query, a.limit)
        if not found:
            print("no freely licensed photograph found for: %s" % query)
            return 1
        for d in found:
            print("%-58s %sx%s" % (d["title"][:58], d["width"], d["height"]))
            print("    %s%s" % (d["licence"],
                                ("  CREDIT REQUIRED: " + d["credit"]) if d["credit"] else ""))
            print("    %s" % d["url"])
        return 0

    hits = search(query, a.limit)
    if not hits:
        print("no public-domain film found for: %s" % query)
        return 1

    for h in hits:
        fs = files(h["identifier"])
        best = fs[0] if fs else None
        print("%-28s %-6s %s" % (h["identifier"][:28], h.get("year") or "-", h["rights"]))
        print("    %s" % str(h.get("title"))[:90])
        if best:
            print("    %s  (%.0f MB)" % (best["url"], best["size"] / 1e6))
            if a.download:
                os.makedirs(a.download, exist_ok=True)
                dst = os.path.join(a.download, h["identifier"] + os.path.splitext(best["name"])[1])
                print("    downloading -> %s" % dst, flush=True)
                req = urllib.request.Request(best["url"], headers=UA)
                with urllib.request.urlopen(req, timeout=600) as r, open(dst, "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
        else:
            print("    (no playable video file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
