# -*- coding: utf-8 -*-
"""Is anything silently dead?

Fatema's complaint, and she is right: things get built, the runs go green, and
nothing happens inside them until she asks. Three in one afternoon today -

  * History had 25 publishable scripts left, three days at its new cadence,
    because a gate was blocking 74% of its bank
  * the only channel that converts had no questions seeded under anything,
    because its comment floor was set where nothing could reach it
  * the documentary refiller had been declining to write for weeks, because it
    counted published topics as if they were still available

- and every one of them was in a workflow that reported success. "Succeeded"
only means the script exited zero. It says nothing about whether the thing the
script exists to do happened.

So this checks the numbers that go quiet rather than loud, and says PROBLEM
when one of them is wrong. It is deliberately small: a check nobody reads is
the same failure one level up, so it reports a handful of things that have
each actually broken here, not everything that could.

    python tools/health.py
"""
import datetime
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = (("history", "History", "autopost_history.yml", "autopost_doc.yml"),
            ("us", "Rise", "autopost_us.yml", "autopost_doc_us.yml"),
            ("fun", "FaRu Fact", "autopost_fun.yml", "autopost_doc_fun.yml"))
MIN_SHORT_DAYS = 7          # below this the bank is about to decide for us
MIN_DOC_WEEKS = 4.0
MAX_SILENT_DAYS = 2         # a channel that has not published in this long


def crons(wf):
    try:
        return len(re.findall(r"- cron:",
                              io.open(os.path.join(ROOT, ".github", "workflows", wf),
                                      encoding="utf-8").read()))
    except Exception:
        return 0


def norm(t):
    t = re.sub(r"#\w+", "", t or "")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())


def doc_runway(key, wf):
    d = os.path.join(ROOT, "autopilot_%s" % key, "longform")
    topics = []
    for f in glob.glob(os.path.join(d, "topics*.json")):
        try:
            topics += json.load(io.open(f, encoding="utf-8"))
        except Exception:
            pass
    try:
        done = set(norm(t) for t in json.load(
            io.open(os.path.join(d, "published_docs.json"), encoding="utf-8")))
    except Exception:
        done = set()
    left = [t for t in topics if norm(t.get("title")) not in done]
    per = crons(wf)
    return len(topics), len(left), per, (len(left) / float(per)) if per else 0.0


def last_published(key):
    """(last upload, the day the file itself was written).

    Both, because they answer different questions. A last upload four days ago
    in a file written today means the channel is silent. The same date in a
    file written four days ago means the collection is broken and the channel
    may be fine - which is what happened on 13 October, and reporting it as a
    silent channel would have been an alarm worth ignoring.
    """
    try:
        d = json.load(io.open(os.path.join(ROOT, "analytics",
                                           "videos_%s.json" % key),
                              encoding="utf-8"))
    except Exception:
        return None, None
    days = [v["published"][:10] for v in d["videos"].values() if v.get("published")]
    return (max(days) if days else None), d.get("updated")


def engagement(key, days=7):
    """Comments and likes the channel earned recently - the quiet signals."""
    cut = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    try:
        vids = json.load(io.open(os.path.join(ROOT, "analytics",
                                              "videos_%s.json" % key),
                                 encoding="utf-8"))["videos"]
    except Exception:
        return 0, 0, 0
    c = l = v = 0
    for rec in vids.values():
        if (rec.get("published") or "")[:10] < cut:
            continue
        s = rec.get("snapshots") or []
        if not s:
            continue
        c += s[-1].get("comments") or 0
        l += s[-1].get("likes") or 0
        v += s[-1].get("views") or 0
    return v, l, c


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    today = datetime.date.today()
    out = ["# Is anything silently dead?", "",
           "Checked %s. A green workflow run only means the script exited "
           "zero. These are the numbers that go quiet instead of loud." %
           today.isoformat(), ""]
    problems = []

    for key, name, short_wf, doc_wf in CHANNELS:
        per_day = crons(short_wf)
        out += ["## %s" % name, ""]

        last, updated = last_published(key)
        stale = 0
        if updated:
            stale = (today - datetime.date(*map(int, updated.split("-")))).days
            line = "    data written           %s (%d days ago)" % (updated, stale)
            if stale > 1:
                problems.append("%s's analytics have not reached the repo for "
                                "%d days - every number below it is that old"
                                % (name, stale))
                line += "   <-- PROBLEM"
            out.append(line)
        if last:
            age = (today - datetime.date(*map(int, last.split("-")))).days
            line = "    last upload            %s (%d days ago)" % (last, age)
            if age > MAX_SILENT_DAYS and stale <= 1:
                # Only a real silence when the file that says so is current.
                problems.append("%s has not published for %d days" % (name, age))
                line += "   <-- PROBLEM"
            elif age > MAX_SILENT_DAYS:
                line += "   (but the file is %d days old, so this may just be "
                line = line % stale
                line += "the stale data above)"
            out.append(line)

        n, left, per, weeks = doc_runway(key, doc_wf)
        line = ("    documentary topics     %d left of %d, %d a week -> %.1f weeks"
                % (left, n, per, weeks))
        if weeks < MIN_DOC_WEEKS:
            problems.append("%s has %.1f weeks of documentary topics" % (name, weeks))
            line += "   <-- PROBLEM"
        out.append(line)
        out.append("    shorts a day           %d" % per_day)

        # An experiment that runs and records nothing. The subscribe-placement
        # test printed its arm on every upload for eight days while the
        # autopost workflows committed only the ledger, so the file died with
        # the runner and the report read "nothing assigned yet" throughout.
        ab = os.path.join(ROOT, "analytics", "ab_subscribe_%s.json" % key)
        try:
            rows = len(json.load(io.open(ab, encoding="utf-8")))
        except Exception:
            rows = 0
        out.append("    subscribe test         %d videos assigned" % rows)
        if rows == 0 and stale <= 1:
            problems.append("%s has published since the subscribe test began "
                            "and recorded no arms - the test is not recording"
                            % name)
            out[-1] += "   <-- PROBLEM"

        v, l, c = engagement(key)
        out.append("    last 7 days            %d views, %d likes, %d comments"
                   % (v, l, c))
        if v > 500 and c == 0:
            problems.append("%s took %d views in a week and not one comment - "
                            "check the question seeding" % (name, v))
            out.append("                           <-- PROBLEM: views but no "
                       "comments at all")
        out.append("")

    # The script banks, after the publish gate. This is the number that was
    # three days deep on History today while the bank looked full.
    out += ["## Publishable scripts left, after the gate", "",
            "    Run from each channel's own machine, because the gate is part "
            "of it:", "",
            "        cd autopilot_<key> && python -c \"import main_<key>\"", "",
            "    main_*.py prints the share of its bank the click rule blocks "
            "at startup, and demotes it to a ranking signal above 60%.", ""]

    out += ["## Problems", ""]
    if problems:
        for p in problems:
            out.append("    - %s" % p)
    else:
        out.append("    None of the checks above found anything.")
    out.append("")

    io.open(os.path.join(ROOT, "analytics", "health.md"), "w",
            encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print("\n".join(out))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
