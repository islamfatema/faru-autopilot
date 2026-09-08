# -*- coding: utf-8 -*-
"""Refuse to write to a channel the token does not belong to.

Every write tool here trusts that YT_REFRESH_TOKEN_MANAGE_US really is Rise
With Fate. Nothing checks it. A swapped secret would put FaRu Fact's channel
description on Rise, or retitle the wrong videos, and the first sign would be
Fatema noticing days later - the same class of mistake as linking @FaRuFacts,
which turned out to be someone else's channel entirely, because the handle
looked right.

Three tokens are sitting on the Desktop right now waiting to be installed, and
they cannot be verified today because the Data API quota is spent. That is
exactly the situation this guard exists for: the workflow says which channel
each step is for, and the tool stops before writing if the token disagrees. It
costs nothing - the channel title is already being fetched.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUARD = '''

def check_channel(actual, expected):
    """Stop before writing if the token is not the channel we were told."""
    if not expected:
        return
    if actual.strip().lower() != expected.strip().lower():
        raise SystemExit(
            "REFUSING TO WRITE."
            "\\n  this run is for : %s"
            "\\n  the token is    : %s"
            "\\nA swapped secret would edit the wrong channel. Fix the secret "
            "rather than removing this check." % (expected, actual))
'''

ARG = ('    ap.add_argument("--expect", default="",\n'
       '                    help="the channel title this run is for - the tool "\n'
       '                         "refuses to write if the token is a different one")\n')

FILES = {
    "tools/relink.py": (
        'print("channel: %s" % name, flush=True)',
        'print("channel: %s" % name, flush=True)\n    check_channel(name, a.expect)'),
    "tools/playlists.py": (
        'print("channel: %s  |  %d public videos" % (name, len(vids)), flush=True)',
        'print("channel: %s  |  %d public videos" % (name, len(vids)), flush=True)\n'
        '    check_channel(name, a.expect)'),
    "tools/branding.py": (
        'print("channel: %s  (%s)" % (c["snippet"]["title"], cid), flush=True)',
        'print("channel: %s  (%s)" % (c["snippet"]["title"], cid), flush=True)\n'
        '    check_channel(c["snippet"]["title"], a.expect)'),
    "tools/retitle.py": (
        'print("channel: %s" % c["snippet"]["title"], flush=True)',
        'print("channel: %s" % c["snippet"]["title"], flush=True)\n'
        '    check_channel(c["snippet"]["title"], EXPECT)'),
    "tools/set_thumbnails.py": (
        'print("channel: %s" % c["snippet"]["title"], flush=True)',
        'print("channel: %s" % c["snippet"]["title"], flush=True)\n'
        '    check_channel(c["snippet"]["title"], EXPECT)'),
}

# retitle and set_thumbnails fetch the channel inside a helper that has no
# access to the parsed args, so they read the expectation from the environment
# instead - the workflow sets it either way.
ENV_EXPECT = 'EXPECT = os.environ.get("EXPECT_CHANNEL", "")\n\n\n'


def patch(rel, old, new):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "def check_channel" in s:
        print("  already guarded: %s" % rel)
        return
    if s.count(old) != 1:
        raise SystemExit("%s: anchor found %d times" % (rel, s.count(old)))
    s = s.replace(old, new)
    s = s.replace("def main():", GUARD.strip("\n") + "\n\n\ndef main():", 1)

    if "EXPECT" in new and "a.expect" not in new:
        s = s.replace("def check_channel(", ENV_EXPECT + "def check_channel(", 1)
    else:
        i = s.index("    a = ap.parse_args()")
        s = s[:i] + ARG + s[i:]

    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  guarded: %s" % rel)


for rel, (old, new) in FILES.items():
    patch(rel, old, new)
print("done")
