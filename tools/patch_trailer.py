# -*- coding: utf-8 -*-
"""Give the channel page a trailer for people who are not subscribed.

A visitor who taps through from a Short lands on a wall of thumbnails and
decides in about two seconds. YouTube will autoplay one video for them - the
unsubscribed trailer - and on all three channels that slot is empty, so the
best-performing video on the channel never gets shown to the person most likely
to subscribe.

The trailer is set to the most-watched Short rather than to a documentary: the
visitor has seconds of patience, and a 20-second video that already proved it
holds people is a better argument than twelve minutes they will not start.
It is re-checked on every run, so as a better video appears it takes the slot.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "tools", "branding.py")

HELPER = '''
def best_short(tok):
    """The most-watched video under four minutes, with its view count."""
    try:
        up = get(API + "/channels?part=contentDetails&mine=true", tok)
        pl = up["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        ids, page = [], None
        while len(ids) < 200:
            u = (API + "/playlistItems?part=contentDetails&maxResults=50&playlistId=" + pl)
            if page:
                u += "&pageToken=" + page
            j = get(u, tok)
            ids += [i["contentDetails"]["videoId"] for i in j.get("items", [])]
            page = j.get("nextPageToken")
            if not page:
                break
        best = None
        for k in range(0, len(ids), 50):
            j = get(API + "/videos?part=snippet,statistics,contentDetails&id="
                    + ",".join(ids[k:k + 50]), tok)
            for v in j.get("items", []):
                dur = v["contentDetails"]["duration"]
                secs = 0
                m = re.match(r"PT(?:(\\d+)M)?(?:(\\d+)S)?", dur)
                if m:
                    secs = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
                if not secs or secs > 240:
                    continue
                views = int(v["statistics"].get("viewCount") or 0)
                if not best or views > best[1]:
                    best = (v["id"], views, v["snippet"]["title"])
        return best
    except Exception as e:
        print("  could not read the uploads: %s" % str(e)[:120], flush=True)
        return None

'''

OLD = '''    cur = (chan.get("description") or "").strip()
    want = DESCRIPTIONS[a.channel]'''
NEW = '''    # The autoplaying video for people who are not subscribed. Empty on all
    # three channels, which wastes the one slot YouTube gives the channel page
    # to make its case.
    print("\\nTRAILER FOR NON-SUBSCRIBERS")
    now_trailer = chan.get("unsubscribedTrailer")
    pick = best_short(tok)
    if not pick:
        print("  no video to use")
    elif now_trailer == pick[0]:
        print("  already the best one: %s (%d views)" % (pick[2][:44], pick[1]))
    else:
        print("  now:  %s" % (now_trailer or "*** EMPTY ***"))
        print("  new:  %s  (%d views) %s" % (pick[0], pick[1], pick[2][:44]))
        if a.apply:
            chan["unsubscribedTrailer"] = pick[0]
            try:
                send(API + "/channels?part=brandingSettings", tok,
                     {"id": cid, "brandingSettings": branding}, "PUT")
                print("  TRAILER SET", flush=True)
            except Exception as e:
                print("  could not set the trailer: %s" % str(e)[:160], flush=True)

    cur = (chan.get("description") or "").strip()
    want = DESCRIPTIONS[a.channel]'''


def patch():
    s = io.open(PATH, encoding="utf-8").read()
    if "def best_short" in s:
        print("already patched")
        return
    if s.count(OLD) != 1:
        raise SystemExit("description block found %d times" % s.count(OLD))
    s = s.replace(OLD, NEW)
    s = s.replace("def main():", HELPER.strip("\n") + "\n\n\ndef main():", 1)
    if "\nimport re" not in s:
        s = s.replace("import argparse", "import argparse\nimport re", 1)
    ast.parse(s)
    tmp = PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, PATH)
    print("patched tools/branding.py")


patch()
