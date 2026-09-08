# -*- coding: utf-8 -*-
"""Ask the question on the videos that already have an audience.

New videos end on a question now. The 500 already published do not, and that is
where all the reach is:

    Sharks Are Older Than Trees                        1,077 views   0 comments
    Oxford University Is Older Than the Aztec Empire      997 views   0 comments
    Ancient Roman Concrete Can Heal Itself                950 views   0 comments
    Anne Frank and MLK Were Born the Same Year            932 views   0 comments

Nearly four thousand views on four videos and not one comment on any of them.
Nobody was asked anything, so nobody said anything - and comments are what make
YouTube widen a video's audience.

The video cannot be changed, but the channel can post the question underneath
it, which is what creators do as a matter of routine. This is the channel
speaking as itself, on its own video, asking something real about that video's
subject. It is not fake engagement: no other accounts, no bought anything, no
pretending to be a viewer.

Rules it holds to:
  - only videos with real reach and genuinely zero comments
  - one comment per video, ever - it checks whether the channel already spoke
  - the question names the video's own subject, so it reads as a question and
    not as a template
  - small daily limit, because the quota is shared with the uploads

    python tools/seed_comments.py history --check
    python tools/seed_comments.py history --apply --limit 10

Env: REFRESH_TOKEN with the editing scope (/api/yt-auth?manage=1).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grow  # noqa: E402  - model discovery, request budget, backoff

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"

# The subject of the video, pulled out of its own title, goes into the question.
# A question that could sit under any video reads as a template and earns
# nothing; one that names the thing reads as a question.
# No template pool. Five rotating questions across thirty-nine videos reads as
# a bot however they are shuffled - and mass-produced comment text is exactly
# the pattern YouTube's inauthentic-content policy is aimed at. The questions
# are written per video instead, from that video's own title, and if the
# generator is unavailable nothing is posted at all.
VOICE = {
    "history": ("a history channel for a US audience. The question should be "
                "about what the viewer was taught, or what else they think the "
                "textbook left out."),
    "fun": ("a channel about surprising true things, mostly about the viewer's "
            "own body. The question should ask whether they already knew, had "
            "to check, or who they would send it to."),
    "us": ("a motivation channel that talks to one person directly. The "
           "question should be about the viewer's own situation, and should be "
           "answerable in a few words."),
}

PROMPT = """Write one comment for each video below, to be posted by the channel
itself underneath its own video.

The channel is {voice}

Rules:
- One short question per video, under 110 characters.
- It must be about THAT video's specific subject. A question that could sit
  under any video is worthless and reads as a bot.
- Ask something a viewer can answer in one line. Not "what do you think".
- No emoji, no hashtags, no "comment below", no asking for likes or subscribes.
- Plain sentence, written the way a person types.

Videos:
{titles}

Return ONLY a JSON array of {n} strings, in the same order. No commentary."""


def write_questions(channel, titles, gkey):
    """One question per title, written for that specific video.

    Returns None if the generator cannot be reached. Falling back to a template
    on thirty-nine videos is the exact thing this function exists to avoid, so
    nothing is the better outcome.
    """
    listing = "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(titles))
    prompt = PROMPT.format(voice=VOICE[channel], titles=listing, n=len(titles))
    try:
        out = grow.parse_array(grow.gemini(prompt, gkey))
    except Exception as e:
        print("could not write the questions: %s" % str(e)[:160], flush=True)
        return None
    good = []
    for q in out:
        q = q.strip() if isinstance(q, str) else ""
        # Something that is not a question, or is long enough to be a speech,
        # is not worth posting under anything.
        good.append(q if q and len(q) <= 140 and "?" in q else None)
    good += [None] * max(0, len(titles) - len(good))
    return good[:len(titles)]


def _open(req, timeout=120):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))


def access_token():
    d = json.dumps({"refresh_token": os.environ["REFRESH_TOKEN"].strip()}).encode()
    r = urllib.request.Request(TOKEN_URL, data=d, headers={"Content-Type": "application/json"})
    return json.loads(_open(r).read())["access_token"]


def get(url, tok):
    return json.loads(_open(urllib.request.Request(
        url, headers={"Authorization": "Bearer " + tok})).read())


def post(url, tok, body):
    return json.loads(_open(urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + tok,
                 "Content-Type": "application/json"})).read())


def check_channel(actual, expected):
    if not expected:
        return
    if actual.strip().lower() != expected.strip().lower():
        raise SystemExit(
            "REFUSING TO WRITE."
            "\n  this run is for : %s"
            "\n  the token is    : %s"
            "\nA swapped secret would comment on the wrong channel." % (expected, actual))


def uploads(tok):
    ch = get(API + "/channels?part=snippet,contentDetails&mine=true", tok)
    if not ch.get("items"):
        raise SystemExit("no channel for this token")
    c = ch["items"][0]
    up = c["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        u = API + "/playlistItems?part=contentDetails&maxResults=50&playlistId=" + up
        if page:
            u += "&pageToken=" + page
        for attempt in (1, 2, 3):
            try:
                j = get(u, tok)
                break
            except Exception as e:
                if attempt == 3:
                    print("  page failed (%s) - continuing with %d"
                          % (str(e)[:70], len(ids)), flush=True)
                    j = None
                    break
                time.sleep(3)
        if j is None:
            break
        ids += [it["contentDetails"]["videoId"] for it in j.get("items", [])]
        page = j.get("nextPageToken")
        if not page:
            break
    out = []
    for i in range(0, len(ids), 50):
        j = get(API + "/videos?part=snippet,statistics,status&id=" + ",".join(ids[i:i + 50]), tok)
        for v in j.get("items", []):
            if v["status"]["privacyStatus"] != "public":
                continue
            st = v.get("statistics", {})
            v["_views"] = int(st.get("viewCount", 0) or 0)
            v["_comments"] = int(st.get("commentCount", 0) or 0)
            out.append(v)
    out.sort(key=lambda v: -v["_views"])
    return c["snippet"]["title"], c["id"], out


def already_spoke(vid, channel_id, tok):
    """Never comment twice. Comments are public and a duplicate reads as a bot."""
    try:
        j = get(API + "/commentThreads?part=snippet&maxResults=50&videoId=" + vid, tok)
    except Exception:
        # Comments disabled, or unreadable - either way, do not post.
        return True
    for t in j.get("items", []):
        top = t["snippet"]["topLevelComment"]["snippet"]
        cid = (top.get("authorChannelId") or {}).get("value")
        if cid == channel_id:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", choices=sorted(VOICE))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--min-views", type=int, default=200,
                    help="only where there is an audience to answer")
    ap.add_argument("--expect", default="")
    a = ap.parse_args()

    gkey = (os.environ.get("OWNER_GEMINI_KEY") or "").strip()
    if not gkey:
        print("no OWNER_GEMINI_KEY - every question is written for its own "
              "video, so there is nothing to post without it")
        return 0

    tok = access_token()
    name, channel_id, vids = uploads(tok)
    print("channel: %s" % name, flush=True)
    check_channel(name, a.expect)

    todo = [v for v in vids if v["_views"] >= a.min_views and v["_comments"] == 0]
    print("public videos: %d | over %d views with zero comments: %d"
          % (len(vids), a.min_views, len(todo)), flush=True)
    todo = todo[:(2 if a.check else a.limit)]
    if not todo:
        return 0

    questions = write_questions(a.channel, [v["snippet"]["title"] for v in todo], gkey)
    if questions is None:
        return 1

    done = 0
    for v, text in zip(todo, questions):
        title = v["snippet"]["title"]
        if not text:
            print("\n%s  skipped - no usable question came back" % v["id"], flush=True)
            continue
        print("\n%s  %5d views  %s" % (v["id"], v["_views"], title[:46]), flush=True)
        print("   ask: %s" % text, flush=True)
        if not a.apply:
            continue
        if already_spoke(v["id"], channel_id, tok):
            print("   skipped - already commented, or comments are off", flush=True)
            continue
        try:
            post(API + "/commentThreads?part=snippet", tok,
                 {"snippet": {"videoId": v["id"],
                              "topLevelComment": {"snippet": {"textOriginal": text}}}})
            print("   ASKED", flush=True)
            done += 1
        except Exception as e:
            msg = str(e)
            if "quotaExceeded" in msg or "exceeded your" in msg:
                print("   STOPPED - daily quota spent, shared with the uploads.",
                      flush=True)
                break
            print("   failed: %s" % msg[:160], flush=True)
        time.sleep(2)

    print("\nasked on %d videos%s" % (done, "" if a.apply else "  (check only)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
