# -*- coding: utf-8 -*-
"""Turn one pasted Meta token into the four secrets crosspost_meta.py needs.

Every Short this machine publishes is already packed for Reels and then thrown
away, because IG_USER_ID, IG_ACCESS_TOKEN, FB_PAGE_ID and FB_PAGE_TOKEN have
never been set. The same vertical file usually reaches more people on Reels
than in the Shorts feed, so those are views the machine makes and discards.

Finding those four values by hand means four lookups in two different consoles.
This does the lookups. Fatema pastes one user token; this discovers her Page,
the Instagram Business account attached to it, and the Page token, checks that
each one can actually publish, and writes them straight into the repository's
secrets with `gh`. The token is read from the environment or from a file and is
never printed, never written to disk by this script, and never committed.

    set META_USER_TOKEN=...        (or: --token-file path)
    python tools/meta_connect.py --check     # look only, change nothing
    python tools/meta_connect.py --apply     # also set the four repo secrets

What it cannot do, and what is Fatema's to do once:
  - create the Meta app and generate the user token (that is the consent),
  - connect the Instagram account to the Facebook Page as a Business account.
"""
import argparse
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
NEED = ("pages_show_list", "pages_manage_posts", "pages_read_engagement",
        "instagram_basic", "instagram_content_publish")


def get(path, token, **params):
    params["access_token"] = token
    url = "%s/%s?%s" % (GRAPH, path.lstrip("/"), urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace").replace(token, "[TOKEN]")
        raise RuntimeError("%s -> %s" % (path, raw[:300]))


def redact(s, token):
    return (s or "").replace(token, "[TOKEN]")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--token-file")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--repo", default="islamfatema/faru-autopilot")
    a = ap.parse_args()

    token = os.environ.get("META_USER_TOKEN", "").strip()
    if not token and a.token_file:
        token = io.open(a.token_file, encoding="utf-8").read().strip()
    if not token:
        print("No token. Put it in META_USER_TOKEN, or pass --token-file.")
        print("It is never printed and never written anywhere by this script.")
        return 2

    # 1. What the token is actually allowed to do. A token that looks fine and
    #    is missing one scope fails later, inside a posting run, where nobody
    #    is watching.
    try:
        perms = get("me/permissions", token)
    except RuntimeError as e:
        print("The token did not work: %s" % redact(str(e), token))
        return 1
    granted = {p["permission"] for p in perms.get("data", [])
               if p.get("status") == "granted"}
    missing = [p for p in NEED if p not in granted]
    print("permissions granted: %d of %d needed" % (len(NEED) - len(missing), len(NEED)))
    for p in missing:
        print("   MISSING  %s" % p)

    # 2. The Page, and the Page's own token - which is what actually posts.
    pages = get("me/accounts", token, fields="id,name,access_token").get("data", [])
    if not pages:
        print("No Facebook Page on this account. A Page is what Reels posts to.")
        return 1
    page = pages[0]
    if len(pages) > 1:
        print("Pages found: %s" % ", ".join(p.get("name", "?") for p in pages))
        print("Using the first one: %s" % page.get("name"))
    print("facebook page      %s  (id %s)" % (page.get("name"), page.get("id")))

    # 3. The Instagram Business account hanging off that Page.
    ig = get(page["id"], page["access_token"],
             fields="instagram_business_account{id,username}")
    iga = (ig or {}).get("instagram_business_account") or {}
    if iga:
        print("instagram account  @%s  (id %s)" % (iga.get("username"), iga.get("id")))
    else:
        print("instagram account  NOT CONNECTED to this Page - Reels on Instagram "
              "will be skipped, Facebook Reels still work")

    values = {"FB_PAGE_ID": page["id"], "FB_PAGE_TOKEN": page["access_token"]}
    if iga.get("id"):
        values["IG_USER_ID"] = iga["id"]
        values["IG_ACCESS_TOKEN"] = page["access_token"]

    if missing:
        print("\nNot setting anything: %d permission(s) are missing above, and a "
              "half-connected account fails inside a posting run where nobody "
              "sees it." % len(missing))
        return 1
    if not a.apply:
        print("\nWould set: %s" % ", ".join(sorted(values)))
        print("Run again with --apply to write them as repository secrets.")
        return 0

    for name in sorted(values):
        p = subprocess.run(["gh", "secret", "set", name, "--repo", a.repo],
                           input=values[name], text=True, capture_output=True)
        print("  %-16s %s" % (name, "set" if p.returncode == 0
                              else "FAILED " + redact(p.stderr.strip(), token)[:120]))
    print("\nDone. The next Short each channel publishes goes to Reels too.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
