# -*- coding: utf-8 -*-
"""
History That Explains the World - documentary engine v2 (ANTI-SLIDESHOW).

Enforces the channel visual standard:
  * no long uninterrupted static visuals
  * varied camera language per shot (push / pull / pan / tilt / diagonal)
  * mixed visual TYPES: cinematic reconstruction, animated map, document/artifact
    with highlight, typographic graphic, before/after compare
  * crossfade transitions so cuts feel edited, not concatenated
  * a storyboard ANALYZER that refuses to render if the plan looks like a slideshow

Usage: python docgen2.py <storyboard.json>   ->  _work2/final_doc.mp4
"""
import io, os, sys, json, subprocess, asyncio, time, random, math, textwrap
import urllib.request, urllib.parse, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
WORK = os.path.join(HERE, "_work2"); os.makedirs(WORK, exist_ok=True)
W, H, FPS = 1920, 1080, 30
VOICE = "en-US-ChristopherNeural"
shutil.copy(os.path.join(ASSETS, "Anton-Regular.ttf"), os.path.join(WORK, "font.ttf"))
shutil.copy(os.path.join(ASSETS, "logo.png"), os.path.join(WORK, "logo.png"))
shutil.copy(os.path.join(ASSETS, "fog.jpg"), os.path.join(WORK, "fog.jpg"))
FONT_PATH = os.path.join(WORK, "font.ttf")

VENC = ["-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
        "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]



def label_file(name, text):
    """Write on-screen text to a file so ffmpeg never has to parse it.

    drawtext's text= argument is parsed twice, so an apostrophe in a label like
    "Today's Workforce" ends the quoted string and the render dies. textfile=
    reads the bytes literally, which removes the whole class of problem.
    """
    p = os.path.join(WORK, name)
    io.open(p, "w", encoding="utf-8", newline="\n").write((text or "").strip())
    return name

def run(args):
    p = subprocess.run(args, capture_output=True, text=True, cwd=WORK)
    if p.returncode != 0:
        print("CMD FAIL:", " ".join(str(a) for a in args[:8]))
        print((p.stderr or "")[-1800:]); sys.exit(1)
    return p


def dur(name):
    p = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "json", os.path.join(WORK, name)], capture_output=True, text=True)
    return float(json.loads(p.stdout)["format"]["duration"])


# ---------------- narration ----------------
async def _tts(text, out):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate="-6%").save(out)


def tts(text, out_abs):
    for a in range(6):
        try:
            asyncio.run(_tts(text, out_abs))
            if os.path.getsize(out_abs) > 1500:
                return
        except Exception as e:
            print("  tts retry", a, str(e)[:60]); time.sleep(4)
    raise RuntimeError("edge-tts failed")


# ---------------- imagery ----------------
STYLE_SUFFIX = ", photorealistic, cinematic photography, sharp focus, highly detailed, professional lighting, 8k"

def fetch(prompt, dst_abs, w=1280, h=720):
    prompt = prompt + STYLE_SUFFIX
    url = ("https://image.pollinations.ai/prompt/%s?width=%d&height=%d&nologo=true&seed=%d&model=flux"
           % (urllib.parse.quote(prompt), w, h, random.randint(1, 999999)))
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=100) as r:
                data = r.read()
            if len(data) > 8000:
                open(dst_abs, "wb").write(data); return True
        except Exception as e:
            print("  img retry", str(e)[:60]); time.sleep(3)
    return False



# ---------------- cinematic motion: makes a still read as filmed footage ----------------
def live_chain(move, frames, seconds, idx):
    """Camera move + handheld wobble + slight perspective drift, cropped from an
    oversized frame so the wobble never exposes an edge. This is what separates
    'filmed' from 'photo with a zoom'."""
    OW, OH = 2240, 1260          # oversized working frame
    z_in  = "min(1.0+0.00055*on,1.30)"
    z_out = "max(1.30-0.00055*on,1.0)"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if move == "push":     z, x, y = z_in, cx, cy
    elif move == "pull":   z, x, y = z_out, cx, cy
    elif move == "pan_r":  z, x, y = "1.26", "min(on/%d*(iw-iw/zoom),iw-iw/zoom)" % frames, cy
    elif move == "pan_l":  z, x, y = "1.26", "max((1-on/%d)*(iw-iw/zoom),0)" % frames, cy
    elif move == "tilt_d": z, x, y = "1.26", cx, "min(on/%d*(ih-ih/zoom),ih-ih/zoom)" % frames
    elif move == "tilt_u": z, x, y = "1.26", cx, "max((1-on/%d)*(ih-ih/zoom),0)" % frames
    elif move == "diag":   z = z_in; x = "min(on/%d*(iw-iw/zoom),iw-iw/zoom)" % frames; y = "min(on/%d*(ih-ih/zoom),ih-ih/zoom)" % frames
    else:                  z, x, y = z_in, cx, cy
    # handheld: two out-of-phase sines per axis so it never looks mechanical
    ph = (idx % 5) * 1.1
    jx = "(iw-ow)/2 + 9*sin(2*PI*t*0.63+%.2f) + 5*sin(2*PI*t*1.27+%.2f)" % (ph, ph * 1.7)
    jy = "(ih-oh)/2 + 7*sin(2*PI*t*0.48+%.2f) + 4*sin(2*PI*t*1.09+%.2f)" % (ph * 1.3, ph)
    return ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
            "zoompan=z='%s':x='%s':y='%s':d=%d:s=%dx%d:fps=%d,"
            "crop=%d:%d:x='%s':y='%s'"
            % (int(OW * 1.16), int(OH * 1.16), int(OW * 1.16), int(OH * 1.16),
               z, x, y, frames, OW, OH, FPS, W, H, jx, jy))

def finish_look():
    """Shared grade so every shot feels like one film: contrast, warmth, grain, vignette."""
    return ("eq=contrast=1.06:saturation=1.05:gamma=0.98,"
            "noise=alls=7:allf=t+u,"
            "vignette=PI/5")

# ---------------- camera language ----------------
def cam_expr(move, frames):
    z_in = "min(1.0+0.00050*on,1.28)"
    z_out = "max(1.28-0.00050*on,1.0)"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if move == "push":
        z, x, y = z_in, cx, cy
    elif move == "pull":
        z, x, y = z_out, cx, cy
    elif move == "pan_r":
        z, x, y = "1.22", "min(on/%d*(iw-iw/zoom),iw-iw/zoom)" % frames, cy
    elif move == "pan_l":
        z, x, y = "1.22", "max((1-on/%d)*(iw-iw/zoom),0)" % frames, cy
    elif move == "tilt_d":
        z, x, y = "1.22", cx, "min(on/%d*(ih-ih/zoom),ih-ih/zoom)" % frames
    elif move == "tilt_u":
        z, x, y = "1.22", cx, "max((1-on/%d)*(ih-ih/zoom),0)" % frames
    elif move == "diag":
        z = z_in
        x = "min(on/%d*(iw-iw/zoom),iw-iw/zoom)" % frames
        y = "min(on/%d*(ih-ih/zoom),ih-ih/zoom)" % frames
    else:
        z, x, y = z_in, cx, cy
    return ("scale=2600:1463:force_original_aspect_ratio=increase,crop=2600:1463,"
            "zoompan=z='%s':x='%s':y='%s':d=%d:s=%dx%d:fps=%d" % (z, x, y, frames, W, H, FPS))


def caption_filter(idx, text):
    cap = "cap%d.txt" % idx
    open(os.path.join(WORK, cap), "w", encoding="utf-8", newline="\n").write(
        "\n".join(textwrap.wrap(text, width=54)[:3]))
    return ("drawbox=x=0:y=838:w=1920:h=242:color=black@0.48:t=fill,"
            "drawtext=fontfile=font.ttf:textfile=%s:fontcolor=white:fontsize=44:line_spacing=10:"
            "x=(w-text_w)/2:y=888:borderw=5:bordercolor=black@0.9" % cap)


# ---------------- animated MAP (真 frame animation) ----------------
def render_map(idx, spec, seconds, caption):
    from PIL import Image, ImageDraw, ImageFont
    base_abs = os.path.join(WORK, "mapbase%d.jpg" % idx)
    ok = fetch(spec.get("img", "antique parchment world map, muted colors, top down, no text"),
               base_abs, 1600, 900)
    if ok:
        base = Image.open(base_abs).convert("RGB").resize((2200, 1238), Image.LANCZOS)
        base = Image.blend(base, Image.new("RGB", base.size, (14, 26, 42)), 0.35)
    else:
        base = Image.new("RGB", (2200, 1238), (18, 32, 50))
    f_lab = ImageFont.truetype(FONT_PATH, 40)
    logo = Image.open(os.path.join(WORK, "logo.png")).convert("RGBA")
    logo.thumbnail((360, 360))
    # Defensive: a storyboard from a model may put a sentence here. A bad route is
    # not worth throwing away an entire rendered documentary, so draw the map
    # without the animated path instead of crashing.
    pts = spec.get("route", [])
    if not (isinstance(pts, list) and all(
            isinstance(p, (list, tuple)) and len(p) == 2
            and all(isinstance(v, (int, float)) for v in p) for p in pts)):
        pts = []
    labels = spec.get("labels", [])
    cap_lines = textwrap.wrap(caption, width=54)[:3]
    f_cap = ImageFont.truetype(FONT_PATH, 44)
    n = int(seconds * FPS)
    fdir = os.path.join(WORK, "mapf%d" % idx); os.makedirs(fdir, exist_ok=True)
    for k in range(n):
        p = k / max(1, n - 1)
        zoom = 1.0 + 0.10 * p
        cw, ch = int(2200 / zoom), int(1238 / zoom)
        ox = int((2200 - cw) * (0.5 + 0.06 * p))
        oy = int((1238 - ch) * (0.5 - 0.04 * p))
        fr = base.crop((ox, oy, ox + cw, oy + ch)).resize((W, H), Image.LANCZOS).convert("RGBA")
        d = ImageDraw.Draw(fr, "RGBA")
        if len(pts) >= 2:
            seg = p * (len(pts) - 1)
            done = int(seg); frac = seg - done
            path = [(int(px * W), int(py * H)) for px, py in pts[:done + 1]]
            if done < len(pts) - 1:
                x0, y0 = pts[done]; x1, y1 = pts[done + 1]
                path.append((int((x0 + (x1 - x0) * frac) * W), int((y0 + (y1 - y0) * frac) * H)))
            if len(path) >= 2:
                d.line(path, fill=(255, 210, 90, 235), width=9, joint="curve")
                (ax, ay), (bx, by) = path[-2], path[-1]
                ang = math.atan2(by - ay, bx - ax); L = 34
                d.polygon([(bx, by),
                           (bx - L * math.cos(ang - 0.42), by - L * math.sin(ang - 0.42)),
                           (bx - L * math.cos(ang + 0.42), by - L * math.sin(ang + 0.42))],
                          fill=(255, 225, 130, 245))
            for px, py in pts[:done + 1]:
                cxp, cyp = int(px * W), int(py * H)
                r = 11 + 4 * math.sin(k * 0.25)
                d.ellipse([cxp - r, cyp - r, cxp + r, cyp + r], fill=(255, 235, 160, 235))
        for lb in labels:
            at = lb.get("at", 0.2)
            if p >= at:
                a = int(min(1.0, (p - at) * 6) * 255)
                tx, ty = int(lb["x"] * W), int(lb["y"] * H)
                d.text((tx + 3, ty + 3), lb["t"], font=f_lab, fill=(0, 0, 0, a), anchor="mm")
                d.text((tx, ty), lb["t"], font=f_lab, fill=(255, 232, 150, a), anchor="mm")
        d.rectangle([0, 838, W, H], fill=(0, 0, 0, 122))
        for j, line in enumerate(cap_lines):
            yy = 888 + j * 56
            d.text((W // 2 + 3, yy + 3), line, font=f_cap, fill=(0, 0, 0, 230), anchor="ma")
            d.text((W // 2, yy), line, font=f_cap, fill=(255, 255, 255, 255), anchor="ma")
        fr.alpha_composite(logo, (40, 36))
        fr.convert("RGB").save(os.path.join(fdir, "%05d.jpg" % k), quality=88)
    out = "sc%d.mp4" % idx
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", "mapf%d/%%05d.jpg" % idx,
         "-i", "sc%d.wav" % idx, "-map", "0:v", "-map", "1:a",
         "-t", "%.2f" % seconds, *VENC, out])
    return out


# ---------------- shot renderers ----------------
def render_cinematic(idx, prompt, seconds, caption, move, extra=""):
    img = "sc%d.jpg" % idx
    ok = fetch(prompt, os.path.join(WORK, img))
    frames = int(seconds * FPS)
    if ok:
        vin = ["-loop", "1", "-i", img]
        chain = "[0:v]" + live_chain(move, frames, seconds, idx)
    else:
        vin = ["-f", "lavfi", "-i", "color=c=0x0E1B2A:s=%dx%d:r=%d" % (W, H, FPS)]
        chain = "[0:v]trim=duration=%.2f,setpts=PTS-STARTPTS" % seconds
    # drifting atmosphere (screen-blended) sells depth and air movement
    fog = ("[1:v]scale=2600:1463,crop=%d:%d:x='200+120*sin(2*PI*t*0.05)':y='120+60*cos(2*PI*t*0.04)',"
           "format=gbrp,colorchannelmixer=rr=0.16:gg=0.16:bb=0.17[fog];" % (W, H))
    fc = ("%s%s[base];%s[base][fog]blend=all_mode=screen,%s,%s[bg];"
          "movie=logo.png[lg];[bg][lg]overlay=40:36[v]"
          % (chain, ("," + extra) if extra else "", fog, finish_look(), caption_filter(idx, caption)))
    out = "sc%d.mp4" % idx
    run(["ffmpeg", "-y", *vin, "-loop", "1", "-i", "fog.jpg", "-i", "sc%d.wav" % idx,
         "-filter_complex", fc, "-map", "[v]", "-map", "2:a", "-t", "%.2f" % seconds, *VENC, out])
    return out


def render_document(idx, prompt, seconds, caption, highlight):
    hx, hy, hw, hh = highlight
    t0 = seconds * 0.35
    box = ("drawbox=x=%d:y=%d:w=%d:h=%d:color=0xFFD86A@0.16:t=fill:enable='gte(t,%.2f)',"
           "drawbox=x=%d:y=%d:w=%d:h=%d:color=0xFFD86A@0.95:t=6:enable='gte(t,%.2f)'"
           % (int(hx * W), int(hy * H), int(hw * W), int(hh * H), t0,
              int(hx * W), int(hy * H), int(hw * W), int(hh * H), t0))
    return render_cinematic(idx, prompt, seconds, caption, "push", box)


def render_textcard(idx, seconds, caption, big):
    open(os.path.join(WORK, "big%d.txt" % idx), "w", encoding="utf-8", newline="\n").write(
        "\n".join(textwrap.wrap(big.upper(), width=18)[:3]))
    fc = ("[0:v]trim=duration=%.2f,setpts=PTS-STARTPTS,"
          "drawtext=fontfile=font.ttf:textfile=big%d.txt:fontcolor=0xE8C878:fontsize=118:"
          "line_spacing=16:x=(w-text_w)/2:y=(h-text_h)/2-40:borderw=6:bordercolor=black@0.85:"
          "alpha='min(1,t*2.2)',%s[bg];movie=logo.png[lg];[bg][lg]overlay=40:36[v]"
          % (seconds, idx, caption_filter(idx, caption)))
    out = "sc%d.mp4" % idx
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x0B1524:s=%dx%d:r=%d" % (W, H, FPS),
         "-i", "sc%d.wav" % idx, "-filter_complex", fc,
         "-map", "[v]", "-map", "1:a", "-t", "%.2f" % seconds, *VENC, out])
    return out


def render_compare(idx, seconds, caption, left_prompt, right_prompt, left_label, right_label):
    a, b = "cmpA%d.jpg" % idx, "cmpB%d.jpg" % idx
    ok1 = fetch(left_prompt, os.path.join(WORK, a))
    ok2 = fetch(right_prompt, os.path.join(WORK, b))
    if not (ok1 and ok2):
        return render_cinematic(idx, left_prompt, seconds, caption, "push")
    frames = int(seconds * FPS)
    half = seconds * 0.5
    label_file("cmpL%d.txt" % idx, left_label)
    label_file("cmpR%d.txt" % idx, right_label)
    fc = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
          "zoompan=z='min(1.0+0.0004*on,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          "d=%d:s=%dx%d:fps=%d[L];"
          "[1:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
          "zoompan=z='max(1.12-0.0004*on,1.0)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          "d=%d:s=%dx%d:fps=%d[R];"
          "[L][R]xfade=transition=wiperight:duration=0.9:offset=%.2f[mix];"
          "[mix]drawtext=fontfile=font.ttf:textfile=cmpL%d.txt:fontcolor=white:fontsize=48:x=120:y=110:"
          "borderw=5:bordercolor=black@0.9:enable='lt(t,%.2f)',"
          "drawtext=fontfile=font.ttf:textfile=cmpR%d.txt:fontcolor=white:fontsize=48:x=w-tw-120:y=110:"
          "borderw=5:bordercolor=black@0.9:enable='gte(t,%.2f)',%s[bg];"
          "movie=logo.png[lg];[bg][lg]overlay=40:36[v]"
          % (W * 2, H * 2, W * 2, H * 2, frames, W, H, FPS,
             W * 2, H * 2, W * 2, H * 2, frames, W, H, FPS,
             half, idx, seconds * 0.55, idx, half,
             caption_filter(idx, caption)))
    out = "sc%d.mp4" % idx
    run(["ffmpeg", "-y", "-loop", "1", "-i", a, "-loop", "1", "-i", b, "-i", "sc%d.wav" % idx,
         "-filter_complex", fc, "-map", "[v]", "-map", "2:a", "-t", "%.2f" % seconds, *VENC, out])
    return out


# ---------------- storyboard analyzer ----------------
def analyze(shots):
    total = sum(s["_dur"] for s in shots)
    by = {}
    for s in shots:
        by[s["type"]] = by.get(s["type"], 0) + s["_dur"]
    longest_static = max((s["_dur"] for s in shots if s["type"] in ("cinematic", "document")),
                         default=0)
    avg_change = total / max(1, len(shots))
    still_pct = 100.0 * by.get("cinematic", 0) / total
    report = {
        "total_seconds": round(total, 1),
        "unique_shots": len(shots),
        "avg_visual_change_s": round(avg_change, 1),
        "longest_uninterrupted_static_s": round(longest_static, 1),
        "mix_pct": {k: round(100.0 * v / total, 1) for k, v in by.items()},
    }
    fails = []
    if avg_change > 9.0:
        fails.append("average shot too long (%.1fs > 9s)" % avg_change)
    if longest_static > 11.0:
        fails.append("a static shot runs %.1fs (>11s)" % longest_static)
    if len(by) < 3:
        fails.append("only %d visual types (need >=3)" % len(by))
    if still_pct > 70.0:
        fails.append("cinematic stills are %.0f%% of runtime (>70%%)" % still_pct)
    if len(shots) < max(8, total / 9):
        fails.append("too few unique shots for the runtime")
    return report, fails


# ---------------- assembly ----------------
def build_title(title, subtitle):
    open(os.path.join(WORK, "ttl.txt"), "w", encoding="utf-8", newline="\n").write(
        "\n".join(textwrap.wrap(title.upper(), width=22)[:3]))
    label_file("sub.txt", subtitle)
    d = 4.6
    fc = ("[0:v]drawtext=fontfile=font.ttf:textfile=ttl.txt:fontcolor=0xE8C878:fontsize=92:"
          "line_spacing=14:x=(w-text_w)/2:y=(h-text_h)/2+80:borderw=6:bordercolor=black@0.85:"
          "alpha='min(1,t*1.4)',"
          "drawtext=fontfile=font.ttf:textfile=sub.txt:fontcolor=0xD8D2C2:fontsize=42:"
          "x=(w-text_w)/2:y=h-190:alpha='max(0,min(1,(t-1.2)*1.4))'[t1];"
          "movie=logo.png,scale=560:-1[lg];[t1][lg]overlay=(W-w)/2:150[v]")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x0B1524:s=%dx%d:r=%d" % (W, H, FPS),
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", fc,
         "-map", "[v]", "-map", "1:a", "-t", "%.2f" % d, *VENC, "sctitle.mp4"])
    return "sctitle.mp4"


def crossfade_all(clips, xf=0.5):
    cur = clips[0]; cur_d = dur(cur)
    for i, nxt in enumerate(clips[1:], start=1):
        nd = dur(nxt); off = max(0.1, cur_d - xf)
        out = "mix%d.mp4" % i
        run(["ffmpeg", "-y", "-i", cur, "-i", nxt, "-filter_complex",
             "[0:v][1:v]xfade=transition=fade:duration=%.2f:offset=%.2f[v];"
             "[0:a][1:a]acrossfade=d=%.2f[a]" % (xf, off, xf),
             "-map", "[v]", "-map", "[a]", *VENC, out])
        cur = out; cur_d = off + nd
    return cur


def make_music(dur_s):
    notes = [130.81, 164.81, 196.00, 261.63]
    body = "+".join("(sin(2*PI*%.2f*t)+0.28*sin(2*PI*%.2f*t))" % (f, 2 * f) for f in notes)
    expr = "(0.5+0.5*sin(2*PI*t/22))*0.11*(%s)" % body
    fo = max(0.0, dur_s - 3.0)
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "aevalsrc=%s:s=48000:d=%.2f" % (expr, dur_s),
         "-af", "tremolo=f=0.1:d=0.35,aecho=0.85:0.9:1200|2200:0.3|0.2,lowpass=f=1900,"
                "highpass=f=60,afade=t=in:st=0:d=3,afade=t=out:st=%.2f:d=3" % fo,
         "-ac", "2", "-ar", "48000", "music.wav"])


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "storyboard.json")
    doc = json.load(open(src, encoding="utf-8"))
    shots = doc["shots"]

    print("== narrating %d shots ==" % len(shots), flush=True)
    for i, s in enumerate(shots):
        tts(s["say"], os.path.join(WORK, "sc%d.mp3" % i))
        run(["ffmpeg", "-y", "-i", "sc%d.mp3" % i, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
             "-ar", "48000", "-ac", "2", "sc%d.wav" % i])
        s["_dur"] = round(dur("sc%d.wav" % i) + 0.3, 2)

    report, fails = analyze(shots)
    print("== storyboard report ==\n" + json.dumps(report, indent=2), flush=True)
    if fails:
        print("!! SLIDESHOW CHECK FAILED - not rendering:", flush=True)
        for f in fails:
            print("   -", f, flush=True)
        sys.exit(2)
    print("== slideshow check PASSED ==", flush=True)

    moves = ["push", "pan_r", "pull", "tilt_d", "diag", "pan_l", "push", "tilt_u"]
    clips = [build_title(doc["title"], doc.get("subtitle", "HISTORY THAT EXPLAINS THE WORLD"))]
    for i, s in enumerate(shots):
        t = s["type"]; d = s["_dur"]
        print("shot %d/%d [%s] %.1fs" % (i + 1, len(shots), t, d), flush=True)
        if t == "map":
            clips.append(render_map(i, s, d, s["say"]))
        elif t == "document":
            clips.append(render_document(i, s["img"], d, s["say"],
                                         s.get("highlight", [0.3, 0.3, 0.4, 0.2])))
        elif t == "textcard":
            clips.append(render_textcard(i, d, s["say"], s["big"]))
        elif t == "compare":
            clips.append(render_compare(i, d, s["say"],
                                    s.get("left", s.get("img", "a scene, 16:9")),
                                    s.get("right", s.get("img", "a scene, 16:9")),
                                        s.get("left_label", "BEFORE"),
                                        s.get("right_label", "AFTER")))
        else:
            clips.append(render_cinematic(i, s["img"], d, s["say"],
                                          s.get("move", moves[i % len(moves)])))

    print("== assembling with crossfades ==", flush=True)
    body = crossfade_all(clips, 0.5)
    make_music(dur(body))
    run(["ffmpeg", "-y", "-i", body, "-i", "music.wav", "-filter_complex",
         "[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:normalize=0:duration=first,"
         "alimiter=limit=0.95[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "final_doc.mp4"])
    json.dump(report, open(os.path.join(WORK, "storyboard_report.json"), "w"), indent=2)
    print("DONE final_doc.mp4", round(dur("final_doc.mp4"), 1), "s", flush=True)


if __name__ == "__main__":
    main()
