# -*- coding: utf-8 -*-
"""Publish at the hours this channel's own numbers prefer.

    python growth/schedule.py --key history --apply

The posting times were guesses written in August - "facts do well mid-morning
and late evening" - and they have been running ever since. The first real
measurement says they are worth a lot more than a guess:

    History Explains   23:00 UTC   842 median views      against 225 overall
    Rise With Fate     15:00 UTC    20 median views      against  90 overall

That is the same video, the same channel, the same week - a slot that buries it
and a slot that quadruples it. This rewrites the cron lines in the channel's
posting workflow so the good hours keep their slots and the worst hour is moved
to the best unused one.

Rules that keep it honest:

  * the number of uploads a day never changes - this moves slots, it does not
    cut or add volume;
  * an hour needs at least three videos behind it before it may be called good
    or bad, which comes from the playbook, not from this file;
  * one move per run. Changing every slot at once means the next measurement
    cannot tell which move did what.
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import store  # noqa: E402

WORKFLOW = {"fun": ".github/workflows/autopost_fun.yml",
            "us": ".github/workflows/autopost_us.yml",
            "history": ".github/workflows/autopost_history.yml"}
CRON = re.compile(r'^(\s*- cron: ")(\d+) (\d+)( \* \* \*"\s*(#.*)?)$')


def hours_from(book, want):
    """Hours the playbook rated, as {hour: median views}."""
    out = {}
    for row in book.get(want, []):
        if row.get("kind") == "hour_utc":
            try:
                out[int(row["value"])] = row.get("views") or 0
            except Exception:
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, choices=sorted(WORKFLOW))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    bpath = os.path.join(HERE, "playbook_%s.json" % a.key)
    if not os.path.exists(bpath):
        print("no playbook yet")
        return 0
    book = json.load(io.open(bpath, encoding="utf-8"))
    good = hours_from(book, "prefer")
    bad = hours_from(book, "avoid")
    if not good:
        print("%s: no hour has enough evidence yet" % a.key)
        return 0

    path = os.path.join(ROOT, WORKFLOW[a.key])
    lines = io.open(path, encoding="utf-8").read().splitlines(True)

    current = []
    for i, line in enumerate(lines):
        m = CRON.match(line.rstrip("\n"))
        if m:
            current.append((i, int(m.group(3)), int(m.group(2)), m))   # index, hour, minute
    if not current:
        print("%s: no cron lines found" % a.key)
        return 0

    used = set(h for _, h, _, _ in current)
    print("%s: publishes at %s UTC" % (a.key, ", ".join("%02d" % h for h in sorted(used))))
    print("   good hours: %s" % ", ".join("%02d (%s views)" % (h, v) for h, v in sorted(good.items(), key=lambda kv: -kv[1])))
    print("   bad hours:  %s" % (", ".join("%02d (%s views)" % (h, v) for h, v in sorted(bad.items())) or "-"))

    # Every hour the playbook has evidence for, not only the ones it called
    # good or bad: a slot with 40 measured views is worth moving to one with
    # 500 even if neither crossed the "avoid" threshold. Cron hours drift by a
    # few minutes to an hour on GitHub's schedulers, so these are the hours the
    # videos actually landed at.
    rated = dict(bad)
    for name, ev in (book.get("evidence") or {}).items():
        if name.startswith("hour_utc:"):
            try:
                rated.setdefault(int(name.split(":", 1)[1]), ev.get("views") or 0)
            except Exception:
                pass
    # the weakest slot in use, by what actually happened at that hour
    worst = None
    for idx, hour, minute, m in current:
        if hour not in rated:
            continue
        if worst is None or rated[hour] < rated[worst[1]]:
            worst = (idx, hour, minute, m)
    # the best hour the data likes that is not already in use
    spare = [(h, v) for h, v in sorted(good.items(), key=lambda kv: -kv[1]) if h not in used]

    if not worst:
        print("   nothing to move: no slot in use has evidence behind it yet")
        return 0
    if not spare:
        print("   nothing to move to: every hour the data likes is already in use")
        return 0
    if rated[worst[1]] >= spare[0][1] * 0.75:
        print("   nothing worth moving: the weakest slot in use (%02d, %s views) is "
              "close to the best free one (%02d, %s views)"
              % (worst[1], rated[worst[1]], spare[0][0], spare[0][1]))
        return 0

    idx, hour, minute, m = worst
    new_hour = spare[0][0]
    lines[idx] = "%s%d %d%s\n" % (m.group(1), minute, new_hour,
                                  ' * * *"   # moved by growth/schedule.py on %s: '
                                  '%02d UTC measured %s views against %02d at %s'
                                  % (date.today().isoformat(), hour, rated[hour],
                                     new_hour, spare[0][1]))
    print("   MOVE %02d:%02d -> %02d:%02d  (%s views -> %s at the new hour)"
          % (hour, minute, new_hour, minute, rated[hour], spare[0][1]))

    if a.apply:
        io.open(path, "w", encoding="utf-8", newline="\n").write("".join(lines))
        print("   rewrote %s" % WORKFLOW[a.key])
        log = os.path.join(store.DIR, "schedule_changes.jsonl")
        with io.open(log, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"date": date.today().isoformat(), "key": a.key,
                                "from_hour": hour, "to_hour": new_hour,
                                "from_views": rated[hour], "to_views": spare[0][1]}) + "\n")
    else:
        print("   (dry run - pass --apply to rewrite)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
