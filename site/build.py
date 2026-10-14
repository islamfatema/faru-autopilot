# -*- coding: utf-8 -*-
"""A page per video, so Google can find what YouTube is not showing anyone.

    python site/build.py            # writes docs/

787 videos exist across the three channels and almost none of them can be found
outside YouTube's own feed. YouTube decides who sees a Short; Google decides
who finds a page, and a page it can read - the full spoken text of the video,
the sources behind the claim, the video itself embedded - is a second door into
the same work that nobody can close.

What each page carries, all of it real:

    the video, embedded, so watching it on the page is a YouTube view
    the whole narration as text - this is what Google actually indexes
    the sources, where the script is one of the hand-written sourced episodes
    a subscribe link, and the other videos on the same channel

The index pages list every video by channel, and sitemap.xml tells Google where
they all are. Nothing here is generated filler: a video with no script text in
the bank gets a short page with its own description, or no page at all.
"""
import io
import json
import os
import re
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs")
BASE = "https://islamfatema.github.io/faru-autopilot"

CHANNELS = {
    "history": {"name": "History That Explains the World",
                "handle": "HistoryExplainsTheWorld",
                "blurb": "The past doing things we assume are modern - with the "
                         "source for every claim.",
                "bank": "autopilot_history/scripts_history.json"},
    "us": {"name": "Rise With Fate", "handle": "risewithfate",
           "blurb": "One published study at a time, about you.",
           "bank": "autopilot_us/scripts_us.json"},
    "fun": {"name": "FaRu Fact", "handle": "FactsFaru",
            "blurb": "Facts that sound fake, checked against a named source.",
            "bank": "autopilot_fun/scripts_fun.json"},
}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def slug(title):
    t = re.sub(r"#\w+", " ", title or "").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:70] or "video"


def norm(t):
    return " ".join(re.sub(r"#\w+", " ", (t or "")).lower().split())


def clean_title(t):
    t = re.sub(r"#\w+", "", t or "")
    return " ".join("".join(ch for ch in t if ord(ch) < 0x2190).split())


PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s | %(channel)s</title>
<meta name="description" content="%(meta)s">
<link rel="canonical" href="%(url)s">
<meta property="og:type" content="video.other">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(meta)s">
<meta property="og:image" content="https://i.ytimg.com/vi/%(vid)s/maxresdefault.jpg">
<meta property="og:url" content="%(url)s">
<script type="application/ld+json">%(ld)s</script>
<style>
:root{--ink:#14181C;--muted:#5C6670;--rule:#D3D8DD;--paper:#F7F8F9;--panel:#fff;--accent:#0B7285}
@media(prefers-color-scheme:dark){:root{--ink:#E7EDF0;--muted:#8B959E;--rule:#28333A;--paper:#0D1114;--panel:#151B1F;--accent:#3FB4C6}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:780px;margin:0 auto;padding:0 20px 60px}
header{border-bottom:1px solid var(--rule);background:var(--panel);margin-bottom:26px}
header .wrap{padding:14px 20px;display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
header a{color:var(--accent);text-decoration:none;font-weight:600}
h1{font-size:clamp(23px,4.2vw,33px);line-height:1.2;margin:18px 0 6px}
.meta{color:var(--muted);font-size:14px;margin:0 0 18px}
.player{position:relative;padding-top:177.8%%;max-width:420px;margin:0 auto 24px;background:#000;border-radius:10px;overflow:hidden}
.player.wide{padding-top:56.25%%;max-width:100%%}
.player iframe{position:absolute;inset:0;width:100%%;height:100%%;border:0}
h2{font-size:17px;margin:28px 0 8px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
p{margin:0 0 14px}
ul{padding-left:20px}
li{margin-bottom:6px}
a{color:var(--accent)}
.sub{display:inline-block;margin:10px 0 0;padding:11px 18px;background:var(--accent);color:#fff;
     text-decoration:none;border-radius:6px;font-weight:600}
.more{display:grid;gap:8px;margin-top:10px}
.more a{text-decoration:none}
footer{border-top:1px solid var(--rule);margin-top:40px;padding-top:16px;color:var(--muted);font-size:14px}
</style></head><body>
<header><div class="wrap"><a href="%(home)s">%(channel)s</a>
<span class="meta">%(blurb)s</span></div></header>
<div class="wrap">
<h1>%(title)s</h1>
<p class="meta">Published %(published)s &middot; <a href="https://www.youtube.com/watch?v=%(vid)s">Watch on YouTube</a></p>
<div class="player%(wide)s"><iframe src="https://www.youtube-nocookie.com/embed/%(vid)s" title="%(title)s"
 allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe></div>
%(body)s
<a class="sub" href="https://www.youtube.com/@%(handle)s?sub_confirmation=1">Subscribe to %(channel)s</a>
<h2>More from this channel</h2>
<div class="more">%(more)s</div>
<footer>%(channel)s &middot; %(blurb)s</footer>
</div></body></html>
"""

INDEX = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(meta)s">
<link rel="canonical" href="%(url)s">
<style>
:root{--ink:#14181C;--muted:#5C6670;--rule:#D3D8DD;--paper:#F7F8F9;--panel:#fff;--accent:#0B7285}
@media(prefers-color-scheme:dark){:root{--ink:#E7EDF0;--muted:#8B959E;--rule:#28333A;--paper:#0D1114;--panel:#151B1F;--accent:#3FB4C6}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:0 20px 60px}
h1{font-size:clamp(24px,4.6vw,38px);margin:26px 0 6px}
p.lede{color:var(--muted);margin:0 0 22px}
ul{list-style:none;padding:0;display:grid;gap:10px}
li{border-bottom:1px solid var(--rule);padding-bottom:10px}
a{color:var(--accent);text-decoration:none;font-weight:600}
span.d{display:block;color:var(--muted);font-size:14px;font-weight:400}
.sub{display:inline-block;margin:6px 0 20px;padding:11px 18px;background:var(--accent);color:#fff;border-radius:6px}
</style></head><body><div class="wrap">
<h1>%(h1)s</h1><p class="lede">%(meta)s</p>
%(subscribe)s
<ul>%(items)s</ul>
</div></body></html>
"""


def transcript(bank_by_title, title):
    """The spoken text of this video, if the script is still in the bank."""
    d = bank_by_title.get(norm(title))
    if not d:
        return None, None, None
    lines = [l for l in (d.get("phrases") or []) if l]
    text = " ".join(l.replace("\n", " ") for l in lines)
    sources = []
    desc = d.get("desc") or ""
    if "Sources:" in desc:
        for line in desc.split("Sources:", 1)[1].strip().splitlines():
            line = line.strip("- ").strip()
            if line:
                sources.append(line)
    return text, sources, d.get("series")


def build_channel(key, cfg):
    data = json.load(io.open(os.path.join(ROOT, "analytics", "videos_%s.json" % key),
                             encoding="utf-8"))
    bank = json.load(io.open(os.path.join(ROOT, cfg["bank"]), encoding="utf-8"))
    by_title = dict((norm(d["title"]), d) for d in bank)

    # Videos tools/hide_duplicates.py has already made private. They are still
    # in the analytics file - it records views, not privacy - and a page for a
    # video nobody can watch is a dead embed.
    try:
        hidden = set(json.load(io.open(
            os.path.join(ROOT, "analytics", "hidden_%s.json" % key), encoding="utf-8")))
    except Exception:
        hidden = set()

    def views_of(rec):
        s = rec.get("snapshots") or []
        return (s[-1].get("views") or 0) if s else 0

    vids = []
    for vid, rec in data["videos"].items():
        t = clean_title(rec.get("title"))
        if not t or vid in hidden:
            continue
        vids.append((rec.get("published") or "", vid, t, rec))
    vids.sort(reverse=True)

    # Whatever the hide pass has not caught yet still collides here: two videos
    # with one title produce one slug, so the second overwrote the first on disk
    # while both sat in the index and both went into sitemap.xml. Keep the copy
    # people actually watched.
    best = {}
    for row in vids:
        s = slug(row[2])
        if s not in best or views_of(row[3]) > views_of(best[s][3]):
            best[s] = row
    dropped = len(vids) - len(best)
    if dropped:
        print("  %s: %d duplicate page%s skipped (%d hidden on the channel)"
              % (key, dropped, "" if dropped == 1 else "s", len(hidden)))
    vids = sorted(best.values(), reverse=True)

    pages = []
    for published, vid, title, rec in vids:
        text, sources, series = transcript(by_title, rec.get("title"))
        body = []
        if text:
            body.append("<h2>What the video says</h2><p>%s</p>" % esc(text))
        if sources:
            body.append("<h2>Sources</h2><ul>%s</ul>"
                        % "".join("<li>%s</li>" % esc(s) for s in sources))
        if not text:
            # No script in the bank any more. A page with nothing on it but a
            # title and an embed is the kind of thin page Google is right to
            # ignore, and 61 of them would drag the other 649 down. Skip it.
            continue
        pages.append((published, vid, title, "\n".join(body), rec))

    os.makedirs(os.path.join(OUT, key), exist_ok=True)
    urls = []
    for i, (published, vid, title, body, rec) in enumerate(pages):
        s = slug(title)
        more = "".join(
            '<a href="%s/%s/">%s</a>' % (BASE + "/" + key, slug(t2), esc(t2))
            for _, _, t2, _, _ in pages[max(0, i - 3):i] + pages[i + 1:i + 4])
        url = "%s/%s/%s/" % (BASE, key, s)
        meta = (text_meta(body) or cfg["blurb"])[:300]
        ld = json.dumps({
            "@context": "https://schema.org", "@type": "VideoObject",
            "name": title, "description": meta,
            "thumbnailUrl": ["https://i.ytimg.com/vi/%s/maxresdefault.jpg" % vid],
            "uploadDate": published[:19] if published else None,
            "embedUrl": "https://www.youtube.com/embed/%s" % vid,
            "url": url,
        }, ensure_ascii=False)
        html = PAGE % {
            "title": esc(title), "channel": esc(cfg["name"]), "blurb": esc(cfg["blurb"]),
            "meta": esc(meta), "vid": vid, "url": url, "ld": ld, "body": body,
            "handle": cfg["handle"], "more": more, "home": BASE + "/" + key + "/",
            "published": esc((published or "")[:10]),
            "wide": "" if (rec.get("kind") == "short") else " wide",
        }
        d = os.path.join(OUT, key, s)
        os.makedirs(d, exist_ok=True)
        io.open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n").write(html)
        urls.append((url, (published or "")[:10]))

    items = "".join(
        '<li><a href="%s/%s/%s/">%s</a><span class="d">%s</span></li>'
        % (BASE, key, slug(t), esc(t), esc((p or "")[:10]))
        for p, v, t, _, _ in pages)
    io.open(os.path.join(OUT, key, "index.html"), "w", encoding="utf-8", newline="\n").write(
        INDEX % {"title": esc(cfg["name"]), "h1": esc(cfg["name"]),
                 "meta": esc(cfg["blurb"]), "url": "%s/%s/" % (BASE, key),
                 "subscribe": '<a class="sub" href="https://www.youtube.com/@%s?sub_confirmation=1">Subscribe</a>'
                              % cfg["handle"],
                 "items": items})
    urls.append(("%s/%s/" % (BASE, key), date.today().isoformat()))
    return urls, len(pages)


def text_meta(body_html):
    txt = re.sub(r"<[^>]+>", " ", body_html)
    txt = " ".join(txt.split())
    return txt[:300]


def main():
    os.makedirs(OUT, exist_ok=True)
    all_urls, counts = [], {}
    for key, cfg in CHANNELS.items():
        urls, n = build_channel(key, cfg)
        all_urls += urls
        counts[key] = n
        print("%-8s %d pages" % (key, n), flush=True)

    # the home page
    items = "".join(
        '<li><a href="%s/%s/">%s</a><span class="d">%s - %d videos</span></li>'
        % (BASE, k, esc(c["name"]), esc(c["blurb"]), counts[k])
        for k, c in CHANNELS.items())
    io.open(os.path.join(OUT, "index.html"), "w", encoding="utf-8", newline="\n").write(
        INDEX % {"title": "Three channels, every video with its transcript and sources",
                 "h1": "Every video, with what it says and where it comes from",
                 "meta": "Transcripts and sources for every video on three YouTube channels.",
                 "url": BASE + "/", "subscribe": "", "items": items})
    all_urls.append((BASE + "/", date.today().isoformat()))

    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, lastmod in all_urls:
        sm.append("<url><loc>%s</loc>%s</url>"
                  % (esc(url), "<lastmod>%s</lastmod>" % lastmod if lastmod else ""))
    sm.append("</urlset>")
    io.open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8", newline="\n").write("\n".join(sm))
    io.open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8", newline="\n").write(
        "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % BASE)
    io.open(os.path.join(OUT, ".nojekyll"), "w", encoding="utf-8", newline="\n").write("")
    print("wrote docs/ with %d pages and a sitemap" % len(all_urls), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
