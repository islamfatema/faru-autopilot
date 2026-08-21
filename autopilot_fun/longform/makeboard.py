# -*- coding: utf-8 -*-
"""Turn one topic from a channel's topic bank into a full documentary storyboard.

Before this existed the documentary workflow alternated between two hand written
files, so it re-uploaded the same two videos every week forever. That is
duplicate content, and YouTube treats it accordingly.

Now: each channel keeps a bank of topics (`topics_<key>.json`). A topic carries a
title, an angle, and the beats the episode should hit. This script picks the next
topic in rotation and expands it into the storyboard/meta/thumb trio that
docgen2.py, thumb.py and publish.py already consume.

Expansion uses Gemini when a key is available, because it writes far better
narration than a template can. If Gemini is unavailable or returns something that
fails validation, the beats are expanded deterministically instead - a shorter
episode, but a real and unique one. The run never publishes filler.

    python makeboard.py <channel_key> [out_dir]

Writes out_dir/storyboard.json, meta.json, thumb.json and prints the paths.
"""
import datetime
import json
import io
import os
import random
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# An episode should clear 8 minutes so YouTube allows mid-roll ads, which is
# where the actual money on a documentary channel comes from. At ~150 words per
# minute of narration that means 1,300 words minimum; aim past it for headroom.
MIN_WORDS = 1300
TARGET_WORDS = 1500
MIN_SHOTS = 70
MAX_SHOTS = 130

MOVES = ["push", "pull", "pan_l", "pan_r", "tilt_u", "tilt_d", "diag"]


# ---------------------------------------------------------------- topic bank
def load_topics(key):
    p = os.path.join(HERE, "topics_%s.json" % key)
    return json.load(io.open(p, encoding="utf-8"))


def pick_topic(topics, offset=0):
    """Rotate strictly by episode number so nothing repeats until the bank cycles.

    Episodes land twice a week, so counting whole weeks since a fixed epoch and
    doubling it (plus 1 for the second episode of the week) gives a stable,
    gap-free index even if a run is missed or re-run.
    """
    epoch = datetime.date(2026, 1, 5)  # a Monday
    today = datetime.date.today()
    week = (today - epoch).days // 7
    second_half = 1 if today.weekday() >= 4 else 0  # Fri/Sat/Sun -> second episode
    idx = (week * 2 + second_half + offset) % len(topics)
    return topics[idx], idx


# ---------------------------------------------------------------- gemini
def gemini(prompt, key, timeout=180):
    models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]
    last = ""
    for m in models:
        try:
            body = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 1.0, "maxOutputTokens": 32768},
            }).encode()
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   + m + ":generateContent?key=" + key)
            req = urllib.request.Request(url, data=body,
                                         headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                j = json.loads(r.read())
            parts = j["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except Exception as e:
            last = "%s: %s" % (m, str(e)[:120])
            print("  gemini %s" % last, flush=True)
    raise RuntimeError("all gemini models failed: " + last)


def build_prompt(topic):
    beats = "\n".join("  %d. %s" % (i + 1, b) for i, b in enumerate(topic["beats"]))
    return """You are writing a YouTube documentary script for a channel that explains history
and the world to a general audience. Write in clear, plain English. No filler, no
"welcome back to the channel", no asking for likes.

EPISODE TITLE: %s
ANGLE: %s

BEATS THE EPISODE MUST COVER, in order:
%s

Return ONLY a JSON array of shot objects. No markdown fence, no commentary.

Each shot object:
  "type": one of "cinematic" (most shots), "textcard" (a single big statement),
          "map" (geography), "document" (a quote, letter, ledger or inscription),
          "compare" (two things set against each other)
  "say":  one or two sentences of narration for this shot. Plain spoken English.
  "img":  a detailed image prompt for this shot, ending in ", 16:9". Describe a
          real scene with light, texture and mood. Never describe text or words
          inside the image.
  "move": one of push, pull, pan_l, pan_r, tilt_u, tilt_d, diag. Vary it - never
          use the same move more than twice in a row.

For "textcard" shots also add "big": a short punchy line of 2 to 5 words.
For "map" shots also add "route": a short description of what the map shows.
For "compare" shots also add "left_label" and "right_label".

HARD REQUIREMENTS:
- Between 90 and 120 shots.
- The narration across all shots must total at least %d words. This is the most
  important requirement: the finished episode has to run past 8 minutes.
- Open with a concrete, specific moment - a person, a date, a scene. Never open
  with a general statement about history.
- At most 50%% of shots may be "cinematic". The rest must be spread across
  textcard, map, document and compare, mixed all the way through - a run of
  cinematic stills reads as a slideshow and is automatically rejected.
- Keep every "say" to 22 words or fewer. One shot that talks for too long
  leaves a still image on screen and fails the same check. Use more, shorter
  shots instead of fewer, longer ones.
- Every "img" must be visually different from the shots around it.
- End with a sentence that lands the point, not a call to subscribe.
""" % (topic["title"], topic["angle"], beats, TARGET_WORDS)


# ---------------------------------------------------------------- validation
def parse_shots(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    i, j = t.find("["), t.rfind("]")
    if i < 0 or j < 0:
        raise ValueError("no JSON array in model output")
    return json.loads(t[i:j + 1])


def clean(shots):
    """Drop malformed shots and repair what is cheaply repairable."""
    out, last_move = [], None
    for s in shots:
        if not isinstance(s, dict):
            continue
        say = str(s.get("say") or "").strip()
        img = str(s.get("img") or "").strip()
        if not say or not img:
            continue
        typ = s.get("type") if s.get("type") in (
            "cinematic", "textcard", "map", "document", "compare") else "cinematic"
        mv = s.get("move") if s.get("move") in MOVES else None
        if mv is None or mv == last_move:
            mv = random.choice([m for m in MOVES if m != last_move])
        last_move = mv
        if not img.rstrip().endswith("16:9"):
            img = img.rstrip(" .,") + ", 16:9"
        shot = {"type": typ, "move": mv, "say": say, "img": img}
        if typ == "textcard":
            shot["big"] = str(s.get("big") or " ".join(say.split()[:4])).upper()
        if typ == "map":
            shot["route"] = str(s.get("route") or say)
        if typ == "compare":
            shot["left_label"] = str(s.get("left_label") or "BEFORE")
            shot["right_label"] = str(s.get("right_label") or "AFTER")
        out.extend(_split_long(shot))
    return out[:MAX_SHOTS]


# A shot's screen time is set by how long its narration takes to speak. Anything
# past ~22 words leaves one still image up for more than 11 seconds, which the
# anti-slideshow analyzer rejects outright. Split those into consecutive shots so
# the picture keeps changing.
MAX_SAY_WORDS = 22


def _split_long(shot):
    words = shot["say"].split()
    if len(words) <= MAX_SAY_WORDS:
        return [shot]
    parts, step = [], MAX_SAY_WORDS
    chunks = [words[i:i + step] for i in range(0, len(words), step)]
    if len(chunks[-1]) < 6 and len(chunks) > 1:      # avoid a stranded fragment
        chunks[-2].extend(chunks.pop())
    for n, ch in enumerate(chunks):
        s = dict(shot)
        s["say"] = " ".join(ch)
        if n:                                         # keep type/extras on the first
            s["type"] = "cinematic"
            for k in ("big", "route", "left_label", "right_label"):
                s.pop(k, None)
            s["move"] = random.choice([m for m in MOVES if m != shot.get("move")])
            s["img"] = shot["img"].replace(", 16:9", "") + ", different angle, 16:9"
        parts.append(s)
    return parts


def words_of(shots):
    return sum(len(s["say"].split()) for s in shots)


def validate(shots):
    problems = []
    if len(shots) < MIN_SHOTS:
        problems.append("only %d shots (need %d)" % (len(shots), MIN_SHOTS))
    w = words_of(shots)
    if w < MIN_WORDS:
        problems.append("only %d narration words (need %d for 8+ minutes)" % (w, MIN_WORDS))
    kinds = set(s["type"] for s in shots)
    if len(kinds) < 3:
        problems.append("only %d shot types, the result would look like a slideshow" % len(kinds))
    return problems


# ---------------------------------------------------------------- fallback
def from_beats(topic):
    """No AI: expand the hand written beats into a real, unique episode.

    Shorter than the AI version, but it is genuine content for this topic rather
    than a repeat of last week's video.
    """
    shots = []
    last = None
    for n, beat in enumerate(topic["beats"]):
        sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", beat) if x.strip()]
        for k, sent in enumerate(sentences):
            mv = random.choice([m for m in MOVES if m != last])
            last = mv
            typ = "textcard" if (k == 0 and n % 3 == 0) else "cinematic"
            shot = {
                "type": typ, "move": mv, "say": sent,
                "img": "%s, %s, cinematic documentary lighting, 16:9" % (
                    topic.get("look", "a historical scene"), sent[:90]),
            }
            if typ == "textcard":
                shot["big"] = " ".join(sent.split()[:4]).upper()
            shots.append(shot)
    return shots


# ---------------------------------------------------------------- outputs
def chapters(shots, total_words):
    """Rough chapter marks so the description carries a timeline."""
    out, running, mark = [], 0, 0
    step = max(1, len(shots) // 6)
    for i in range(0, len(shots), step):
        secs = int(running / 150.0 * 60)
        out.append("%d:%02d %s" % (secs // 60, secs % 60,
                                   " ".join(shots[i]["say"].split()[:6])))
        running += sum(len(s["say"].split()) for s in shots[i:i + step])
        mark += 1
        if mark >= 7:
            break
    return "\n".join(out)


def write_all(topic, shots, out_dir):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    sb = {"title": topic["title"], "subtitle": topic.get("angle", ""), "shots": shots}
    total = words_of(shots)
    desc = (topic.get("blurb") or topic["angle"]) + "\n\n" + chapters(shots, total) + \
        "\n\nNew documentaries twice a week.\n\n#history #documentary #education"
    meta = {
        "title": topic["title"],
        "description": desc,
        "tags": topic.get("tags", ["history", "documentary", "education", "explained"]),
    }
    thumb = {
        "img": topic.get("thumb_img", topic.get("look", "a dramatic historical scene")
               + ", epic cinematic, 16:9"),
        "line1": topic.get("line1", topic["title"].split()[0]),
        "line2": topic.get("line2", " ".join(topic["title"].split()[1:3])),
        "badge": topic.get("badge", "TRUE"),
    }
    paths = {}
    for name, obj in (("storyboard.json", sb), ("meta.json", meta), ("thumb.json", thumb)):
        p = os.path.join(out_dir, name)
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(obj, ensure_ascii=False, indent=1))
        paths[name] = p
    return paths, total


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "history"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "_board")

    topics = load_topics(key)
    topic, idx = pick_topic(topics)
    print("episode %d/%d: %s" % (idx + 1, len(topics), topic["title"]), flush=True)

    gkey = (os.environ.get("OWNER_GEMINI_KEY") or "").strip()
    shots = []
    if gkey:
        for attempt in range(2):
            try:
                raw = gemini(build_prompt(topic), gkey)
                cand = clean(parse_shots(raw))
                bad = validate(cand)
                if not bad:
                    shots = cand
                    break
                print("  attempt %d rejected: %s" % (attempt + 1, "; ".join(bad)), flush=True)
            except Exception as e:
                print("  attempt %d failed: %s" % (attempt + 1, str(e)[:160]), flush=True)
    else:
        print("  no OWNER_GEMINI_KEY, using the hand written beats", flush=True)

    if not shots:
        shots = clean(from_beats(topic))
        print("  fell back to beats: %d shots, %d words" % (len(shots), words_of(shots)), flush=True)

    paths, total = write_all(topic, shots, out_dir)
    mins = total / 150.0
    print("shots %d | words %d | about %.1f minutes" % (len(shots), total, mins), flush=True)
    for k, v in paths.items():
        print("  %s -> %s" % (k, v), flush=True)

    # Publishing a two minute clip titled like a documentary is worse for the
    # channel than publishing nothing, so stop the run instead. A visible failure
    # can be retried; a bad upload cannot be taken back.
    floor = float(os.environ.get("MIN_MINUTES", "5"))
    if mins < floor:
        print("REFUSING to publish: %.1f min is below the %.1f min floor. "
              "Fix the generator or the topic, then re-run." % (mins, floor), flush=True)
        sys.exit(3)
    if mins < 8:
        print("NOTE: under 8 minutes, so no mid-roll ads on this one", flush=True)


if __name__ == "__main__":
    main()
