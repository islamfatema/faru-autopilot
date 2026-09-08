# -*- coding: utf-8 -*-
"""Do not diagnose from a number that was never returned.

The first live run printed, for FaRu Fact:

    click-through rate        -
    DIAGNOSIS: PACKAGING - people who watch it stay, and almost nobody clicks.

The second line is a fabrication. The CTR was not low; it was *absent* -
YouTube answered "Unknown identifier (impressions)", and diagnose() read the
zero it defaulted to as a measurement. A tool that invents a finding out of a
missing value is worse than one that says nothing, because the finding is
actionable and wrong, and I would have spent a week rewriting titles.

Three fixes:

  - a missing CTR is now unknown, not weak. The diagnosis says which half it
    can judge and which it cannot.
  - impressions are requested under each name the API has used, and the run
    reports which one worked rather than swallowing the failure.
  - the per-video table needs the Data API only for titles, and that quota is
    shared with the uploads. When it is gone the table still prints, with video
    ids instead of titles, rather than losing the whole section.
"""
import ast
import io
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "tools", "insights.py")

OLD_DIAG = '''def diagnose(ctr, pct_viewed, subs_per_k):
    """The decision rule. CTR and retention fail in opposite directions and
    need opposite fixes, which is exactly why guessing between them wastes
    weeks."""
    # Benchmarks for a small channel, not absolutes: 4-6% CTR is ordinary,
    # 30%+ average viewed is healthy for long-form, and 1 subscriber per
    # thousand views is a weak but common starting point.
    weak_ctr = ctr < 4.0
    weak_ret = pct_viewed < 30.0
    if weak_ctr and weak_ret:
        return ("BOTH WEAK - the topic is not wanted. Change the subject, "
                "not the packaging.")
    if weak_ctr:
        return ("PACKAGING - people who watch it stay, and almost nobody "
                "clicks. Rewrite titles and thumbnails; the content is fine.")
    if weak_ret:
        return ("CONTENT - the packaging earns the click and the video loses "
                "them. Fix the first ten seconds before touching the title.")
    if subs_per_k < 1.0:
        return ("POSITIONING - clicks and retention are both fine and nobody "
                "subscribes. The channel is not telling them what they get "
                "if they come back.")
    return "WORKING - make more of this."'''

NEW_DIAG = '''def diagnose(ctr, pct_viewed, subs_per_k, have_ctr=True):
    """The decision rule. CTR and retention fail in opposite directions and
    need opposite fixes, which is exactly why guessing between them wastes
    weeks.

    have_ctr says whether a click-through rate was actually measured. On a
    Shorts-dominated channel YouTube returns none at all, and the first live
    run read that absence as a zero and announced a packaging problem that no
    number supported. An invented finding is worse than a missing one.
    """
    # Benchmarks for a small channel, not absolutes: 4-6% CTR is ordinary,
    # 30%+ average viewed is healthy, and 1 subscriber per thousand views is a
    # weak but common starting point.
    weak_ret = pct_viewed < 30.0
    weak_subs = subs_per_k < 1.0

    if not have_ctr:
        parts = ["NO CTR AVAILABLE - YouTube reports no impressions for this "
                 "channel, which is normal when almost all views come from the "
                 "Shorts feed. Nothing here can say whether packaging works."]
        if weak_ret:
            parts.append("Retention IS measured and it is weak: fix the first "
                         "ten seconds.")
        elif weak_subs:
            parts.append("Retention is fine and nobody subscribes: this is "
                         "positioning, not packaging.")
        else:
            parts.append("Retention and subscriber conversion are both fine.")
        return " ".join(parts)

    weak_ctr = ctr < 4.0
    if weak_ctr and weak_ret:
        return ("BOTH WEAK - the topic is not wanted. Change the subject, "
                "not the packaging.")
    if weak_ctr:
        return ("PACKAGING - people who watch it stay, and almost nobody "
                "clicks. Rewrite titles and thumbnails; the content is fine.")
    if weak_ret:
        return ("CONTENT - the packaging earns the click and the video loses "
                "them. Fix the first ten seconds before touching the title.")
    if weak_subs:
        return ("POSITIONING - clicks and retention are both fine and nobody "
                "subscribes. The channel is not telling them what they get "
                "if they come back.")
    return "WORKING - make more of this."'''

OLD_IMP = '''    ctr = imp = 0.0
    try:
        ir = report(tok, s, e, ["impressions", "impressionClickThroughRate"])
        ih = [h["name"] for h in ir.get("columnHeaders", [])]
        I = dict(zip(ih, one(ir)))
        imp = I.get("impressions", 0) or 0
        ctr = I.get("impressionClickThroughRate", 0) or 0
    except Exception as ex:
        print("(impressions unavailable: %s)" % str(ex)[:90])'''

NEW_IMP = '''    # Impressions have gone by more than one identifier, and on a channel whose
    # views are nearly all Shorts the API returns none under any of them. Try
    # each and say plainly which worked, rather than defaulting to zero and
    # letting the diagnosis treat "absent" as "low".
    ctr = imp = 0.0
    have_ctr = False
    for names in (["impressions", "impressionClickThroughRate"],
                  ["annotationImpressions"],):
        try:
            ir = report(tok, s, e, names)
            ih = [h["name"] for h in ir.get("columnHeaders", [])]
            I = dict(zip(ih, one(ir)))
            imp = I.get(names[0], 0) or 0
            ctr = I.get("impressionClickThroughRate", 0) or 0
            have_ctr = "impressionClickThroughRate" in I
            break
        except Exception as ex:
            last_imp_error = str(ex)[:100]
    else:
        print("(no impressions metric available - %s)" % last_imp_error)'''

OLD_CTR_LINE = '''    print("\\n  DIAGNOSIS: %s" % diagnose(ctr, C.get("averageViewPercentage", 0) or 0, subs_per_k))'''
NEW_CTR_LINE = '''    print("\\n  DIAGNOSIS: %s"
          % diagnose(ctr, C.get("averageViewPercentage", 0) or 0, subs_per_k,
                     have_ctr))'''

OLD_TITLES = '''        ids = [r[0] for r in rows(vr)]
        titles = {}
        for i in range(0, len(ids), 50):
            j = get(DATA_API + "/videos?part=snippet&id=" + ",".join(ids[i:i + 50]), tok)
            for it in j.get("items", []):
                titles[it["id"]] = it["snippet"]["title"]'''
NEW_TITLES = '''        ids = [r[0] for r in rows(vr)]
        titles = {}
        # Titles come from the Data API, whose quota is shared with the uploads
        # and runs out most afternoons. Losing the names is a nuisance; losing
        # the whole table because of it is not acceptable.
        for i in range(0, len(ids), 50):
            try:
                j = get(DATA_API + "/videos?part=snippet&id=" + ",".join(ids[i:i + 50]), tok)
            except Exception as ex:
                print("  (titles unavailable, showing ids: %s)" % str(ex)[:80])
                break
            for it in j.get("items", []):
                titles[it["id"]] = it["snippet"]["title"]'''


def main():
    s = io.open(PATH, encoding="utf-8").read()
    if "have_ctr" in s:
        raise SystemExit("already patched")
    for old, new, what in ((OLD_DIAG, NEW_DIAG, "diagnose"),
                           (OLD_IMP, NEW_IMP, "impressions"),
                           (OLD_CTR_LINE, NEW_CTR_LINE, "diagnosis call"),
                           (OLD_TITLES, NEW_TITLES, "title lookup")):
        if s.count(old) != 1:
            raise SystemExit("%s: found %d times" % (what, s.count(old)))
        s = s.replace(old, new)
    s = s.replace("    ctr = imp = 0.0\n    have_ctr = False",
                  "    ctr = imp = 0.0\n    have_ctr = False\n    last_imp_error = \"\"", 1)
    ast.parse(s)
    tmp = PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, PATH)
    print("patched tools/insights.py")


main()
