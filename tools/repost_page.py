# -*- coding: utf-8 -*-
"""One page with today's finished videos, ready to post anywhere by hand.

Every Short the machine publishes is already attached to a GitHub release with
its caption beside it - the mp4 and a .txt. They are there so Instagram and
Facebook can fetch them by URL, and that path is waiting on a Meta token. The
files themselves are not waiting on anything: they are finished vertical
videos with captions written, and they can go on TikTok, Reels, Snapchat,
Pinterest or anywhere else the moment somebody downloads one.

Nobody does, because finding them means walking back through the releases list
and matching an mp4 to the right caption. So this builds the page that makes
it two minutes instead of twenty: today's videos, newest first, each with the
file, the caption ready to copy, and the YouTube link it belongs to.

    python tools/repost_page.py             # writes docs/post/index.html
    python tools/repost_page.py --days 3

It reads the releases through `gh`, so it needs nothing that the posting
workflows do not already have.
"""
import argparse
import html
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "post")
REPO = "islamfatema/faru-autopilot"
CHANNEL = {"fun": "FaRu Fact", "us": "Rise With Fate",
           "history": "History Explains"}

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Post these</title>
<style>
 :root{color-scheme:light dark;--bg:#faf9f7;--fg:#17171a;--mut:#6b6b73;--line:#e3e1dd;--card:#fff;--acc:#b4532a}
 @media (prefers-color-scheme:dark){:root{--bg:#131316;--fg:#ececf0;--mut:#9a9aa3;--line:#2b2b31;--card:#1b1b1f;--acc:#e58a5f}}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:720px;margin:0 auto;padding:28px 16px 64px}
 h1{font-size:1.5rem;margin:0 0 4px;letter-spacing:-.01em}
 .sub{color:var(--mut);font-size:.92rem;margin:0 0 26px}
 .v{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:0 0 14px}
 .top{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
 .ch{font-size:.72rem;letter-spacing:.07em;text-transform:uppercase;color:var(--acc);font-weight:600}
 .when{font-size:.78rem;color:var(--mut);margin-left:auto}
 .t{font-weight:600;margin:6px 0 10px;overflow-wrap:anywhere}
 .cap{white-space:pre-wrap;background:transparent;border:1px solid var(--line);border-radius:8px;
      padding:10px;font-size:.88rem;color:var(--fg);width:100%%;min-height:76px;resize:vertical;font-family:inherit}
 .row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
 a.btn,button.btn{display:inline-block;border:1px solid var(--line);background:transparent;color:var(--fg);
   text-decoration:none;padding:7px 12px;border-radius:8px;font-size:.85rem;cursor:pointer}
 a.btn.go{border-color:var(--acc);color:var(--acc)}
 .none{color:var(--mut)}
 footer{color:var(--mut);font-size:.82rem;margin-top:28px;border-top:1px solid var(--line);padding-top:14px}
</style></head><body><div class="wrap">
<h1>Post these</h1>
<p class="sub">%(n)d finished videos from the last %(days)d day(s). Download, copy the caption, post. Nothing here is uploaded anywhere automatically.</p>
%(items)s
<footer>Built %(built)s. Instagram and Facebook post themselves once a Meta token is set; this page is for everywhere else.</footer>
</div>
<script>
document.addEventListener('click', function (e) {
  var b = e.target.closest('button.copy'); if (!b) return;
  var t = document.getElementById(b.dataset.for);
  t.select(); t.setSelectionRange(0, 99999);
  try { document.execCommand('copy'); b.textContent = 'copied'; setTimeout(function(){ b.textContent = 'copy caption'; }, 1400); } catch (err) {}
});
</script>
</body></html>
"""

ITEM = """<div class="v">
 <div class="top"><span class="ch">%(ch)s</span><span class="when">%(when)s</span></div>
 <div class="t">%(title)s</div>
 <textarea class="cap" id="c%(i)d" readonly>%(caption)s</textarea>
 <div class="row">
   <a class="btn go" href="%(mp4)s" download>download video</a>
   <button class="btn copy" data-for="c%(i)d">copy caption</button>
 </div>
</div>
"""


def gh(args):
    p = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    return p.stdout


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    a = ap.parse_args()

    since = datetime.now(timezone.utc) - timedelta(days=a.days)
    rels = json.loads(gh(["release", "list", "--limit", "60", "--repo", REPO,
                          "--json", "tagName,createdAt,name"]))
    items, n = [], 0
    for r in rels:
        try:
            when = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
        except Exception:
            continue
        if when < since:
            continue
        tag = r["tagName"]
        key = tag.split("-")[1] if "-" in tag else "?"
        assets = json.loads(gh(["release", "view", tag, "--repo", REPO,
                                "--json", "assets"]))["assets"]
        mp4s = sorted(x["name"] for x in assets if x["name"].endswith(".mp4"))
        for name in mp4s:
            base = name[:-4]
            cap = ""
            txt = base + ".txt"
            if any(x["name"] == txt for x in assets):
                try:
                    d = os.path.join(OUT, "_tmp")
                    os.makedirs(d, exist_ok=True)
                    gh(["release", "download", tag, "--repo", REPO,
                        "--pattern", txt, "--dir", d, "--clobber"])
                    cap = io.open(os.path.join(d, txt), encoding="utf-8").read().strip()
                    os.remove(os.path.join(d, txt))
                except Exception:
                    cap = ""
            url = "https://github.com/%s/releases/download/%s/%s" % (REPO, tag, name)
            items.append(ITEM % {
                "ch": html.escape(CHANNEL.get(key, key)),
                "when": when.strftime("%d %b %H:%M UTC"),
                # Strip the pack's running number: the file is
                # "01-why-corkboards-are-made-of-cork.mp4" and the 01 is
                # the slot in that run, not part of the title.
                "title": html.escape(
                    re.sub(r"^\d+[- ]", "", base).replace("-", " ").strip().title()),
                "caption": html.escape(cap or base.replace("-", " ")),
                "mp4": html.escape(url), "i": n})
            n += 1

    os.makedirs(OUT, exist_ok=True)
    body = "".join(items) or '<p class="none">Nothing published in this window.</p>'
    io.open(os.path.join(OUT, "index.html"), "w", encoding="utf-8",
            newline="\n").write(PAGE % {
                "n": n, "days": a.days, "items": body,
                "built": datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")})
    tmp = os.path.join(OUT, "_tmp")
    if os.path.isdir(tmp):
        try:
            os.rmdir(tmp)
        except OSError:
            pass
    print("docs/post/index.html - %d videos" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
