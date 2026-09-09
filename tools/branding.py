# -*- coding: utf-8 -*-
"""Make the channel page answer the three questions it has to.

A visitor who taps through from a Short lands on the channel page with about
two seconds of patience and three questions: who is this for, what do I get,
why should I come back. Right now:

    FaRu Fact          description completely EMPTY
    Rise With Fate     description fine, no sections, nothing featured
    History Explains   description fine, no sections, nothing featured

An empty description is not only a page that says nothing - it is also the text
YouTube reads to decide what the channel is about and who to suggest it to.

This sets the description and channel keywords where they are missing or thin,
and builds the homepage: a featured section pointing at the Start Here playlist
and another at the Documentaries playlist, so the first thing a visitor sees is
the channel's best work and its long-form, rather than a reverse-chronological
wall of whatever published last.

Everything is read before it is written and merged rather than replaced -
channels.update replaces the whole brandingSettings object, so sending a partial
one wipes the banner, the trailer and the country.

    python tools/branding.py history --check
    python tools/branding.py history --apply

Env: REFRESH_TOKEN with the editing scope (/api/yt-auth?manage=1).
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN_URL = "https://faru-pwa.vercel.app/api/yt-token"
API = "https://www.googleapis.com/youtube/v3"

# Written to say what the viewer gets and why to come back, not what the channel
# "is about" - the second is what every dead channel description says.
DESCRIPTIONS = {
    "fun": (
        "Short, surprising facts that turn out to be true - the ones that sound "
        "made up until you look them up.\n\n"
        "Every video takes one thing you are fairly sure about and shows you it "
        "is wrong, in under a minute, with the detail you need to check it "
        "yourself.\n\n"
        "New facts several times a week. Subscribe if you are the person your "
        "friends send these to."
    ),
    "us": (
        "Motivation for people who are tired of motivation.\n\n"
        "No shouting, no posters, no quotes over a mountain. Each video takes "
        "one thing you believe about yourself - that it is too late, that you "
        "need more discipline, that you should have started earlier - and shows "
        "you what is actually true, with something you can do about it today.\n\n"
        "Short films several times a week, and longer ones on Mondays and "
        "Fridays. Subscribe if you would rather be told the truth than cheered "
        "at."
    ),
    "history": (
        "The history your class skipped, and why it still decides things today.\n\n"
        "Empires, money, inventions and the accidents that changed everything - "
        "each one told with the dates and numbers, so you can check it and argue "
        "with it.\n\n"
        "Short ones through the week, full documentaries four times a week. "
        "Subscribe if you have ever finished a history lesson thinking that "
        "cannot be the whole story."
    ),
}

KEYWORDS = {
    "fun": "facts surprising facts true facts science trivia did you know",
    "us": "motivation discipline mindset self improvement focus habits",
    "history": "history documentary empires ancient history world history money",
}

# Which playlists to feature on the homepage, in order. Best work first: a
# first-time visitor should not have to scroll past this week's uploads.
SECTIONS = ["Start Here - Best of the Channel", "Documentaries"]


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


def send(url, tok, body, method):
    return json.loads(_open(urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method=method,
        headers={"Authorization": "Bearer " + tok,
                 "Content-Type": "application/json"})).read())


def playlists(tok):
    out, page = {}, None
    while True:
        u = API + "/playlists?part=snippet&mine=true&maxResults=50"
        if page:
            u += "&pageToken=" + page
        j = get(u, tok)
        for p in j.get("items", []):
            out[p["snippet"]["title"]] = p["id"]
        page = j.get("nextPageToken")
        if not page:
            break
    return out


def check_channel(actual, expected):
    """Stop before writing if the token is not the channel we were told."""
    if not expected:
        return
    if actual.strip().lower() != expected.strip().lower():
        raise SystemExit(
            "REFUSING TO WRITE."
            "\n  this run is for : %s"
            "\n  the token is    : %s"
            "\nA swapped secret would edit the wrong channel. Fix the secret "
            "rather than removing this check." % (expected, actual))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", choices=sorted(DESCRIPTIONS))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--expect", default="",
                    help="the channel title this run is for - the tool "
                         "refuses to write if the token is a different one")
    a = ap.parse_args()

    tok = access_token()
    ch = get(API + "/channels?part=snippet,brandingSettings&mine=true", tok)
    if not ch.get("items"):
        raise SystemExit("no channel for this token")
    c = ch["items"][0]
    cid = c["id"]
    print("channel: %s  (%s)" % (c["snippet"]["title"], cid), flush=True)
    check_channel(c["snippet"]["title"], a.expect)

    branding = c.get("brandingSettings") or {}
    chan = branding.setdefault("channel", {})

    # Comments are turned off on every video on all three channels, verified on
    # ten of them from May to September. Before telling Fatema that is a Studio
    # setting only she can reach, print what the API actually holds - if the
    # cause is moderateComments then this tool can set it and she need not touch
    # anything.
    print("\nWHAT THE API KNOWS ABOUT THIS CHANNEL")
    for k in sorted(chan):
        val = chan[k]
        if isinstance(val, str) and len(val) > 60:
            val = val[:60] + "..."
        print("  %-30s %r" % (k, val))
    for k in ("moderateComments",):
        if k not in chan:
            print("  %-30s (not returned by the API at all)" % k)

    # The watch page says "Comments are turned off." on every video on every
    # channel. I read the page for a Save-to-playlist button and a notification
    # bell, found both, and concluded these are not made for kids - but the
    # page is not the authority on that. status.madeForKids is, and it costs
    # one call to ask. YouTube's own classifier can set it regardless of what
    # the upload declared, and made-for-kids disables comments outright.
    print("\nIS YOUTUBE TREATING THESE AS MADE FOR KIDS?")
    try:
        up = get(API + "/channels?part=contentDetails&mine=true", tok)
        pl = up["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        j = get(API + "/playlistItems?part=contentDetails&maxResults=3&playlistId=" + pl, tok)
        ids = [i["contentDetails"]["videoId"] for i in j.get("items", [])]
        v = get(API + "/videos?part=status,snippet&id=" + ",".join(ids), tok)
        for it in v.get("items", []):
            st = it["status"]
            print("  %s  madeForKids=%-5s selfDeclared=%-5s  %s"
                  % (it["id"], st.get("madeForKids"),
                     st.get("selfDeclaredMadeForKids"),
                     it["snippet"]["title"][:38]))
    except Exception as e:
        print("  could not check: %s" % str(e)[:140])
    cur = (chan.get("description") or "").strip()
    want = DESCRIPTIONS[a.channel]

    print("\nDESCRIPTION")
    print("  now:  %s" % (("%d chars - %s..." % (len(cur), cur[:70])) if cur else "*** EMPTY ***"))
    # Only replace something short enough to be a placeholder. A description
    # Fatema wrote herself should not be silently overwritten.
    if len(cur) >= 400:
        print("  keeping it - it is already substantial")
    else:
        print("  new:  %s..." % want[:70])
        if a.apply:
            chan["description"] = want
            chan["keywords"] = KEYWORDS[a.channel]
            try:
                # The whole brandingSettings object is replaced by this call, so
                # it is the one that was just read, with two fields changed.
                send(API + "/channels?part=brandingSettings", tok,
                     {"id": cid, "brandingSettings": branding}, "PUT")
                print("  DESCRIPTION SET", flush=True)
            except Exception as e:
                print("  failed: %s" % str(e)[:220], flush=True)

    print("\nHOMEPAGE SECTIONS")
    pls = playlists(tok)
    have = get(API + "/channelSections?part=snippet,contentDetails&mine=true", tok)
    featured = set()
    for s in have.get("items", []):
        for p in (s.get("contentDetails") or {}).get("playlists", []) or []:
            featured.add(p)
    print("  existing sections: %d" % len(have.get("items", [])))

    pos = len(have.get("items", []))
    for title in SECTIONS:
        pid = pls.get(title)
        if not pid:
            print("  %-38s playlist does not exist yet" % title)
            continue
        if pid in featured:
            print("  %-38s already featured" % title)
            continue
        print("  %-38s WILL FEATURE (%s)" % (title, pid))
        if not a.apply:
            continue
        try:
            send(API + "/channelSections?part=snippet,contentDetails", tok,
                 {"snippet": {"type": "singlePlaylist", "style": "horizontalRow",
                              "position": pos},
                  "contentDetails": {"playlists": [pid]}}, "POST")
            print("    FEATURED", flush=True)
            pos += 1
        except Exception as e:
            print("    failed: %s" % str(e)[:220], flush=True)

    if not (a.apply or a.check):
        print("\n(nothing changed - pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
