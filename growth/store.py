# -*- coding: utf-8 -*-
"""Where every video's real numbers are kept, over time.

Everything this project measured until now was a snapshot: a report printed,
read once, and thrown away. A snapshot cannot answer the only questions that
matter - is this video doing better or worse than the channel's normal, and is
the channel's normal moving - so every decision about what to make next was
made from memory.

This is the memory. One file per channel, one record per video, and a dated
snapshot appended each time the collector runs:

    analytics/videos_fun.json
      videos:
        dQw4w9WgXcQ:
          title, published, duration_s, kind (short|long), series, tags
          snapshots: [{date, window_days, views, watch_minutes, avd_s, avg_pct,
                       subs_gained, subs_lost, likes, comments, shares,
                       playlist_adds, impressions, ctr, traffic{}, subscribed{},
                       first3_ratio}]

`impressions` and `ctr` are stored as null on purpose. YouTube's public
Analytics API does not expose thumbnail impressions or click-through rate -
they exist only inside Studio - and a growth system that invents them is worse
than one that admits it cannot separate "nobody was shown this" from "everybody
scrolled past it". Every other field here is measured.
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "analytics")

# The metrics this project can actually read, and the ones it cannot.
MEASURED = ("views", "watch_minutes", "avd_s", "avg_pct", "subs_gained",
            "subs_lost", "likes", "comments", "shares", "playlist_adds")
UNAVAILABLE = ("impressions", "ctr")      # Studio only - never guessed here


def path(key):
    return os.path.join(DIR, "videos_%s.json" % key)


def load(key):
    try:
        return json.load(io.open(path(key), encoding="utf-8"))
    except Exception:
        return {"channel": None, "updated": None, "videos": {}}


def save(key, data):
    os.makedirs(DIR, exist_ok=True)
    tmp = path(key) + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True))
    os.replace(tmp, path(key))


def upsert(data, vid, fields):
    """Create or update the stable part of a video's record."""
    rec = data["videos"].setdefault(vid, {"snapshots": []})
    for k, v in fields.items():
        if v is not None:
            rec[k] = v
    return rec


def add_snapshot(rec, snap):
    """Append today's numbers, replacing an existing snapshot for the same day.

    Re-running the collector twice in a day must not double the history, or
    every average computed from it drifts.
    """
    snaps = rec.setdefault("snapshots", [])
    for i, s in enumerate(snaps):
        if s.get("date") == snap.get("date") and s.get("window_days") == snap.get("window_days"):
            snaps[i] = snap
            return
    snaps.append(snap)
    snaps.sort(key=lambda s: (s.get("date") or "", s.get("window_days") or 0))


def latest(rec, window_days=None):
    """The newest snapshot, optionally for one measurement window."""
    snaps = [s for s in (rec.get("snapshots") or [])
             if window_days is None or s.get("window_days") == window_days]
    return snaps[-1] if snaps else None


def per_1k(snap, field):
    """Rate per thousand views - the only way to compare a 60-view Short with
    a 900-view one."""
    v = (snap or {}).get("views") or 0
    if not v:
        return None
    n = (snap or {}).get(field)
    if n is None:
        return None
    return round(n * 1000.0 / v, 2)
