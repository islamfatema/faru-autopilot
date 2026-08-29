# -*- coding: utf-8 -*-
"""How many days of unique video each channel has left.

The failure that flattened the views was silent: the banks quietly ran dry, the
rotation wrapped, and the same videos went up again for weeks with nothing
reporting it. This prints the runway so that never happens unnoticed again, and
warns while there is still time to do something about it.

    python tools/runway.py
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Must match ROTATION_ORIGIN in the main_*.py posting scripts.
ROTATION_ORIGIN = 1787961600   # 2026-08-29 00:00 UTC
PER_DAY = 10
WARN_DAYS = 14

BANKS = [
    ("Rise With Fate", "autopilot_us", "scripts_us.json"),
    ("FaRu Facts", "autopilot_fun", "scripts_fun.json"),
    ("History That Explains", "autopilot_history", "scripts_history.json"),
]


def main():
    used = max(0, int((time.time() - ROTATION_ORIGIN) // 86400)) * PER_DAY
    print("day %d of the rotation - about %d videos published per channel\n"
          % (used // PER_DAY, used))
    print("%-24s %7s %9s %9s" % ("channel", "scripts", "used", "days left"))

    low = []
    for name, d, f in BANKS:
        bank = json.load(io.open(os.path.join(ROOT, d, f), encoding="utf-8"))
        left = max(0, len(bank) - used)
        days = left // PER_DAY
        flag = ""
        if days < WARN_DAYS:
            flag = "  <-- refill needed"
            low.append(name)
        print("%-24s %7d %9d %9d%s" % (name, len(bank), used, days, flag))

    if low:
        print("\nWARNING: %s will start repeating within %d days."
              % (", ".join(low), WARN_DAYS))
        print("Run: python tools/grow.py --target 1200")
        return 1
    print("\nAll channels have more than %d days of unique content." % WARN_DAYS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
