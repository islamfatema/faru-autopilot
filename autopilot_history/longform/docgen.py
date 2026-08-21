# -*- coding: utf-8 -*-
"""
History That Explains the World - free long-form documentary generator (16:9).
Per-scene cinematic Ken Burns clip + narration (edge-tts) + wrapped captions +
gold-globe watermark, concatenated, with a title card and a soft music bed.
Human approval gate: review the output before it is ever uploaded.

Usage:  python docgen.py pilot.json     ->  _work/final_doc.mp4
"""
import os, sys, json, subprocess, asyncio, time, random, urllib.request, urllib.parse, textwrap, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
WORK = os.path.join(HERE, "_work"); os.makedirs(WORK, exist_ok=True)
W, H = 1920, 1080
VOICE = "en-US-ChristopherNeural"
# assets copied into WORK so ffmpeg can use bare filenames (no Windows drive-colon escaping)
shutil.copy(os.path.join(ASSETS, "Anton-Regular.ttf"), os.path.join(WORK, "font.ttf"))
shutil.copy(os.path.join(ASSETS, "logo.png"), os.path.join(WORK, "logo.png"))

def run(args):
    p = subprocess.run(args, capture_output=True, text=True, cwd=WORK)
    if p.returncode != 0:
        print("CMD FAIL:", " ".join(str(a) for a in args[:6])); print((p.stderr or "")[-1600:]); sys.exit(1)
    return p

def dur(path):
    p = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration","-of","json",
                        os.path.join(WORK, path)], capture_output=True, text=True)
    return float(json.loads(p.stdout)["format"]["duration"])

async def _tts(text, out):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate="-6%").save(out)

def tts(text, out_abs):
    for a in range(6):
        try:
            asyncio.run(_tts(text, out_abs))
            if os.path.getsize(out_abs) > 1500: return
        except Exception as e:
            print("tts retry", a, str(e)[:70]); time.sleep(4)
    raise RuntimeError("edge-tts failed")

def get_image(prompt, dst_abs):
    url = ("https://image.pollinations.ai/prompt/%s?width=1280&height=720&nologo=true&seed=%d&model=flux"
           % (urllib.parse.quote(prompt), random.randint(1, 999999)))
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            if len(data) > 8000:
                open(dst_abs, "wb").write(data); return True
        except Exception as e:
            print("img retry", str(e)[:70]); time.sleep(3)
    return False

VENC = ["-r","30","-c:v","libx264","-pix_fmt","yuv420p","-preset","medium","-crf","20",
        "-c:a","aac","-b:a","192k","-ar","48000","-ac","2"]

def build_scene(i, text, img_prompt):
    tts(text, os.path.join(WORK, "sc%d.mp3" % i))
    run(["ffmpeg","-y","-i","sc%d.mp3"%i,"-af","loudnorm=I=-16:TP=-1.5:LRA=11","-ar","48000","-ac","2","sc%d.wav"%i])
    d = dur("sc%d.wav" % i) + 0.35
    ok = get_image(img_prompt, os.path.join(WORK, "sc%d.jpg" % i))
    open(os.path.join(WORK,"cap%d.txt"%i),"w",encoding="utf-8",newline="\n").write(
        "\n".join(textwrap.wrap(text, width=52)[:4]))
    frames = int(d * 30)
    if ok:
        vin = ["-loop","1","-i","sc%d.jpg"%i]
        base = ("[0:v]scale=2400:1350:force_original_aspect_ratio=increase,crop=2400:1350,"
                "zoompan=z='min(1.0+0.00035*on,1.14)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                "d=%d:s=1920x1080:fps=30[bg];" % frames)
    else:
        vin = ["-f","lavfi","-i","color=c=0x0E1B2A:s=1920x1080:r=30"]
        base = "[0:v]trim=duration=%.2f,setpts=PTS-STARTPTS[bg];" % d
    fc = (base +
          "[bg]drawbox=x=0:y=815:w=1920:h=265:color=black@0.45:t=fill,"
          "drawtext=fontfile=font.ttf:textfile=cap%d.txt:fontcolor=white:fontsize=46:line_spacing=10:"
          "x=(w-text_w)/2:y=875:borderw=5:bordercolor=black@0.9[tx];"
          "movie=logo.png[lg];[tx][lg]overlay=40:36[v]" % i)
    run(["ffmpeg","-y",*vin,"-i","sc%d.wav"%i,"-filter_complex",fc,"-map","[v]","-map","1:a","-t","%.2f"%d,*VENC,"sc%d.mp4"%i])
    return "sc%d.mp4" % i

def build_title(title):
    open(os.path.join(WORK,"captitle.txt"),"w",encoding="utf-8",newline="\n").write(
        "\n".join(textwrap.wrap(title.upper(), width=22)[:3]))
    d=4.5
    fc=("[0:v]drawtext=fontfile=font.ttf:textfile=captitle.txt:fontcolor=0xE6C878:fontsize=92:line_spacing=14:"
        "x=(w-text_w)/2:y=(h-text_h)/2+70:borderw=6:bordercolor=black@0.85[t1];"
        "movie=logo.png,scale=520:-1[lg];[t1][lg]overlay=(W-w)/2:190[v]")
    run(["ffmpeg","-y","-f","lavfi","-i","color=c=0x0E1B2A:s=1920x1080:r=30",
         "-f","lavfi","-i","anullsrc=r=48000:cl=stereo","-filter_complex",fc,
         "-map","[v]","-map","1:a","-t","%.2f"%d,*VENC,"sctitle.mp4"])
    return "sctitle.mp4"

def make_music(dur_s):
    notes=[130.81,164.81,196.00,261.63]
    body="+".join("(sin(2*PI*%.2f*t)+0.28*sin(2*PI*%.2f*t))"%(f,2*f) for f in notes)
    expr="(0.5+0.5*sin(2*PI*t/22))*0.11*(%s)"%body; fo=max(0.0,dur_s-3.0)
    run(["ffmpeg","-y","-f","lavfi","-i","aevalsrc=%s:s=48000:d=%.2f"%(expr,dur_s),
         "-af","tremolo=f=0.1:d=0.35,aecho=0.85:0.9:1200|2200:0.3|0.2,lowpass=f=1900,highpass=f=60,"
               "afade=t=in:st=0:d=3,afade=t=out:st=%.2f:d=3"%fo,"-ac","2","-ar","48000","music.wav"])

def main():
    src = sys.argv[1] if len(sys.argv)>1 else os.path.join(HERE,"pilot.json")
    doc = json.load(open(src, encoding="utf-8"))
    clips=[build_title(doc["title"])]
    for i,sc in enumerate(doc["scenes"]):
        print("scene %d/%d"%(i+1,len(doc["scenes"])),flush=True)
        clips.append(build_scene(i, sc["t"], sc["img"]))
    open(os.path.join(WORK,"concat.txt"),"w").write("\n".join("file '%s'"%c for c in clips))
    run(["ffmpeg","-y","-f","concat","-safe","0","-i","concat.txt",*VENC,"body.mp4"])
    make_music(dur("body.mp4"))
    run(["ffmpeg","-y","-i","body.mp4","-i","music.wav","-filter_complex",
         "[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]",
         "-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","final_doc.mp4"])
    print("DONE final_doc.mp4", round(dur("final_doc.mp4"),1),"s",flush=True)

if __name__=="__main__":
    main()
