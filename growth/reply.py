# -*- coding: utf-8 -*-
"""Answer the people who comment.

    python growth/reply.py --key history --max 20
    python growth/reply.py --key us --check          # show, post nothing

A comment is the rarest thing these channels get - Rise takes 43 in 28 days,
History 30, FaRu 7 - and every one of them has been left unanswered. A reply
from the channel is the cheapest way there is to turn a viewer into someone who
comes back: they get a notification, they return to the video, and the thread
under it grows, which is itself a signal YouTube reads.

What this will and will not do:

  * replies once per comment, only to comments from other people, only on
    comments that have no reply from the channel yet, only within 14 days;
  * the reply is written for that comment on that video - it answers what was
    said, and where it fits, asks one question back. No "thanks for watching",
    no "subscribe", no links, ever;
  * spam, links and "check my channel" are skipped, and so is anything the
    model cannot answer specifically - a generic reply is worse than none;
  * never more than --max a run, so the channel never looks like a bot.

Env: REFRESH_TOKEN (manage token with youtube.force-ssl), OWNER_GEMINI_KEY,
EXPECT_CHANNEL optional.
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import store  # noqa: E402
import yt     # noqa: E402

VOICE = {
    "us": ("Rise With Fate", "warm, direct, like a friend who has been through it - "
           "second person, no preaching, no emojis beyond one at most"),
    "fun": ("FaRu Fact", "curious and playful, a fact-lover talking to another one - "
            "can add one extra true detail about the subject"),
    "history": ("History That Explains the World", "a history nerd talking to another - "
                "can add one extra true detail, never lecturing"),
}
SPAM = re.compile(r"https?://|www\.|\.com\b|check (out )?my|sub4sub|subscribe to me|"
                  r"my channel|follow me|telegram|whatsapp|crypto|giveaway", re.I)


def gemini(prompt):
    """One short completion via the same client and budget the generators use."""
    import grow
    key = (os.environ.get("OWNER_GEMINI_KEY") or "").strip()
    if not key:
        return None
    try:
        return grow.gemini(prompt, key)
    except Exception as e:
        print("   model unavailable: %s" % str(e)[:80], flush=True)
        return None


def write_reply(key, video_title, comment):
    name, voice = VOICE[key]
    prompt = (
        "You run the YouTube channel %s. Someone left this comment under your video "
        "titled \"%s\":\n\n\"%s\"\n\n"
        "Write the channel's reply. Rules:\n"
        "- 1 or 2 sentences, under 40 words.\n"
        "- Answer what THEY said, specifically. If they asked something, answer it truthfully; "
        "if you are not sure of a fact, do not state it.\n"
        "- Where it fits naturally, end with ONE short question back to them about their own "
        "experience or opinion.\n"
        "- Voice: %s.\n"
        "- Never say thanks for watching, never ask them to subscribe or like, no links, "
        "no hashtags.\n"
        "- If the comment is hostile, spam, or impossible to answer specifically, reply with "
        "exactly SKIP.\n"
        "Return only the reply text." % (name, re.sub(r"#\w+", "", video_title).strip(),
                                         comment[:500], voice))
    out = gemini(prompt)
    if not out:
        return None
    out = out.strip().strip('"').strip()
    if not out or out.upper().startswith("SKIP") or len(out) > 320:
        return None
    if SPAM.search(out) or "subscribe" in out.lower() or "thanks for watching" in out.lower():
        return None
    return out


def threads(tok, channel_id, pages=3):
    out, page = [], None
    for _ in range(pages):
        u = (yt.DATA_API + "/commentThreads?part=snippet,replies&maxResults=50&order=time"
             "&allThreadsRelatedToChannelId=" + channel_id)
        if page:
            u += "&pageToken=" + page
        j = yt.get(u, tok)
        out += j.get("items", [])
        page = j.get("nextPageToken")
        if not page:
            break
    return out


def post_reply(tok, parent_id, text):
    body = json.dumps({"snippet": {"parentId": parent_id, "textOriginal": text}}).encode()
    req = urllib.request.Request(yt.DATA_API + "/comments?part=snippet", data=body,
                                 headers={"Authorization": "Bearer " + tok,
                                          "Content-Type": "application/json"})
    with yt._open(req) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=sorted(VOICE))
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    tok = yt.access_token()
    ch = yt.channel(tok)
    expect = (os.environ.get("EXPECT_CHANNEL") or "").strip()
    if expect and expect.lower() not in ch["title"].lower():
        raise SystemExit("token is for %r, expected %r" % (ch["title"], expect))

    items = threads(tok, ch["id"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=a.days)
    titles = {}
    todo = []
    for t in items:
        top = t["snippet"]["topLevelComment"]["snippet"]
        author = (top.get("authorChannelId") or {}).get("value")
        if author == ch["id"]:
            continue                                  # our own pinned question
        replied = any(((r["snippet"].get("authorChannelId") or {}).get("value") == ch["id"])
                      for r in (t.get("replies") or {}).get("comments", []))
        if replied:
            continue
        when = datetime.strptime(top["publishedAt"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        if when < cutoff:
            continue
        text = top.get("textOriginal") or top.get("textDisplay") or ""
        if not text.strip() or SPAM.search(text):
            continue
        todo.append((t["id"], top.get("videoId"), text))

    print("%s: %d threads read, %d unanswered comments from viewers in %d days"
          % (ch["title"], len(items), len(todo), a.days), flush=True)

    # titles, so the reply knows what the video was about
    vids = sorted(set(v for _, v, _ in todo if v))
    for k in range(0, len(vids), 50):
        j = yt.get(yt.DATA_API + "/videos?part=snippet&id=" + ",".join(vids[k:k + 50]), tok)
        for v in j.get("items", []):
            titles[v["id"]] = v["snippet"]["title"]

    log_path = os.path.join(store.DIR, "replies_%s.jsonl" % a.key)
    done = 0
    for thread_id, vid, text in todo:
        if done >= a.max:
            print("   run limit reached - the rest wait for the next run", flush=True)
            break
        reply = write_reply(a.key, titles.get(vid, ""), text)
        print("\n   [%s] %s" % (titles.get(vid, "?")[:40], text[:90].replace("\n", " ")), flush=True)
        if not reply:
            print("   -> skipped (nothing specific to say)", flush=True)
            continue
        print("   -> %s" % reply, flush=True)
        if a.check:
            continue
        try:
            post_reply(tok, thread_id, reply)
            done += 1
            with io.open(log_path, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps({"date": date.today().isoformat(), "video": vid,
                                    "comment": text[:300], "reply": reply},
                                   ensure_ascii=False) + "\n")
            time.sleep(4)                 # a person replies at a person's pace
        except Exception as e:
            print("   could not post: %s" % str(e)[:140], flush=True)
    print("\nreplied to %d comments%s" % (done, " (check only)" if a.check else ""), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
