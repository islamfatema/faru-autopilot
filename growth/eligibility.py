# -*- coding: utf-8 -*-
"""Every monetisation requirement, checked, not assumed.

Hitting the numbers only makes a channel eligible to *apply*. The application
is then reviewed against a checklist, and several items on it have nothing to
do with views - they are settings that are either right or wrong today, and a
channel can sit at the threshold for a month before anybody notices one of
them is wrong.

Verified 2026-10-14 against support.google.com/youtube/answer/72851 and
answer/13429240:

  Expanded YPP - fan funding and Shopping, no ad revenue, and the nearer gate:
      500 subscribers
      3 valid public uploads in the last 90 days
      EITHER 3,000 public long-form watch hours in 365 days
      OR     3 million qualified Shorts views in 90 days

  Full YPP - ad revenue:
      1,000 subscribers
      EITHER 4,000 long-form watch hours in 365 days
      OR     10 million qualified Shorts views in 90 days

  Both also need: monetisation policies followed, a supported country,
  no active Community Guidelines strikes, 2-Step Verification on the Google
  account, access to advanced features, and a linked AdSense account.

Shorts watch time does not count toward the watch-hour thresholds, and the two
routes never combine. From 1 February 2027 the ad-revenue bar rises for new
applicants; the fan-funding thresholds do not change.

What this can check from the API: subscribers, the three uploads, long-form
watch hours split from Shorts, Shorts views, whether the channel is flagged as
made for kids - which would cap monetisation whatever else is true - and
whether advanced features are on, which longUploadsStatus reveals. What it
cannot see is strikes, 2-Step Verification and AdSense, so it lists those as
things for Fatema to confirm rather than quietly passing them.

    python growth/eligibility.py --key history
"""
import argparse
import io
import json
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import yt      # noqa: E402

TIERS = (
    ("Fan funding (expanded YPP)", 500, 3000, 3000000),
    ("Ad revenue (full YPP)", 1000, 4000, 10000000),
)
BY_HAND = (
    "no active Community Guidelines strikes (they expire after 90 days)",
    "ONE AdSense account, with all three channels linked to it. The three "
    "channels sit under three different Google accounts, and Google matches "
    "duplicates on payee name and address - so an AdSense account per channel "
    "is a duplicate, and a duplicate turns monetisation off. See "
    "docs/adsense-setup.md",
)
DONE_BY_HAND = (
    "2-Step Verification on all three Google accounts (confirmed 2026-10-14)",
)


def longform_hours(tok, days):
    """Public long-form watch hours. Shorts do not count toward the threshold."""
    end = date.today()
    try:
        r = yt.report(tok, (end - timedelta(days=days)).isoformat(), end.isoformat(),
                      ["estimatedMinutesWatched"], dimensions=["creatorContentType"])
    except Exception as e:
        print("  could not split watch time: %s" % str(e)[:100])
        return None
    mins, seen = 0.0, False
    for row in yt.as_rows(r):
        kind = str(row.get("creatorContentType") or "").lower()
        if kind in ("videoondemand", "livestream"):
            mins += float(row.get("estimatedMinutesWatched") or 0)
        if kind in ("videoondemand", "livestream", "shorts"):
            seen = True
    return round(mins / 60.0, 1) if seen else None


def channel_status(tok):
    """madeForKids and longUploadsStatus - two settings that silently decide a lot."""
    try:
        j = yt.get(yt.DATA_API + "/channels?part=status,contentDetails&mine=true", tok)
        return (j.get("items") or [{}])[0].get("status") or {}
    except Exception as e:
        print("  could not read channel status: %s" % str(e)[:100])
        return {}


def recent_uploads(key, days=90):
    cut = (date.today() - timedelta(days=days)).isoformat()
    try:
        vids = json.load(io.open(os.path.join(ROOT, "analytics", "videos_%s.json" % key),
                                 encoding="utf-8"))["videos"]
    except Exception:
        return 0
    return sum(1 for v in vids.values() if (v.get("published") or "")[:10] >= cut)


def shorts_views_90(key):
    cut = (date.today() - timedelta(days=90)).isoformat()
    try:
        vids = json.load(io.open(os.path.join(ROOT, "analytics", "videos_%s.json" % key),
                                 encoding="utf-8"))["videos"]
    except Exception:
        return 0
    n = 0
    for v in vids.values():
        if v.get("kind") != "short" or (v.get("published") or "")[:10] < cut:
            continue
        s = v.get("snapshots") or []
        if s:
            n += s[-1].get("views") or 0
    return n


def mark(ok):
    return "MET " if ok else "no  "


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=["fun", "us", "history"])
    a = ap.parse_args()

    tok = yt.access_token()          # REFRESH_TOKEN, as the rest of growth/ does
    ch = yt.channel(tok)
    st = channel_status(tok)
    hours = longform_hours(tok, 365)
    shorts90 = shorts_views_90(a.key)
    ups = recent_uploads(a.key, 90)

    L = ["# Monetisation eligibility - %s" % ch["title"], "",
         "Checked %s against the thresholds on YouTube's own eligibility pages."
         % date.today().isoformat(), ""]
    for name, subs_need, hours_need, shorts_need in TIERS:
        L.append("## %s" % name)
        L.append("")
        L.append("    %s subscribers              %7d / %-9d" %
                 (mark(ch["subscribers"] >= subs_need), ch["subscribers"], subs_need))
        if hours is None:
            L.append("    ?    long-form watch hours    UNKNOWN - the API did not "
                     "split Shorts out this run")
        else:
            L.append("    %s long-form watch hours   %7.1f / %-9d  (365 days, "
                     "Shorts excluded)" % (mark(hours >= hours_need), hours, hours_need))
        L.append("    %s or Shorts views           %7d / %-9d  (90 days)" %
                 (mark(shorts90 >= shorts_need), shorts90, shorts_need))
        if subs_need == 500:
            L.append("    %s public uploads           %7d / 3          (90 days)" %
                     (mark(ups >= 3), ups))
        L.append("")

    L.append("## Settings, which are true or false today")
    L.append("")
    mfk = st.get("madeForKids")
    if mfk is True:
        L.append("    FAIL made for kids is ON - this caps monetisation whatever "
                 "else is true, and turns off personalised ads")
    else:
        L.append("    ok   not flagged as made for kids")
    lu = st.get("longUploadsStatus")
    if lu in ("allowed", "eligible"):
        L.append("    ok   advanced features on (long uploads: %s)" % lu)
    elif lu:
        L.append("    FAIL advanced features look off (long uploads: %s) - verify "
                 "the account by phone in Studio" % lu)
    L.append("")
    L.append("## Not visible to the API - confirm these in Studio")
    L.append("")
    for item in DONE_BY_HAND:
        L.append("    [x] %s" % item)
    for item in BY_HAND:
        L.append("    [ ] %s" % item)
    L.append("")
    L.append("From 1 February 2027 the ad-revenue thresholds rise for new "
             "applicants. The fan-funding ones do not, which is why it is the "
             "tier to aim at.")

    out = os.path.join(ROOT, "analytics", "eligibility_%s.md" % a.key)
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("\n".join(L))
    print("\nwrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
