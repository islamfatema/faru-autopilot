# -*- coding: utf-8 -*-
"""
Rise Daily - headless US motivation Short generator + YouTube uploader.
Runs in GitHub Actions on a cron (5x/day): builds a fresh cinematic motivation
Short (AI image + Ken Burns zoom + deep US narrator voice + animated quote text
+ channel watermark) and uploads it to the USA YouTube channel. No device needed.

Env: YT_REFRESH_TOKEN_US (required)  YT_PRIVACY (default 'public')
"""
import os, sys, json, subprocess, asyncio, time, random, shutil, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work"); os.makedirs(WORK, exist_ok=True)
ASSETS = os.path.join(HERE, "assets")
FONT = os.path.join(ASSETS, "Anton-Regular.ttf")
LOGO = os.path.join(ASSETS, "logo.png")
W, H = 1080, 1920   # full HD vertical
VOICE = "en-US-GuyNeural"   # upbeat, friendly US male voice (fits fun facts)

BANK = json.load(open(os.path.join(HERE, "scripts_fun.json"), encoding="utf-8"))

CHANNEL_KEY = "fun"

# ---------------- winner-loop: bias topic selection toward what is working ----------------
# One line at the end of every description. These videos reach exactly the
# people this app is for, and telling them costs nothing.
PROMO = ("\n---\n"
         "Made with Faru AI OS: type an idea, get a finished video with "
         "voice, captions and music, and post it to YouTube automatically.\n"
         "Try it free for 2 days: https://faru-pwa.vercel.app\n")


def biased_bank():
    """If analytics found winning tags for this channel, weight the rotation 2:1
    toward scripts carrying those tags (still cycles everything, never repeats early)."""
    try:
        wf = os.path.join(HERE, "..", "analytics", "winners_%s.json" % CHANNEL_KEY)
        wt = set(t.lower() for t in json.load(open(wf, encoding="utf-8"))["tags"])
    except Exception:
        return BANK
    if not wt:
        return BANK
    win, rest = [], []
    for d in BANK:
        (win if wt & set(t.lower() for t in d.get("tags", [])) else rest).append(d)
    if not win or not rest:
        return BANK
    out, wi, ri = [], 0, 0
    while wi < len(win) or ri < len(rest):
        for _ in range(2):
            if wi < len(win):
                out.append(win[wi]); wi += 1
        if ri < len(rest):
            out.append(rest[ri]); ri += 1
    print("winner-loop: %d winning-tag scripts prioritised" % len(win), flush=True)
    return out

BANK_ORDERED = biased_bank()

# Rotation origin: the day the non-repeating rotation was introduced.
# Do not change this - moving it re-runs scripts the channel has already posted.
ROTATION_ORIGIN = 1787961600   # 2026-08-29 00:00 UTC


def next_index(i):
    """Index of the i-th video in this run, advancing once per video published.

    This used to be int(time.time() // 3600) + i, which moved 24 places a day
    while the channel published 10 videos. The bank was consumed two and a half
    times faster than it was read, so a 64 script bank wrapped in under three
    days and the same videos went up again - which is what YouTube penalised.

    Deriving the slot from the posting interval instead means the index advances
    by exactly RUNS_PER_DAY * COUNT each day: one step per video, no skipping,
    and a full pass takes len(bank) / videos-per-day days.
    """
    runs = max(1, int(os.environ.get("RUNS_PER_DAY", "5")))
    count = max(1, int(os.environ.get("COUNT", "1")))
    step = 86400 // runs
    # Counted from a fixed origin, not from the epoch: an epoch-based slot is a
    # six figure number, so idx % len(bank) lands arbitrarily and wraps however
    # large the bank gets. From a fixed origin the index starts at 0 and climbs
    # one per video, so a growing bank genuinely prevents repeats.
    slot = int((time.time() - ROTATION_ORIGIN) // step)
    return max(0, slot) * count + i

def run(args, cwd=None):
    p = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    if p.returncode != 0:
        print("CMD FAIL:", " ".join(str(a) for a in args[:8]))
        print((p.stderr or "")[-2000:]); sys.exit(1)
    return p

def dur(path):
    p = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration","-of","json",path],
                       capture_output=True, text=True)
    return float(json.loads(p.stdout)["format"]["duration"])

# ---------------- 1. narration (edge-tts) ----------------
async def _tts(text, out):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate="-6%").save(out)

def make_voices(phrases):
    # Voice EACH on-screen line separately so spoken words exactly match the caption
    # shown at that moment (perfect sync).
    durs = []
    for i, p in enumerate(phrases):
        spoken = p.replace("\n", " ").replace("—", ", ").strip()
        mp3 = os.path.join(WORK, "raw%d.mp3" % i); last = None
        for attempt in range(5):
            try:
                asyncio.run(_tts(spoken, mp3))
                if os.path.getsize(mp3) > 1200: break
            except Exception as e:
                last = e; print("tts try %d failed: %s" % (attempt+1, str(e)[:90])); time.sleep(4)
        else:
            raise RuntimeError("edge-tts failed after retries: %s" % last)
        wav = os.path.join(WORK, "p%d.wav" % i)
        run(["ffmpeg","-y","-i",mp3,"-af","loudnorm=I=-16:TP=-1.5:LRA=11","-ar","48000","-ac","2",wav])
        durs.append(dur(wav))
    return durs

# ---------------- soft background music (procedural = copyright-safe, monetization-safe) ----------------
def make_music(dur_s, out):
    # A warm C-major pad (organ-like: fundamentals + 2nd harmonic), with a slow
    # ~16s "breathing" swell. Fully synthesized -> zero Content ID / copyright risk.
    notes = [130.81, 164.81, 196.00, 261.63, 329.63]  # C3 E3 G3 C4 E4
    body = "+".join("(sin(2*PI*%.2f*t)+0.3*sin(2*PI*%.2f*t))" % (f, 2*f) for f in notes)
    expr = "(0.55+0.45*sin(2*PI*t/16))*0.12*(%s)" % body
    fo = max(0.0, dur_s - 2.0)
    run(["ffmpeg","-y","-f","lavfi","-i","aevalsrc=%s:s=48000:d=%.2f" % (expr, dur_s),
         "-af","tremolo=f=0.1:d=0.4,aecho=0.85:0.9:900|1600:0.3|0.2,lowpass=f=2200,highpass=f=70,"
               "afade=t=in:st=0:d=2,afade=t=out:st=%.2f:d=2" % fo,
         "-ac","2","-ar","48000", out])

# ---------------- 2. background image (Pollinations, with bundled fallback) ----------------
STYLE_SUFFIX = ", photorealistic, cinematic photography, sharp focus, highly detailed, professional lighting, 8k"

def get_image(prompt, slot):
    prompt = prompt + STYLE_SUFFIX
    dst = os.path.join(WORK, "bg.jpg")
    enc = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    url = ("https://image.pollinations.ai/prompt/%s?width=1080&height=1920&nologo=true&seed=%d&model=flux"
           % (enc, seed))
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            if len(data) > 8000:
                open(dst, "wb").write(data)
                print("image: Pollinations ok (%d bytes)" % len(data))
                return dst
        except Exception as e:
            print("Pollinations try failed:", str(e)[:120]); time.sleep(3)
    # fallback: one of the bundled cinematic backgrounds
    k = (slot % 4) + 1
    shutil.copy(os.path.join(ASSETS, "bg%d.jpg" % k), dst)
    print("image: fallback bg%d.jpg" % k)
    return dst



SHOT_ANGLES = ["cinematic wide establishing shot", "dramatic close up detail shot",
               "epic aerial view", "macro detail shot, shallow depth of field",
               "dynamic low angle shot", "atmospheric medium shot"]

MAX_IMAGES = 6   # more than this just slows the run down; images are reused instead

def get_images(base_prompt, n, slot):
    """Distinct on-topic images so the visual changes every few seconds. Capped at
    MAX_IMAGES and cycled, which keeps CI runs fast and cheap."""
    want = min(n, MAX_IMAGES)
    paths = []
    for i in range(want):
        dst = os.path.join(WORK, "img%d.jpg" % i)
        prompt = "%s, %s%s" % (base_prompt, SHOT_ANGLES[i % len(SHOT_ANGLES)], STYLE_SUFFIX)
        url = ("https://image.pollinations.ai/prompt/%s?width=1080&height=1920"
               "&nologo=true&seed=%d&model=flux"
               % (urllib.parse.quote(prompt), random.randint(1, 999999)))
        ok = False
        for _ in range(2):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=25) as r:
                    data = r.read()
                if len(data) > 8000:
                    open(dst, "wb").write(data); ok = True; break
            except Exception as e:
                print("  img%d retry: %s" % (i, str(e)[:60])); time.sleep(1)
        if not ok:
            shutil.copy(os.path.join(ASSETS, "bg%d.jpg" % ((slot + i) % 4 + 1)), dst)
        paths.append(dst)
    while len(paths) < n:          # cycle back through them for the remaining lines
        paths.append(paths[len(paths) % want])
    print("images: %d distinct visuals for %d lines" % (want, n), flush=True)
    return paths

# ---------------- caption fitting (prevents text overflowing off screen edges) ----------------
def fit_lines(text, maxw, base, minsz=44, maxlines=3):
    """Wrap+shrink a caption so every line fits inside maxw pixels.
    Fixes first/last words being cut off on mobile when a line was wider than the frame."""
    from PIL import ImageFont
    words = text.replace(chr(10), " ").split()
    best = ([text], minsz)
    for size in range(base, minsz - 1, -4):
        f = ImageFont.truetype(FONT, size)
        lines, cur, ok = [], "", True
        for w in words:
            t = (cur + " " + w).strip()
            if f.getlength(t) <= maxw:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
                if f.getlength(w) > maxw:
                    ok = False
                    break
        if cur:
            lines.append(cur)
        if ok and len(lines) <= maxlines:
            return lines, size
        best = (lines, size)
    return best

# ---------------- 3. compose (ffmpeg) ----------------
def compose(imgs, phrases, durs):
    """One clip per line - its own image, camera move, handheld wobble, atmosphere
    and grain - crossfaded together. Replaces the single static background."""
    for f in (FONT, LOGO, os.path.join(ASSETS, "fog.jpg")):
        shutil.copy(f, os.path.join(WORK, os.path.basename(f)))
    N = len(phrases)
    moves = ["push", "pan_r", "pull", "tilt_d", "diag", "pan_l", "tilt_u"]
    XF = 0.32
    clips = []
    for i, p in enumerate(phrases):
        d = durs[i] + 0.55
        frames = int(d * 30)
        lines, sz = fit_lines(p, int(W * 0.86), 86)
        open(os.path.join(WORK, "p%d.txt" % i), "w", encoding="utf-8",
             newline=chr(10)).write(chr(10).join(lines))
        mv = moves[i % len(moves)]
        ph = (i % 5) * 1.1
        OW, OH = int(W * 1.14), int(H * 1.14)
        zi, zo = "min(1.0+0.00055*on,1.30)", "max(1.30-0.00055*on,1.0)"
        cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        if mv == "push":
            z, x, y = zi, cx, cy
        elif mv == "pull":
            z, x, y = zo, cx, cy
        elif mv == "pan_r":
            z, x, y = "1.26", "min(on/%d*(iw-iw/zoom),iw-iw/zoom)" % frames, cy
        elif mv == "pan_l":
            z, x, y = "1.26", "max((1-on/%d)*(iw-iw/zoom),0)" % frames, cy
        elif mv == "tilt_d":
            z, x, y = "1.26", cx, "min(on/%d*(ih-ih/zoom),ih-ih/zoom)" % frames
        elif mv == "tilt_u":
            z, x, y = "1.26", cx, "max((1-on/%d)*(ih-ih/zoom),0)" % frames
        else:
            z = zi
            x = "min(on/%d*(iw-iw/zoom),iw-iw/zoom)" % frames
            y = "min(on/%d*(ih-ih/zoom),ih-ih/zoom)" % frames
        jx = "(iw-ow)/2 + 9*sin(2*PI*t*0.63+%.2f) + 5*sin(2*PI*t*1.27+%.2f)" % (ph, ph * 1.7)
        jy = "(ih-oh)/2 + 7*sin(2*PI*t*0.48+%.2f) + 4*sin(2*PI*t*1.09+%.2f)" % (ph * 1.3, ph)
        fc = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
              "zoompan=z='%s':x='%s':y='%s':d=%d:s=%dx%d:fps=30,"
              "crop=%d:%d:x='%s':y='%s'[mv];"
              "[1:v]scale=%d:%d,crop=%d:%d:x='120+90*sin(2*PI*t*0.05)':"
              "y='80+50*cos(2*PI*t*0.04)',format=gbrp,"
              "colorchannelmixer=rr=0.15:gg=0.15:bb=0.16[fog];"
              "[mv][fog]blend=all_mode=screen,"
              "drawbox=x=0:y=0:w=%d:h=%d:color=black@0.26:t=fill,"
              "eq=contrast=1.05:saturation=1.06,noise=alls=6:allf=t+u,vignette=PI/5,"
              "drawtext=fontfile=Anton-Regular.ttf:textfile=p%d.txt:fontcolor=white:"
              "fontsize=%d:line_spacing=18:%s:y=(h-text_h)/2:borderw=9:"
              "bordercolor=black@0.9:shadowcolor=black@0.6:shadowx=3:shadowy=3[tx];"
              "movie=logo.png[lg];[tx][lg]overlay=x=(W-w)/2:y=56[v]"
              % (int(OW * 1.18), int(OH * 1.18), int(OW * 1.18), int(OH * 1.18),
                 z, x, y, frames, OW, OH, W, H, jx, jy,
                 int(W * 2.2), int(H * 1.35), W, H, W, H, i, sz, 'x=max(0\\,(w-text_w)/2)'))
        out = "clip%d.mp4" % i
        run(["ffmpeg", "-y", "-loop", "1", "-i", os.path.basename(imgs[i]),
             "-loop", "1", "-i", "fog.jpg", "-f", "lavfi",
             "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", fc,
             "-map", "[v]", "-map", "2:a", "-t", "%.2f" % d,
             "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
             "-crf", "18", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
             out], cwd=WORK)
        clips.append(out)

    cur, cur_d = clips[0], durs[0] + 0.55
    for i in range(1, len(clips)):
        nd = durs[i] + 0.55
        off = max(0.1, cur_d - XF)
        out = "vmix%d.mp4" % i
        run(["ffmpeg", "-y", "-i", cur, "-i", clips[i], "-filter_complex",
             "[0:v][1:v]xfade=transition=fade:duration=%.2f:offset=%.2f[v]" % (XF, off),
             "-map", "[v]", "-an", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-preset", "medium", "-crf", "18", out], cwd=WORK)
        cur, cur_d = out, off + nd
    TOTAL = cur_d

    starts, t = [], 0.0
    for i in range(N):
        starts.append(t)
        t += durs[i] + 0.55 - (XF if i else 0)
    make_music(TOTAL, os.path.join(WORK, "music.wav"))
    ain, parts, labels = [], [], []
    for i in range(N):
        ain += ["-i", os.path.join(WORK, "p%d.wav" % i)]
        ms = int(max(0.0, starts[i] + 0.22) * 1000)
        parts.append("[%d:a]adelay=%d|%d,volume=1.0[v%d]" % (i, ms, ms, i))
        labels.append("[v%d]" % i)
    ain += ["-i", os.path.join(WORK, "music.wav")]
    parts.append("[%d:a]volume=1.0[mus]" % N)
    labels.append("[mus]")
    fa = (";".join(parts) + ";" + "".join(labels) +
          "amix=inputs=%d:normalize=0:dropout_transition=0,alimiter=limit=0.95,"
          "loudnorm=I=-15:TP=-1.5:LRA=11[a]" % len(labels))
    run(["ffmpeg", "-y", *ain, "-filter_complex", fa, "-map", "[a]",
         "-t", "%.2f" % TOTAL, "-ar", "48000", "-ac", "2",
         os.path.join(WORK, "mixed.wav")])

    out_mp4 = os.path.join(WORK, "final.mp4")
    run(["ffmpeg", "-y", "-i", cur, "-i", "mixed.wav", "-map", "0:v", "-map", "1:a",
         "-t", "%.2f" % TOTAL, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", os.path.basename(out_mp4)], cwd=WORK)
    return out_mp4


# ---------------- 4. upload to YouTube ----------------
def _open(req, timeout=60):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode("utf-8", "replace")[:500]
        except Exception: pass
        print("HTTP %s on %s -> %s" % (e.code, req.full_url, body)); raise

def yt_access_token():
    data = json.dumps({"refresh_token": os.environ["YT_REFRESH_TOKEN"].strip()}).encode()
    req = urllib.request.Request("https://faru-pwa.vercel.app/api/yt-token", data=data,
                                 headers={"Content-Type": "application/json"})
    with _open(req) as r:
        j = json.loads(r.read())
    if not j.get("access_token"):
        raise RuntimeError("no access_token in response: " + str(j)[:200])
    return j["access_token"]

def yt_upload(path, meta):
    tok = yt_access_token()
    body = json.dumps({"snippet": {"title": meta["title"], "description": meta["description"],
                                   "tags": meta.get("tags", []), "categoryId": "24"},
                       "status": {"privacyStatus": os.environ.get("YT_PRIVACY", "public"),
                                  "selfDeclaredMadeForKids": False}}).encode()
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=body, headers={"Authorization": "Bearer " + tok,
                            "Content-Type": "application/json; charset=UTF-8",
                            "X-Upload-Content-Type": "video/mp4"})
    with _open(req) as r:
        loc = r.headers.get("Location")
    blob = open(path, "rb").read()
    put = urllib.request.Request(loc, data=blob, method="PUT",
                                 headers={"Content-Type": "video/mp4", "Content-Length": str(len(blob))})
    with _open(put, 300) as r:
        res = json.loads(r.read())
    return res.get("id")

import urllib.parse  # noqa (used in get_image)

CTAS = ["Subscribe for history that explains the world.",
        "Follow for more history you were never taught.",
        "Save this and share a fact that surprised you.",
        "Comment which fact shocked you the most.",
        "Save this - you will want to tell someone."]
FUN_TAGS = ["facts", "funfacts", "didyouknow", "shorts", "amazingfacts", "weirdfacts",
            "mindblowing", "interesting", "viral", "trending", "wtf", "unbelievable"]

HOOKS = ["This sounds fake, but it's real.", "You won't believe this actually happened.",
         "Wait for the last one.", "This fact broke my brain.", "Nobody believes this one."]

def build_one(idx):
    d = json.loads(json.dumps(BANK_ORDERED[idx % len(BANK_ORDERED)]))
    print("--- [%d] %s" % (idx, d["title"]), flush=True)
    phrases = [HOOKS[idx % len(HOOKS)]] + d["phrases"]   # strong 1st-second hook = better retention
    durs = make_voices(phrases)
    imgs = get_images(d.get("img", "vivid colorful eye catching scene, dramatic lighting, high detail, vertical 9:16"), len(phrases), idx)
    mp4 = compose(imgs, phrases, durs)
    tags = list(dict.fromkeys(d.get("tags", []) + FUN_TAGS))[:15]
    hashtags = " ".join("#" + t for t in tags)
    # This channel was telling its own viewers to subscribe to History That
    # Explains the World - a copy-paste from the other channel's file, sending
    # away the audience of a channel with twelve subscribers.
    desc = ("🌍 " + CTAS[idx % len(CTAS)] + "\n"
            + "▶ https://faru-pwa.vercel.app - free 2 days\n\n"
            + d["narration"]
            + "\n\nSubscribe to FaRu Facts for a surprising true fact every day.\n\n"
            + PROMO + "\n" + hashtags)
    return mp4, {"title": d["title"][:95], "description": desc, "tags": tags}

def main():
    count = max(1, int(os.environ.get("COUNT", "1")))
    dry = bool(os.environ.get("DRY_RUN"))
    urls = []
    print("bank: %d scripts, %s days of runway at this rate"
          % (len(BANK_ORDERED),
             len(BANK_ORDERED) // max(1, count * int(os.environ.get("RUNS_PER_DAY", "5")))),
          flush=True)
    for i in range(count):
        try:
            mp4, meta = build_one(next_index(i))
            if dry:
                print("DRY_RUN - built only:", mp4, flush=True); continue
            vid = yt_upload(mp4, meta)
            u = "https://youtu.be/%s" % vid
            urls.append(u); print("UPLOADED %d/%d %s" % (i + 1, count, u), flush=True)
            if i < count - 1:
                time.sleep(6)  # be gentle between uploads
        except Exception as e:
            print("FAILED item %d: %s" % (i + 1, str(e)[:200]), flush=True)
    print("ALL_URLS " + " ".join(urls), flush=True)

if __name__ == "__main__":
    main()
