# -*- coding: utf-8 -*-
"""Documentary thumbnail generator: one dominant image, 2-4 huge words, brand bar.
Mobile-first: readable at 168px wide."""
import sys, os, json, urllib.request, urllib.parse, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
FONT = os.path.join(ASSETS, "Anton-Regular.ttf")
W, H = 1280, 720

def fetch(prompt, dst):
    url = ("https://image.pollinations.ai/prompt/%s?width=1280&height=720&nologo=true&seed=%d&model=flux"
           % (urllib.parse.quote(prompt + ", photorealistic, cinematic, dramatic lighting, highly detailed, 8k"),
              random.randint(1, 999999)))
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            d = urllib.request.urlopen(req, timeout=100).read()
            if len(d) > 8000:
                open(dst, "wb").write(d); return True
        except Exception as e:
            print("retry", str(e)[:50])
    return False

def gradient_text(im, x, y, text, size, top=(255,240,180), bot=(235,170,40), anchor="mm", outline=10):
    f = ImageFont.truetype(FONT, size)
    m = Image.new("L", im.size, 0); md = ImageDraw.Draw(m)
    # thick dark outline for punch at small sizes
    for dx in range(-outline, outline+1, 2):
        for dy in range(-outline, outline+1, 2):
            if dx*dx+dy*dy <= outline*outline:
                md.text((x+dx, y+dy), text, font=f, fill=255, anchor=anchor)
    im.paste(Image.new("RGB", im.size, (8,10,16)), (0,0), m)
    core = Image.new("L", im.size, 0); ImageDraw.Draw(core).text((x,y), text, font=f, fill=255, anchor=anchor)
    bb = core.getbbox()
    ga = np.zeros((im.size[1], im.size[0], 3), float)
    if bb:
        y0,y1 = bb[1], bb[3]
        for yy in range(y0,y1):
            k=(yy-y0)/max(1,y1-y0); ga[yy,:,:]=np.array(top)*(1-k)+np.array(bot)*k
    im.paste(Image.fromarray(np.clip(ga,0,255).astype('uint8'),'RGB'), (0,0), core)

def build(img_prompt, line1, line2, out, badge=None):
    tmp = os.path.join(HERE, "_thumb_src.jpg")
    base = Image.open(tmp).convert("RGB").resize((W,H), Image.LANCZOS) if (fetch(img_prompt, tmp) and os.path.exists(tmp)) \
           else Image.new("RGB",(W,H),(14,27,42))
    # punch the image: contrast + saturation, darken bottom for text
    base = Image.blend(base, Image.new("RGB",(W,H),(10,16,28)), 0.18)
    grad = Image.new("L",(W,H),0); gd=ImageDraw.Draw(grad)
    for yy in range(H):
        gd.line([(0,yy),(W,yy)], fill=int(210*max(0,(yy-H*0.34)/(H*0.66))**1.4))
    base.paste(Image.new("RGB",(W,H),(6,10,18)), (0,0), grad)
    d = ImageDraw.Draw(base)
    # brand bar
    d.rectangle([0, H-56, W, H], fill=(200,162,75))
    d.text((W//2, H-28), "HISTORY THAT EXPLAINS THE WORLD",
           font=ImageFont.truetype(FONT, 30), fill=(14,22,36), anchor="mm")
    # big words
    gradient_text(base, W//2, H-235, line1.upper(), 118)
    if line2:
        gradient_text(base, W//2, H-120, line2.upper(), 118, top=(255,255,255), bot=(190,195,205))
    # curiosity badge
    if badge:
        bw = 300
        d.rounded_rectangle([W-bw-34, 30, W-34, 116], 16, fill=(200,40,40))
        d.text((W-bw//2-34, 73), badge.upper(), font=ImageFont.truetype(FONT, 44),
               fill=(255,255,255), anchor="mm")
    base.save(out, quality=95)
    print("thumbnail ->", out)

if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    build(cfg["img"], cfg["line1"], cfg.get("line2",""), sys.argv[2], cfg.get("badge"))
