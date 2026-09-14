# -*- coding: utf-8 -*-
"""A playlist for the series, in episode order.

Each channel now publishes a numbered series - Facts That Sound Fake, Your Mind,
Measured, Older Than You Think - and every episode ends by naming the next one.
That promise is only kept if the next one is findable, and on a channel with
three hundred Shorts it is not.

A playlist keeps it: episodes in order, autoplaying into each other, and a
viewer who taps the first one can watch fourteen. That is the cheapest watch
time on the channel - no production, and it counts toward the 4,000 hours - and
it is the difference between "that was interesting" and a subscription.

The order comes from the bank, not from the upload dates: episode 3 published
before episode 2 on one channel because a run failed and the next slot picked
up the following one.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "tools", "playlists.py")

HELPER = '''
BANKS = {"FaRu Fact": ("autopilot_fun/scripts_fun.json", "Facts That Sound Fake"),
         "Rise With Fate": ("autopilot_us/scripts_us.json", "Your Mind, Measured"),
         "History That Explains the World":
             ("autopilot_history/scripts_history.json", "Older Than You Think")}


def series_order(channel_name):
    """(series title, [episode title in order]) for this channel, or None.

    Read from the bank rather than from the upload dates: a failed run means
    episode 3 can publish before episode 2, and a series playlist in the wrong
    order is worse than none.
    """
    for name, (rel, series) in BANKS.items():
        if name.lower() in (channel_name or "").lower():
            try:
                bank = json.load(open(os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel),
                    encoding="utf-8"))
            except Exception:
                return None
            eps = sorted([d for d in bank if d.get("series")],
                         key=lambda d: d.get("series_n", 0))
            return series, [d["title"] for d in eps]
    return None


def _norm(t):
    return " ".join(re.sub(r"#\\w+", " ", (t or "")).lower().split())


def series_videos(vids, channel_name):
    """The published episodes of the series, in episode order."""
    got = series_order(channel_name)
    if not got:
        return None, []
    series, titles = got
    by_title = dict((_norm(v["snippet"]["title"]), v) for v in vids)
    return series, [by_title[_norm(t)] for t in titles if _norm(t) in by_title]

'''

OLD_WANT = '''    want = {"documentaries": docs, "start_here": shorts}'''
NEW_WANT = '''    # The numbered series, in the order the episodes were written. Every one of
    # them ends by naming the next; this is where the next one actually is.
    series_title, series_eps = series_videos(vids, name)
    if series_eps:
        PLAYLISTS["series"] = {
            "title": series_title,
            "description": ("The series, in order. Every episode is one checked "
                            "fact with its source in the description. Start at "
                            "number one."),
        }
        print("series: %d of %d episodes published so far"
              % (len(series_eps), 14), flush=True)

    want = {"documentaries": docs, "start_here": shorts, "series": series_eps}'''


def patch():
    s = io.open(PATH, encoding="utf-8").read()
    if "def series_videos" in s:
        print("already patched")
        return
    for old, what in ((OLD_WANT, "want map"),):
        if s.count(old) != 1:
            raise SystemExit("%s found %d times" % (what, s.count(old)))
    s = s.replace(OLD_WANT, NEW_WANT)
    s = s.replace("def _open(req, timeout=120):", HELPER.strip("\n") + "\n\n\ndef _open(req, timeout=120):", 1)
    ast.parse(s)
    tmp = PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, PATH)
    print("patched tools/playlists.py")


patch()
