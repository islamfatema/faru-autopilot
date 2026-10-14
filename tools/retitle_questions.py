# -*- coding: utf-8 -*-
"""Turn FaRu Fact's published statement titles into the question people type.

Measured on the 160 Shorts the channel published since 1 September:

    question-shaped title   n= 15   median 22 views   9.9 search views each
    statement title         n=145   median  4 views   3.5

The rotation now plays question-shaped scripts first, so everything published
from today carries one. This is for the ones already up. They are indexed and
they are dead - a median of four views - and a title is the one thing about a
published video that can still be changed. At four views there is nothing to
lose and a search result to gain.

Each new title is written from that video's own script, so it claims nothing
the video does not say. Four guards stand between the model and the channel:

  * only videos under --max-views are touched, default 60 - a video that found
    an audience keeps the title that found it
  * the new title must actually be a question
  * it must share at least two content words with the old one, so a model that
    drifts onto another subject is rejected
  * every old title is written to analytics/retitled_fun.json first, so any of
    this can be put back

    python tools/retitle_questions.py --key fun                  # propose only
    python tools/retitle_questions.py --key fun --apply

Env: OWNER_GEMINI_KEY to write the titles, YT_REFRESH_TOKEN_MANAGE to set them.
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import grow  # noqa: E402  - the model call, the budget and the JSON repair

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"
PER_REQUEST = 5
MAX_TITLE = 90

QUESTION = re.compile(
    r"^(why|how|what|do|does|did|can|is|are|when|where|which|should|will)\b", re.I)
STOP = set((
    "the a an is are was was were do does did of in on to for your you my it "
    "that this what why how much and or as at be been can could not no than "
    "with from into about actually really isn't doesn't").split())

PROMPT = """Rewrite each of these {n} YouTube Shorts titles as the question a
person types into YouTube search.

Rules, all of them mandatory:
- Begin with Why, How, What, Do, Does, Can or Is.
- It must be answerable by the script given, and the script's answer must be
  the honest one. Claim nothing the script does not say.
- Keep it under 70 characters, before the hashtags.
- Plain words people actually search with. Not clever, not clickbait.
- Keep the subject nouns from the old title so it is recognisably the same
  video.
- No hashtags, no emoji, no quotation marks.

Example: "You Already Have A Six-Pack, It's One Muscle!"
      -> "Do You Already Have a Six Pack?"

Videos:
{items}

Return ONLY a JSON array of {n} objects, each {{"id": "<the id given>",
"title": "<the question>"}}. No commentary."""


def words(t):
    t = re.sub(r"#\w+", " ", t or "").lower()
    return set(w for w in re.sub(r"[^a-z0-9 ]", " ", t).split()
               if w not in STOP and len(w) > 2)


def norm(t):
    t = re.sub(r"#\w+", "", t or "").lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


def _open(req, timeout=120):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise RuntimeError("HTTP %s -> %s" % (e.code, body))


def access_token():
    refresh = (os.environ.get("YT_REFRESH_TOKEN_MANAGE") or "").strip()
    if not refresh:
        raise SystemExit("YT_REFRESH_TOKEN_MANAGE is not set - this needs a "
                         "token carrying youtube.force-ssl")
    req = urllib.request.Request(
        TOKEN_URL, data=json.dumps({"refresh_token": refresh}).encode(),
        headers={"Content-Type": "application/json"})
    with _open(req) as r:
        j = json.loads(r.read())
    if not j.get("access_token"):
        raise RuntimeError("no access_token in response")
    return j["access_token"]


def current_snippet(vid, tok):
    """categoryId and description have to be sent back unchanged with a title."""
    req = urllib.request.Request(
        "%s/videos?part=snippet&id=%s" % (API, vid),
        headers={"Authorization": "Bearer " + tok})
    with _open(req) as r:
        items = json.loads(r.read()).get("items") or []
    if not items:
        raise RuntimeError("video not found (not this channel's?)")
    return items[0]["snippet"]


def set_title(vid, title, tok):
    sn = current_snippet(vid, tok)
    body = {"id": vid, "snippet": {
        "title": title,
        "categoryId": sn.get("categoryId", "27"),
        "description": sn.get("description", ""),
        "tags": sn.get("tags", []),
        "defaultLanguage": sn.get("defaultLanguage", "en")}}
    req = urllib.request.Request(
        "%s/videos?part=snippet" % API, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + tok,
                 "Content-Type": "application/json"}, method="PUT")
    with _open(req) as r:
        return json.loads(r.read())["snippet"]["title"]


def candidates(key, max_views):
    """Published Shorts whose title is a statement and that nobody watched."""
    vids = json.load(io.open(os.path.join(ROOT, "analytics", "videos_%s.json" % key),
                             encoding="utf-8"))["videos"]
    bank = {norm(x["title"]): x for x in
            json.load(io.open(os.path.join(ROOT, "autopilot_%s" % key,
                                           "scripts_%s.json" % key), encoding="utf-8"))}
    out = []
    for vid, v in vids.items():
        if v.get("kind") != "short":
            continue
        plain = re.sub(r"#\w+", "", v["title"]).strip()
        if plain.endswith("?") or QUESTION.match(plain):
            continue
        snaps = v.get("snapshots") or []
        views = (snaps[-1].get("views") or 0) if snaps else 0
        if views > max_views:
            continue
        b = bank.get(norm(v["title"]))
        script = " ".join(b.get("phrases") or []) if b else (v.get("description") or "")
        script = re.sub(r"\s+", " ", script).strip()
        if len(script) < 40:
            continue
        out.append({"id": vid, "old": plain, "views": views,
                    "tags": "".join(re.findall(r"#\w+", v["title"])),
                    "script": script[:420]})
    out.sort(key=lambda r: -r["views"])
    return out


def accept(old, new):
    """Why this proposal is not usable, or None."""
    if not new or len(new) > MAX_TITLE:
        return "length"
    if not (new.strip().endswith("?") or QUESTION.match(new.strip())):
        return "not a question"
    if '"' in new or "#" in new:
        return "punctuation"
    if len(words(old) & words(new)) < 2:
        return "drifted off the subject"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="fun", choices=["fun", "us", "history"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-views", type=int, default=60)
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()

    todo = candidates(a.key, a.max_views)[:a.limit]
    print("%s: %d published Shorts with a statement title and under %d views"
          % (a.key, len(todo), a.max_views), flush=True)
    if not todo:
        return 0

    gkey = (os.environ.get("OWNER_GEMINI_KEY") or "").strip()
    if not gkey:
        raise SystemExit("OWNER_GEMINI_KEY is not set")

    proposals = []
    for start in range(0, len(todo), PER_REQUEST):
        batch = todo[start:start + PER_REQUEST]
        items = json.dumps([{"id": r["id"], "old_title": r["old"],
                             "script": r["script"]} for r in batch],
                           ensure_ascii=False, indent=1)
        try:
            out = grow.parse_array(grow.gemini(
                PROMPT.format(n=len(batch), items=items), gkey))
        except grow.BudgetSpent as e:
            print("  stopping: %s" % e, flush=True)
            break
        except Exception as e:
            print("  batch failed: %s" % str(e)[:160], flush=True)
            time.sleep(4)
            continue
        by_id = {r["id"]: r for r in batch}
        for got in out:
            r = by_id.get((got or {}).get("id"))
            if not r:
                continue
            new = re.sub(r"\s+", " ", str(got.get("title") or "")).strip()
            bad = accept(r["old"], new)
            if bad:
                print("  rejected (%s): %s -> %s" % (bad, r["old"][:34], new[:40]),
                      flush=True)
                continue
            proposals.append(dict(r, new=new))

    print("\n%d usable of %d asked for\n" % (len(proposals), len(todo)))
    for p in proposals:
        print("  %4dv  %s\n         -> %s" % (p["views"], p["old"][:60], p["new"]))
    if not a.apply or not proposals:
        print("\n(proposals only - pass --apply to set them)")
        return 0

    # Write the old titles down before changing anything.
    led = os.path.join(ROOT, "analytics", "retitled_%s.json" % a.key)
    try:
        prev = json.load(io.open(led, encoding="utf-8"))
    except Exception:
        prev = []
    prev += [{"id": p["id"], "was": p["old"], "now": p["new"],
              "views_then": p["views"]} for p in proposals]
    io.open(led, "w", encoding="utf-8", newline="\n").write(
        json.dumps(prev, ensure_ascii=False, indent=1))

    tok = access_token()
    done = failed = 0
    for p in proposals:
        title = (p["new"] + " " + p["tags"]).strip()[:MAX_TITLE]
        try:
            got = set_title(p["id"], title, tok)
            print("  %s -> %s" % (p["id"], got[:62]), flush=True)
            done += 1
        except Exception as e:
            print("  %s FAILED: %s" % (p["id"], str(e)[:140]), flush=True)
            failed += 1
        time.sleep(0.5)
    print("\nretitled %d, failed %d. Old titles in analytics/retitled_%s.json"
          % (done, failed, a.key))
    return 1 if failed and not done else 0


if __name__ == "__main__":
    sys.exit(main())
