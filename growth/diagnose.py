# -*- coding: utf-8 -*-
"""Say why each video did what it did, against this channel's own baseline.

    python growth/diagnose.py --key fun

A video is never judged against another channel or against an idea of what
YouTube "should" do. It is judged against the median of this channel's own
recent videos of the same kind, because that is the only comparison that tells
Fatema anything: 300 views is a failure on History and a win on FaRu.

The verdicts, in the order they are tested, and what each one means the next
video must change:

  NOT_ENOUGH_DATA   too new or too few views to judge. Judging it anyway is how
                    a working format gets killed on day one.
  WINNER            beat the baseline on views, on subscribers per thousand, or
                    on percent viewed. Scale the principle, not the video.
  NO_DISTRIBUTION   held people who saw it, but almost nobody saw it. The video
                    is fine; the topic or the title did not earn a feed.
  WEAK_HOOK         they arrived and left. Measured at three seconds where the
                    retention curve is available, otherwise from percent viewed.
  WEAK_SUBSCRIBE    plenty of views, almost no subscribers. The channel promise
                    is not landing, or the video never gave a reason to return.
  WEAK_COMMENTS     plenty of views, no argument. The question was generic.
  WEAK_SHARES       plenty of views, nobody sent it on. Nothing in it was worth
                    forwarding to a specific person.
  OK                inside the normal range.

Impressions and click-through rate are not in YouTube's public API, so this
never claims to separate "not shown" from "shown and not clicked". Where that
distinction would change the action, the verdict says which data would settle
it instead of pretending.
"""
import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import store  # noqa: E402

MIN_AGE_DAYS = 3
MIN_VIEWS = 20
RECENT_DAYS = 90

ACTIONS = {
    "WINNER": "scale the principle: same hook shape and length, a new subject in "
              "the same family; and make a long-form on this subject",
    "NO_DISTRIBUTION": "the content held - change what it is about or what it is "
                       "called: pick the next topic from measured search demand, "
                       "and put the surprise in the title",
    "WEAK_HOOK": "rewrite the first three seconds: open on the strangest image and "
                 "the claim, no run-up, and cut the first sentence entirely",
    "WEAK_SUBSCRIBE": "make the promise explicit: name the series and the next "
                      "episode, and keep the subject on what this channel converts on",
    "WEAK_COMMENTS": "replace the closing question with one only this video's "
                     "subject could ask - something a viewer can answer from their "
                     "own life",
    "WEAK_SHARES": "give it a person to be sent to, or a use: 'send this to whoever "
                   "taught you X'; surprise and usefulness travel, statements do not",
    "OK": "nothing specific - keep it in rotation",
    "NOT_ENOUGH_DATA": "wait",
}


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def age_days(published):
    try:
        t = datetime.strptime(published[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return 999
    return (datetime.now(timezone.utc) - t).days


def rates(snap):
    return {
        "views": snap.get("views") or 0,
        "avg_pct": snap.get("avg_pct"),
        "avd_s": snap.get("avd_s"),
        "first3": snap.get("first3_ratio"),
        "subs_per_1k": store.per_1k(snap, "subs_gained"),
        "comments_per_1k": store.per_1k(snap, "comments"),
        "shares_per_1k": store.per_1k(snap, "shares"),
        "likes_per_1k": store.per_1k(snap, "likes"),
        "watch_minutes": snap.get("watch_minutes") or 0,
    }


def traffic_share(snap, source):
    t = snap.get("traffic") or {}
    total = sum(t.values()) or 0
    if not total:
        return None
    return round((t.get(source) or 0) / float(total), 3)


def returning_share(snap):
    """Views from people already subscribed - the closest measure of return."""
    s = snap.get("subscribed") or {}
    total = sum(s.values()) or 0
    if not total:
        return None
    return round((s.get("SUBSCRIBED") or 0) / float(total), 3)


def baselines(rows, kind):
    mine = [r for r in rows if r["kind"] == kind and r["judgeable"]]
    if len(mine) < 4:
        return None
    return {
        "n": len(mine),
        "views": median([r["m"]["views"] for r in mine]),
        "avg_pct": median([r["m"]["avg_pct"] for r in mine]),
        "subs_per_1k": median([r["m"]["subs_per_1k"] for r in mine]),
        "comments_per_1k": median([r["m"]["comments_per_1k"] for r in mine]),
        "shares_per_1k": median([r["m"]["shares_per_1k"] for r in mine]),
        "first3": median([r["m"]["first3"] for r in mine]),
    }


def verdict(m, base):
    """One video against the baseline of its own kind on its own channel."""
    if not base:
        return "NOT_ENOUGH_DATA", "this channel has too few comparable videos yet"

    bv = base["views"] or 0
    bp = base["avg_pct"] or 0
    bs = base["subs_per_1k"] or 0
    bc = base["comments_per_1k"] or 0
    bsh = base["shares_per_1k"] or 0

    won = []
    if bv and m["views"] >= 2 * bv:
        won.append("views %d vs %g median" % (m["views"], bv))
    if bs and (m["subs_per_1k"] or 0) >= 2 * bs and (m["views"] or 0) >= 100:
        won.append("%.1f subs/1k vs %.1f median" % (m["subs_per_1k"], bs))
    if bp and (m["avg_pct"] or 0) >= 1.25 * bp:
        won.append("%.0f%% viewed vs %.0f%% median" % (m["avg_pct"], bp))
    if won:
        return "WINNER", "; ".join(won)

    if bv and m["views"] <= 0.5 * bv and bp and (m["avg_pct"] or 0) >= bp:
        return ("NO_DISTRIBUTION",
                "%d views against a %g median while holding %.0f%% - the video "
                "worked and the feed never arrived (impressions and CTR are "
                "Studio-only, so a screenshot would settle title vs topic)"
                % (m["views"], bv, m["avg_pct"]))

    if m["first3"] is not None and m["first3"] < 0.60:
        return "WEAK_HOOK", "only %.0f%% were still there at three seconds" % (m["first3"] * 100)
    if bp and (m["avg_pct"] or 0) <= 0.75 * bp:
        return "WEAK_HOOK", "%.0f%% viewed against a %.0f%% median" % (m["avg_pct"] or 0, bp)

    if bv and m["views"] >= bv:
        if bs and (m["subs_per_1k"] or 0) < 0.5 * bs:
            return ("WEAK_SUBSCRIBE",
                    "%d views but %.1f subs/1k against a %.1f median"
                    % (m["views"], m["subs_per_1k"] or 0, bs))
        if bc and (m["comments_per_1k"] or 0) < 0.5 * bc:
            return ("WEAK_COMMENTS",
                    "%d views but %.1f comments/1k against a %.1f median"
                    % (m["views"], m["comments_per_1k"] or 0, bc))
        if bsh and (m["shares_per_1k"] or 0) < 0.5 * bsh:
            return ("WEAK_SHARES",
                    "%d views but %.1f shares/1k against a %.1f median"
                    % (m["views"], m["shares_per_1k"] or 0, bsh))
    return "OK", "inside the normal range"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=["fun", "us", "history"])
    ap.add_argument("--window", type=int, default=28)
    a = ap.parse_args()

    data = store.load(a.key)
    if not data.get("videos"):
        raise SystemExit("no data yet - run growth/collect.py first")

    rows = []
    for vid, rec in data["videos"].items():
        snap = store.latest(rec, a.window) or store.latest(rec)
        if not snap:
            continue
        age = age_days(rec.get("published") or "")
        m = rates(snap)
        rows.append({
            "id": vid, "title": rec.get("title") or "", "kind": rec.get("kind") or "short",
            "age_days": age, "published": rec.get("published"),
            "tags": rec.get("tags") or [], "m": m,
            "shorts_feed_share": traffic_share(snap, "SHORTS"),
            "search_share": traffic_share(snap, "YT_SEARCH"),
            "suggested_share": traffic_share(snap, "RELATED_VIDEO"),
            "browse_share": traffic_share(snap, "BROWSE"),
            "returning_share": returning_share(snap),
            "judgeable": age >= MIN_AGE_DAYS and age <= RECENT_DAYS and m["views"] >= MIN_VIEWS,
        })

    base = {"short": baselines(rows, "short"), "long": baselines(rows, "long")}

    out = []
    for r in rows:
        if not r["judgeable"]:
            v, why = ("NOT_ENOUGH_DATA",
                      "%d views at %d days old" % (r["m"]["views"], r["age_days"]))
        else:
            v, why = verdict(r["m"], base[r["kind"]])
        out.append(dict(r, verdict=v, why=why, action=ACTIONS[v]))

    out.sort(key=lambda r: (r["published"] or ""), reverse=True)

    # Recovery: is the channel's recent work worse than its own recent normal?
    recent = [r for r in out if r["judgeable"] and r["kind"] == "short"][:10]
    older = [r for r in out if r["judgeable"] and r["kind"] == "short"][10:40]
    rec_med, old_med = median([r["m"]["views"] for r in recent]), median([r["m"]["views"] for r in older])
    recovery = bool(rec_med and old_med and rec_med < 0.6 * old_med)

    counts = {}
    for r in out:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    report = {
        "channel": data.get("channel"), "key": a.key,
        "generated": data.get("updated"),
        "window_days": a.window,
        "subscribers": data.get("subscribers"),
        "baselines": base,
        "counts": counts,
        "recovery_mode": recovery,
        "recent_median_views": rec_med,
        "previous_median_views": old_med,
        "videos": out,
        "note": ("impressions and click-through rate are not exposed by the "
                 "YouTube Analytics API; they are recorded as null and never "
                 "estimated"),
    }
    p = os.path.join(store.DIR, "diagnosis_%s.json" % a.key)
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(report, ensure_ascii=False, indent=1))

    print("%s: %s" % (data.get("channel"), ", ".join(
        "%s %d" % (k, v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))), flush=True)
    for kind in ("short", "long"):
        b = base[kind]
        if b:
            print("  baseline %-5s n=%-3d views %-6g pct %-5s subs/1k %-5s comments/1k %-4s shares/1k %s"
                  % (kind, b["n"], b["views"], b["avg_pct"], b["subs_per_1k"],
                     b["comments_per_1k"], b["shares_per_1k"]), flush=True)
    if recovery:
        print("  RECOVERY MODE: recent median %g views against %g before"
              % (rec_med, old_med), flush=True)
    for r in out[:12]:
        print("  %-16s %-46s %s" % (r["verdict"], r["title"][:46], r["why"][:70]), flush=True)
    print("wrote analytics/diagnosis_%s.json" % a.key, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
