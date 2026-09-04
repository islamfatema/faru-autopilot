# -*- coding: utf-8 -*-
"""Upload a finished documentary + set its custom thumbnail."""
# Which channel to publish to is chosen by YT_TOKEN_ENV, so the same engine
# serves all three channels instead of being hard wired to one.
import os, sys, json, urllib.request

def _open(req, t=600):
    try: return urllib.request.urlopen(req, timeout=t)
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode("utf-8","replace")[:400]); raise

def token():
    d=json.dumps({"refresh_token":os.environ[os.environ.get("YT_TOKEN_ENV", "YT_REFRESH_TOKEN_HISTORY")].strip()}).encode()
    r=urllib.request.Request("https://faru-pwa.vercel.app/api/yt-token",data=d,
                             headers={"Content-Type":"application/json"})
    return json.loads(_open(r,90).read())["access_token"]

def record_featured(vid, title):
    """Tell the Shorts machine which documentary to send viewers to.

    The Shorts are the only traffic these channels have and they pay almost
    nothing - about two cents per thousand views. The documentaries pay several
    dollars per thousand and are what accumulates watch hours. Linking one to
    the other is free, so every Short published after this points at the newest
    film. The Shorts run reads this file; if it is absent it just omits the line.
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(os.path.dirname(here), "featured_long.json")
        json.dump({"id": vid, "title": title,
                   "url": "https://youtu.be/%s" % vid},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("featured long-form recorded: %s" % vid, flush=True)
    except Exception as e:
        print("could not record the featured video: %s" % str(e)[:120], flush=True)


def upload(path, meta, thumb=None):
    tok=token()
    body=json.dumps({"snippet":{"title":meta["title"],"description":meta["description"],
                                "tags":meta["tags"],"categoryId":"27"},
                     "status":{"privacyStatus":os.environ.get("YT_PRIVACY","public"),
                               "selfDeclaredMadeForKids":False}}).encode()
    req=urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=body,headers={"Authorization":"Bearer "+tok,
                           "Content-Type":"application/json; charset=UTF-8",
                           "X-Upload-Content-Type":"video/mp4"})
    with _open(req,120) as r: loc=r.headers.get("Location")
    blob=open(path,"rb").read()
    put=urllib.request.Request(loc,data=blob,method="PUT",
        headers={"Content-Type":"video/mp4","Content-Length":str(len(blob))})
    with _open(put,1800) as r: vid=json.loads(r.read())["id"]
    print("UPLOADED https://youtu.be/%s" % vid, flush=True)
    record_featured(vid, meta.get("title", ""))
    if thumb and os.path.exists(thumb):
        tb=open(thumb,"rb").read()
        tr=urllib.request.Request(
            "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId="+vid,
            data=tb,method="POST",
            headers={"Authorization":"Bearer "+tok,"Content-Type":"image/png",
                     "Content-Length":str(len(tb))})
        try:
            _open(tr,300); print("THUMBNAIL set", flush=True)
        except Exception as e:
            print("thumbnail failed (needs a verified channel):", str(e)[:120])
    return vid

if __name__=="__main__":
    meta=json.load(open(sys.argv[2],encoding="utf-8"))
    upload(sys.argv[1], meta, sys.argv[3] if len(sys.argv)>3 else None)
