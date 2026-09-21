# -*- coding: utf-8 -*-
"""Build the page that shows what the growth loop measured and decided.

    python growth/dashboard.py            # writes analytics/dashboard.html

Everything on the page comes from analytics/diagnosis_*.json and
growth/playbook_*.json - the same files the machines read. Nothing is computed
here that is not already in them, so the page can never disagree with what the
system actually did. Where YouTube does not expose a number - impressions,
click-through rate - the page says so instead of leaving a confident blank.
"""
import io
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import store  # noqa: E402

CHANNELS = [("us", "Rise With Fate", "#B4324A"),
            ("fun", "FaRu Fact", "#0B7285"),
            ("history", "History That Explains the World", "#7A5C1E")]

VERDICT_TONE = {"WINNER": "win", "OK": "ok", "NOT_ENOUGH_DATA": "muted",
                "WEAK_HOOK": "bad", "NO_DISTRIBUTION": "bad",
                "WEAK_SUBSCRIBE": "warn", "WEAK_COMMENTS": "warn",
                "WEAK_SHARES": "warn"}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def load(key):
    d = os.path.join(store.DIR, "diagnosis_%s.json" % key)
    p = os.path.join(HERE, "playbook_%s.json" % key)
    c = os.path.join(store.DIR, "subscribers_%s.json" % key)
    diag = json.load(io.open(d, encoding="utf-8")) if os.path.exists(d) else None
    book = json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else None
    card = json.load(io.open(c, encoding="utf-8")) if os.path.exists(c) else None
    return diag, book, card


def subscriber_block(card):
    """Gained, lost, net, and the distance to each monetisation threshold.

    Net is the number that matters: a channel gaining 20 and losing 25 is
    shrinking while its view count looks healthy.
    """
    if not card:
        return ""
    w7, w28, mon = card["last_7"], card["last_28"], card["monetisation"]

    def tone(n):
        return "win" if n > 0 else ("bad" if n < 0 else "muted")

    o = ["<div class='cols'><div><h3>Subscribers - gained, lost, net</h3>",
         "<table class='mini'>",
         "<tr><th></th><th>gained</th><th>lost</th><th>net</th></tr>",
         "<tr><td>last 7 days</td><td>%d</td><td>%d</td><td class='%s'><b>%+d</b></td></tr>"
         % (w7["gained"], w7["lost"], tone(w7["net"]), w7["net"]),
         "<tr><td>last 28 days</td><td>%d</td><td>%d</td><td class='%s'><b>%+d</b></td></tr>"
         % (w28["gained"], w28["lost"], tone(w28["net"]), w28["net"]),
         "</table>"]
    best = (card.get("best_converters") or [None])[0]
    worst = (card.get("views_without_subscribers") or [None])[0]
    if best:
        o.append("<p class='muted'>best converter: <b>%s</b> - %+.2f net subs per 1,000 on %d views</p>"
                 % (esc(best["title"][:60]), best["per_1k"], best["views"]))
    if worst:
        o.append("<p class='muted'>most views without a subscriber: <b>%s</b> - %d views, 0 subs</p>"
                 % (esc(worst["title"][:60]), worst["views"]))
    o.append("</div><div><h3>Distance to monetisation</h3><table class='mini'>")
    o.append("<tr><td>subscribers</td><td><b>%d</b> / 1,000</td><td class='muted'>gap %d</td></tr>"
             % (mon["subscribers"], mon["subscriber_gap"]))
    o.append("<tr><td>watch hours (365d)</td><td><b>%s</b> / 4,000</td><td class='muted'>gap %s</td></tr>"
             % (mon["watch_hours_365"], round(mon["watch_hour_gap"])))
    o.append("<tr><td>Shorts views (90d)</td><td><b>%s</b> / 10M</td><td class='muted'>gap %s</td></tr>"
             % ("{:,}".format(mon["shorts_views_90"]), "{:,}".format(mon["shorts_view_gap"])))
    o.append("</table>")
    d1 = mon.get("days_to_1000_subs_at_this_rate")
    d2 = mon.get("days_to_4000_hours_at_this_rate")
    o.append("<p class='muted'>at the last 28 days' rate: %s to 1,000 subscribers, %s to 4,000 hours</p>"
             % ("<b>%d days</b>" % d1 if d1 else "<b>not on this trajectory</b>",
                "<b>%d days</b>" % d2 if d2 else "<b>not on this trajectory</b>"))
    o.append("</div></div>")
    return "\n".join(o)


def num(x, suffix=""):
    if x is None:
        return "&mdash;"
    if isinstance(x, float):
        x = round(x, 2)
    return "%s%s" % (x, suffix)


def channel_section(key, name, accent, diag, book, card):
    if not diag:
        return "<section class='ch'><h2>%s</h2><p class='muted'>no measurement yet</p></section>" % esc(name)
    b = (diag.get("baselines") or {}).get("short") or {}
    bl = (diag.get("baselines") or {}).get("long") or {}
    counts = diag.get("counts") or {}
    vids = diag.get("videos") or []
    judged = [v for v in vids if v.get("judgeable")]
    winners = [v for v in judged if v["verdict"] == "WINNER"][:5]
    problems = [v for v in judged if v["verdict"] in
                ("WEAK_HOOK", "NO_DISTRIBUTION", "WEAK_SUBSCRIBE",
                 "WEAK_COMMENTS", "WEAK_SHARES")][:6]

    o = []
    o.append("<section class='ch' style=\"--accent:%s\">" % accent)
    o.append("<header class='ch-h'><div><h2>%s</h2>"
             "<p class='sub'>%s subscribers &middot; %d videos measured &middot; "
             "window %d days</p></div>" %
             (esc(name), num(diag.get("subscribers")), len(judged), diag.get("window_days") or 28))
    if diag.get("recovery_mode"):
        o.append("<p class='flag bad'>RECOVERY MODE &mdash; recent median %s views "
                 "against %s before</p>" % (num(diag.get("recent_median_views")),
                                            num(diag.get("previous_median_views"))))
    else:
        o.append("<p class='flag ok'>holding its own normal</p>")
    o.append("</header>")

    o.append("<div class='stats'>")
    for label, val in (("median views / Short", num(b.get("views"))),
                       ("percent viewed", num(b.get("avg_pct"), "%")),
                       ("subs per 1,000", num(b.get("subs_per_1k"))),
                       ("comments per 1,000", num(b.get("comments_per_1k"))),
                       ("shares per 1,000", num(b.get("shares_per_1k"))),
                       ("median views / long-form", num(bl.get("views")))):
        o.append("<div class='stat'><b>%s</b><span>%s</span></div>" % (val, esc(label)))
    o.append("</div>")

    o.append("<div class='verdicts'>")
    for v, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        o.append("<span class='pill %s'>%s <b>%d</b></span>"
                 % (VERDICT_TONE.get(v, "muted"), esc(v.replace("_", " ").lower()), n))
    o.append("</div>")

    o.append(subscriber_block(card))
    o.append("<div class='cols'>")
    o.append("<div><h3>Winning, and worth building from</h3><ul class='list'>")
    for w in winners or []:
        o.append("<li><b>%s</b><span>%s</span></li>" % (esc(w["title"][:70]), esc(w["why"])))
    if not winners:
        o.append("<li class='muted'>nothing has cleared the bar this window</li>")
    o.append("</ul></div>")

    o.append("<div><h3>Failing, and what changes next</h3><ul class='list'>")
    for p in problems or []:
        o.append("<li><b>%s</b><span class='v %s'>%s</span><span>%s</span></li>"
                 % (esc(p["title"][:70]), VERDICT_TONE.get(p["verdict"], "muted"),
                    esc(p["verdict"].replace("_", " ").lower()), esc(p["why"])))
    if not problems:
        o.append("<li class='muted'>no diagnosed failures in this window</li>")
    o.append("</ul></div>")
    o.append("</div>")

    if book:
        o.append("<div class='cols'>")
        o.append("<div><h3>More of this</h3><ul class='list tight'>")
        for p in (book.get("prefer") or [])[:7]:
            o.append("<li><b>%s: %s</b><span>%s</span></li>"
                     % (esc(p["kind"]), esc(p["value"]), esc(p["why"])))
        if not book.get("prefer"):
            o.append("<li class='muted'>not enough evidence yet</li>")
        o.append("</ul></div>")
        o.append("<div><h3>Already tested and lost</h3><ul class='list tight'>")
        for p in (book.get("avoid") or [])[:7]:
            o.append("<li><b>%s: %s</b><span>%s</span></li>"
                     % (esc(p["kind"]), esc(p["value"]), esc(p["why"])))
        if not book.get("avoid"):
            o.append("<li class='muted'>nothing has lost badly enough yet</li>")
        o.append("</ul></div>")
        o.append("</div>")
    o.append("</section>")
    return "\n".join(o)


HEAD = """<title>Growth Loop Board</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=Public+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>
:root{
  --paper:#EEF1F3; --panel:#FFFFFF; --sunk:#E3E8EB; --ink:#11171A; --ink-2:#3B474D;
  --muted:#6A757C; --rule:#CBD4D9; --accent:#0B7285;
  --win:#166B3E; --win-bg:rgba(22,107,62,.10);
  --bad:#A32B2B; --bad-bg:rgba(163,43,43,.10);
  --warn:#8A5A00; --warn-bg:rgba(138,90,0,.12);
  --display:"Bricolage Grotesque",system-ui,sans-serif;
  --body:"Public Sans",system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#0C1013; --panel:#141A1E; --sunk:#1B2328; --ink:#E7EDF0; --ink-2:#B3C0C7;
  --muted:#84919A; --rule:#28333A; --accent:#3FB4C6;
  --win:#5CC98C; --win-bg:rgba(92,201,140,.12);
  --bad:#E8797A; --bad-bg:rgba(232,121,122,.12);
  --warn:#E0A356; --warn-bg:rgba(224,163,86,.14);
}}
:root[data-theme="dark"]{
  --paper:#0C1013; --panel:#141A1E; --sunk:#1B2328; --ink:#E7EDF0; --ink-2:#B3C0C7;
  --muted:#84919A; --rule:#28333A; --accent:#3FB4C6;
  --win:#5CC98C; --win-bg:rgba(92,201,140,.12);
  --bad:#E8797A; --bad-bg:rgba(232,121,122,.12);
  --warn:#E0A356; --warn-bg:rgba(224,163,86,.14);
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:16px;line-height:1.55}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
h1,h2,h3{font-family:var(--display);font-weight:800;letter-spacing:-.015em;margin:0;text-wrap:balance}
header.top{background:var(--panel);border-bottom:1px solid var(--rule);padding:30px 0 24px}
header.top h1{font-size:clamp(26px,4.6vw,40px)}
.kicker{font-family:var(--mono);font-size:12px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
.lede{color:var(--ink-2);max-width:74ch;margin:12px 0 0}
section.ch{margin:26px 0;background:var(--panel);border:1px solid var(--rule);border-top:5px solid var(--accent)}
.ch-h{display:flex;gap:16px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;padding:18px 20px;border-bottom:1px solid var(--rule)}
.ch-h h2{font-size:22px}
.sub{margin:4px 0 0;font-family:var(--mono);font-size:12px;color:var(--muted)}
.flag{margin:0;font-family:var(--mono);font-size:12px;letter-spacing:.06em;text-transform:uppercase;padding:6px 10px;border:1px solid currentColor}
.flag.ok{color:var(--win);background:var(--win-bg)}
.flag.bad{color:var(--bad);background:var(--bad-bg)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--rule);border-bottom:1px solid var(--rule)}
.stat{background:var(--panel);padding:12px 16px}
.stat b{display:block;font-family:var(--display);font-size:24px;line-height:1.15;font-variant-numeric:tabular-nums}
.stat span{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.verdicts{display:flex;flex-wrap:wrap;gap:8px;padding:14px 20px;border-bottom:1px solid var(--rule)}
.pill{font-family:var(--mono);font-size:12px;padding:4px 9px;border:1px solid var(--rule);color:var(--ink-2);background:var(--sunk)}
.pill.win{color:var(--win);background:var(--win-bg);border-color:currentColor}
.pill.bad{color:var(--bad);background:var(--bad-bg);border-color:currentColor}
.pill.warn{color:var(--warn);background:var(--warn-bg);border-color:currentColor}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:0}
.cols>div{padding:16px 20px}
.cols>div+div{border-left:1px solid var(--rule)}
.cols+.cols{border-top:1px solid var(--rule)}
@media (max-width:820px){.cols{grid-template-columns:1fr}.cols>div+div{border-left:none;border-top:1px solid var(--rule)}}
h3{font-size:13px;font-family:var(--mono);font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}
ul.list{list-style:none;margin:0;padding:0;display:grid;gap:10px}
ul.list li{display:grid;gap:2px;padding-bottom:9px;border-bottom:1px dashed var(--rule)}
ul.list li:last-child{border-bottom:none;padding-bottom:0}
ul.list b{font-size:15px}
ul.list span{color:var(--ink-2);font-size:14px}
ul.tight li{gap:1px}
.v{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase}
.v.bad{color:var(--bad)} .v.warn{color:var(--warn)} .v.win{color:var(--win)}
.muted{color:var(--muted)}
footer{border-top:1px solid var(--rule);background:var(--panel);padding:20px 0 40px;color:var(--muted);font-size:14px}
table.mini{border-collapse:collapse;width:100%;font-size:14px;margin-bottom:8px}
table.mini td,table.mini th{padding:5px 8px;border-bottom:1px solid var(--rule);text-align:left;font-variant-numeric:tabular-nums}
table.mini th{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
table.mini td.win{color:var(--win)} table.mini td.bad{color:var(--bad)} table.mini td.muted{color:var(--muted)}
.note{border-left:4px solid var(--warn);background:var(--panel);border:1px solid var(--rule);border-left:4px solid var(--warn);padding:12px 16px;margin:18px 0;color:var(--ink-2)}
</style>
"""


def main():
    parts = [HEAD]
    parts.append("<header class='top'><div class='wrap'>")
    parts.append("<p class='kicker'>measured %s</p>" % date.today().isoformat())
    parts.append("<h1>What the numbers say, and what changes next</h1>")
    parts.append("<p class='lede'>Every video on all three channels, judged against that "
                 "channel's own median for its own kind - because 300 views is a failure on "
                 "one channel and a win on another. Each verdict carries the change it "
                 "forces on the next upload. The posting machines read the same files.</p>")
    parts.append("</div></header><div class='wrap'>")
    parts.append("<div class='note'><b>Not shown, because YouTube does not expose it:</b> "
                 "impressions and click-through rate live only inside Studio. Where "
                 "separating &ldquo;nobody was shown this&rdquo; from &ldquo;everybody "
                 "scrolled past it&rdquo; would change the action, the verdict says so "
                 "rather than guessing.</div>")
    for key, name, accent in CHANNELS:
        diag, book, card = load(key)
        parts.append(channel_section(key, name, accent, diag, book, card))
    parts.append("</div><footer><div class='wrap'>Built from analytics/diagnosis_*.json and "
                 "growth/playbook_*.json - the same files the posting machines read. "
                 "Rebuilt every morning by the growth workflow.</div></footer>")

    out = os.path.join(store.DIR, "dashboard.html")
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(parts))
    print("wrote analytics/dashboard.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
