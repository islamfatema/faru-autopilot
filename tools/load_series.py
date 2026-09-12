# -*- coding: utf-8 -*-
"""Load the week-one series into the three script banks.

The 42 episodes live in tools/series/{faru,rise,history}.py exactly as they are
written on the production board: the checked claim, its sources, the shot list
and the line that names the next episode. This turns each one into the bank
entry the posting machine reads, and marks it "series" so patch_series.py's
rules apply - the short, deliberate length is allowed, the machine adds no
canned ending, and each shot gets its own image.

    python tools/load_series.py            # write into the banks
    python tools/load_series.py --dry      # show what would change

Running it twice changes nothing: an episode already in the bank is left alone.
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "series"))

import faru, rise, history  # noqa: E402

CH = {
    "fun": ("autopilot_fun/scripts_fun.json", "Facts That Sound Fake", faru.SHORTS,
            "autopilot_fun/published_fun.json"),
    "us": ("autopilot_us/scripts_us.json", "Your Mind, Measured", rise.SHORTS,
           "autopilot_us/published_us.json"),
    "history": ("autopilot_history/scripts_history.json", "Older Than You Think", history.SHORTS,
                "autopilot_history/published_history.json"),
}

MAX_WORDS = 11      # a caption line the renderer can fit and a voice can say


def norm_title(t):
    return " ".join(re.sub(r"#\w+", " ", (t or "")).lower().split())


def captions(text):
    """Split a spoken block into caption-sized lines at natural breaks."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        sent = sent.strip()
        if not sent:
            continue
        if len(sent.split()) <= MAX_WORDS:
            out.append(sent)
            continue
        # too long to sit on screen at once: break at a comma, colon or dash
        part, buf = [], []
        for chunk in re.split(r"(?<=[,:;-])\s+", sent):
            if len(" ".join(buf + [chunk]).split()) > MAX_WORDS and buf:
                part.append(" ".join(buf))
                buf = [chunk]
            else:
                buf.append(chunk)
        if buf:
            part.append(" ".join(buf))
        # still too long (one clause of 12+ words): break on word count
        for p in part:
            w = p.split()
            while len(w) > MAX_WORDS:
                out.append(" ".join(w[:MAX_WORDS]))
                w = w[MAX_WORDS:]
            if w:
                out.append(" ".join(w))
    return out


def spoken(cta):
    """'#2: Rome had...' is read aloud as a hash. Say the number instead."""
    return re.sub(r"#(\d+)", r"number \1", cta)


def entry(series, d):
    lines = []
    for _, text in d["script"]:
        lines += captions(text)
    lines += captions(spoken(d["cta"]))
    src = "\n".join("- %s%s" % (name, " - " + url if url else "")
                    for name, url in d["sources"])
    tags = [t.lower().lstrip("#") for t in d["tags"]]
    title = d["title"]
    extra = " " + " ".join("#" + t for t in tags[:2])
    if len(title) + len(extra) <= 92:
        title += extra
    return {
        "title": title,
        "tags": list(dict.fromkeys(tags + ["shorts"])),
        "img": d["shots"][0]["prompt"],
        "imgs": [s["prompt"] for s in d["shots"]],
        "narration": " ".join(text for _, text in d["script"]),
        "phrases": lines,
        "desc": d["desc"] + "\n\nSources:\n" + src,
        "series": "%s #%d" % (series, d["n"]),
        "series_n": d["n"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--resync", action="store_true",
                    help="rewrite the shot prompts and description of episodes "
                         "already in the bank from the series file")
    a = ap.parse_args()

    if a.resync:
        for key, (rel, series, shorts, _pub) in CH.items():
            path = os.path.join(ROOT, rel)
            bank = json.load(io.open(path, encoding="utf-8"))
            by_n = dict((d["n"], d) for d in shorts)
            changed = 0
            for e in bank:
                if not e.get("series", "").startswith(series):
                    continue
                d = by_n.get(e.get("series_n"))
                if not d:
                    continue
                fresh = entry(series, d)
                for k in ("img", "imgs", "desc"):
                    if e.get(k) != fresh[k]:
                        e[k] = fresh[k]
                        changed = changed + 1
            print("%-8s %d fields refreshed" % (key, changed))
            if changed and not a.dry:
                io.open(path, "w", encoding="utf-8", newline="\n").write(
                    json.dumps(bank, ensure_ascii=False, indent=1))
        return 0

    for key, (rel, series, shorts, pubrel) in CH.items():
        path = os.path.join(ROOT, rel)
        bank = json.load(io.open(path, encoding="utf-8"))
        have = set(norm_title(d["title"]) for d in bank)
        try:
            published = set(norm_title(t) for t in
                            json.load(io.open(os.path.join(ROOT, pubrel), encoding="utf-8")))
        except Exception:
            published = set()

        added, skipped, clash = [], 0, []
        for d in shorts:
            e = entry(series, d)
            n = norm_title(e["title"])
            if n in have:
                skipped += 1
                continue
            if n in published:
                clash.append(e["title"])
                continue
            words = sum(len(p.split()) for p in e["phrases"])
            if len(e["phrases"]) < 6 or words < 50:
                raise SystemExit("%s #%d too short for the series floor: %d captions, %d words"
                                 % (key, d["n"], len(e["phrases"]), words))
            added.append(e)
            have.add(n)

        print("%-8s %2d new, %d already in bank, %d already published"
              % (key, len(added), skipped, len(clash)))
        for e in added:
            print("   %2d  %-58s %2d captions %3d words"
                  % (e["series_n"], e["title"][:58],
                     len(e["phrases"]), sum(len(p.split()) for p in e["phrases"])))
        for t in clash:
            print("   !! already on the channel, not loaded: %s" % t)

        if added and not a.dry:
            bank = added + bank
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                json.dumps(bank, ensure_ascii=False, indent=1))
            print("   wrote %s (%d scripts)" % (rel, len(bank)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
