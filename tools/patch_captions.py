# -*- coding: utf-8 -*-
"""Upload the real subtitles with every Short.

YouTube writes its own captions by listening to the narration, and it gets
names wrong - Antikythera, Ea-nasir, Turritopsis, thermopolium - which matters
twice over. Captions are read by the search index, so a video about the
Antikythera mechanism is currently indexed under whatever the machine heard.
And a viewer with the sound off reads them.

We already know the exact words and their measured lengths: every caption line
is voiced separately, so `durs[i]` is the true duration of line i. That is a
subtitle file with perfect timing, for free, and it takes one API call.

captions.insert needs the force-ssl scope, which the upload token does not have
and the manage token now does - so the posting workflows pass the manage token
in as YT_REFRESH_TOKEN_CAPTIONS. Without it nothing happens and the upload is
unaffected.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

HELPER = '''
LAST_CAPTIONS = ([], [])     # the words and measured lengths of the last render


def _srt_time(t):
    """00:00:03,140 - the format SRT insists on."""
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def build_srt(phrases, durs):
    """A subtitle file with the timing the renderer actually used."""
    out, t = [], 0.0
    n = len(phrases)
    for i, (p, d) in enumerate(zip(phrases, durs)):
        end = t + d + tail(i, n)
        out.append("%d\\n%s --> %s\\n%s\\n" % (i + 1, _srt_time(t), _srt_time(end),
                                             p.replace(chr(10), " ")))
        t = end
    return "\\n".join(out)


def upload_captions(vid):
    """Attach the real subtitles. Needs a token carrying force-ssl."""
    refresh = (os.environ.get("YT_REFRESH_TOKEN_CAPTIONS") or "").strip()
    phrases, durs = LAST_CAPTIONS
    if not refresh or not phrases or len(phrases) != len(durs):
        return False
    try:
        tok = yt_access_token(refresh)
        srt = build_srt(phrases, durs).encode("utf-8")
        meta = json.dumps({"snippet": {"videoId": vid, "language": "en",
                                       "name": "English", "isDraft": False}}).encode()
        b = "faru" + str(random.randint(10 ** 9, 10 ** 10))
        body = (("--%s\\r\\nContent-Type: application/json; charset=UTF-8\\r\\n\\r\\n" % b).encode()
                + meta
                + ("\\r\\n--%s\\r\\nContent-Type: application/octet-stream\\r\\n\\r\\n" % b).encode()
                + srt
                + ("\\r\\n--%s--\\r\\n" % b).encode())
        req = urllib.request.Request(
            "https://www.googleapis.com/upload/youtube/v3/captions?part=snippet&uploadType=multipart",
            data=body, headers={"Authorization": "Bearer " + tok,
                                "Content-Type": "multipart/related; boundary=" + b})
        with _open(req) as r:
            r.read()
        print("  captions uploaded (%d lines)" % len(phrases), flush=True)
        return True
    except Exception as e:
        # Never let a subtitle failure touch the video that already published.
        print("  captions failed: %s" % str(e)[:120], flush=True)
        return False

'''

OLD_TOKEN = "def yt_access_token():"
NEW_TOKEN = "def yt_access_token(refresh=None):"
OLD_ENV = '    data = json.dumps({"refresh_token": os.environ["%s"].strip()}).encode()'
NEW_ENV = ('    data = json.dumps({"refresh_token": (refresh or os.environ["%s"]).strip()}).encode()')
ENV_FOR = {"autopilot_us/main_us.py": "YT_REFRESH_TOKEN_US",
           "autopilot_fun/main_fun.py": "YT_REFRESH_TOKEN",
           "autopilot_history/main_history.py": "YT_REFRESH_TOKEN_HISTORY"}

OLD_DURS = "    durs = make_voices(phrases)"
NEW_DURS = '''    durs = make_voices(phrases)
    # Keep them for the subtitle file: these are measured lengths, so the
    # timing is exact rather than estimated from word counts.
    global LAST_CAPTIONS
    LAST_CAPTIONS = (list(phrases), list(durs))'''

OLD_CALL = '''            vid = yt_upload(mp4, meta)
            u = "https://youtu.be/%s" % vid'''
NEW_CALL = '''            vid = yt_upload(mp4, meta)
            upload_captions(vid)
            u = "https://youtu.be/%s" % vid'''


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def upload_captions" in s:
        print("  already patched: %s" % rel)
        return
    for old, what in ((OLD_TOKEN, "token"), (OLD_DURS, "durations"), (OLD_CALL, "upload call")):
        if s.count(old) != 1:
            raise SystemExit("%s: %s found %d times" % (rel, what, s.count(old)))
    env_old = OLD_ENV % ENV_FOR[rel]
    if s.count(env_old) != 1:
        raise SystemExit("%s: token env line found %d times" % (rel, s.count(env_old)))
    s = s.replace(OLD_TOKEN, NEW_TOKEN).replace(env_old, NEW_ENV % ENV_FOR[rel])
    s = s.replace(OLD_DURS, NEW_DURS).replace(OLD_CALL, NEW_CALL)
    s = s.replace("def yt_upload(", HELPER.strip("\n") + "\n\n\ndef yt_upload(", 1)
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
