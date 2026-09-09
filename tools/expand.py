# -*- coding: utf-8 -*-
"""Lengthen the scripts already in the banks so they clear the 30 second floor.

Fatema's requirement is plain: no video under 30 seconds. The publisher now
enforces it - worth_publishing() refuses anything under 78 spoken words rather
than post another twelve second clip. That is the right rule, and applying it
revealed the real damage:

    us        bank  685   passes the 30s gate:  1
    fun       bank  707   passes the 30s gate: 15
    history   bank  616   passes the 30s gate:  6

Twenty-two usable scripts against thirty videos a day. Every channel runs dry
inside a day and goes silent, which is worse than the short videos were.

Writing 1,900 replacement scripts is not the answer - the existing ones are
sound, they are simply too short. Each already carries the thing that is hard to
produce: a title that overturns something the viewer believes. So this expands
what is there rather than inventing more. One request carries several scripts,
so a run repairs far more than a generating run could, and the subjects the
channels already rank for are kept.

The first live run repaired nothing at all. Every batch came back as:

    batch failed: Expecting ',' delimiter: line 71 column 4 (char 3334)

which was my fault - the prompt asked for captions split with a backslash-n and
the model obliged with a real newline inside a JSON string, which is not legal
JSON, and one character killed a batch of eight finished scripts. Captions are
now requested as lists of lines, so there is no escape sequence to get wrong,
and the parser repairs raw newlines anyway before giving up.

Rules it holds to:
  - the title, tags and image prompt are never touched, so a script that has
    already been published stays recognisable and the ledger stays valid
  - published scripts are skipped entirely; there is no point paying for a
    rewrite of something that cannot go out again
  - anything that comes back failing grow.valid() leaves the original in place
  - the bank is written after every batch, so a run that is cut short keeps
    everything it finished

    python tools/expand.py us --limit 400
    python tools/expand.py            # all three, budget split evenly

Env: OWNER_GEMINI_KEY, GEMINI_REQUEST_BUDGET (shared with the live app).
"""
import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import grow  # noqa: E402  - reuses the model discovery, budget and validator

try:
    import formula
except Exception as _e:      # a ranking helper must never stop the repair
    formula = None
    print("formula ranking unavailable (%s)" % str(_e)[:60])

# Five fits inside the 8k output token ceiling with room to spare. Eight came
# back truncated often enough to lose whole batches.
PER_REQUEST = 5


def spoken(d):
    return sum(len((p or "").replace("\n", " ").split()) for p in (d.get("phrases") or []))


def too_short(d):
    return spoken(d) < 78 or len(d.get("phrases") or []) < 10


VOICE = {
    "us": "short motivation, spoken to one person, no shouting",
    "fun": "surprising true things, mostly about the viewer's own body",
    "history": "history for a US audience, told with dates and numbers",
}

# The brief used to be pasted in here. That made the prompt 7,602 characters
# with the actual instruction sitting at character 5,294, underneath a 4,892
# character description of the channel - and the model duly ignored it: forty-two
# rewrites in one run came back with five to nine captions when eleven to
# thirteen were asked for. The brief's job is choosing subjects, which matters
# in grow.py where new scripts are written. Here the subject is already fixed
# and only the length and shape are in question, so the prompt says that and
# almost nothing else.
PROMPT = """Rewrite each of these {n} YouTube Shorts scripts LONGER.

Channel: {name} - {voice}.

THE ONLY THING THAT MATTERS: each rewrite must have EXACTLY 12 captions and
between 100 and 115 spoken words in total. The scripts you are given have 7 or 8
captions and about 45 words. That is a twelve-second video and the channel
rejects it. Count your captions and your words before you answer.

Anything under 78 words is thrown away. Rewrites keep coming back at 70, 75 and
77 words and every one of them is discarded over two or three words, so aim for
105 and never write fewer than 100.

Each caption is a list of two short strings, one per line on screen, and each
caption totals 8 to 10 words. Twelve captions of nine words is 108 words.
Example caption: ["Your stomach acid can", "dissolve solid metal."]

Use these twelve captions like this:
   1-2   the belief the viewer already holds - straight in, no greeting
   3-5   that belief is wrong - do NOT explain yet, hold it
   6-8   why it is wrong, with a number or date they could look up
   9-11  what it MEANS for them - a consequence they had not thought of
   12    a question worth arguing with, not "what do you think"

Captions 9 to 11 are missing from every script below. They state a fact,
explain it, and stop, which is why viewers say these are boring.

Keep "title", "tags" and "img" EXACTLY as given. Rewrite "narration" to match,
80 to 120 words. If the title contains a number, the captions MUST say that
number. Never use a double quote inside any text - it breaks the JSON.

Scripts:
{items}

Return ONLY a JSON array of {n} objects with keys title, tags, img, narration,
phrases. Each "phrases" must contain EXACTLY 12 entries. No commentary."""


def split_objects(body):
    """Yield each top-level {...} in the array text.

    Brace depth, with a rough string skip. Rough is the point: this runs when
    strict parsing has already failed, and it only has to find the boundaries.
    """
    depth, start, instring, escaped = 0, None, False, False
    for i, ch in enumerate(body):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            instring = not instring
            continue
        if instring:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                yield body[start:i + 1]
                start = None


def parse_lenient(raw):
    """grow.parse_array, but survives a real newline inside a string.

    The model is asked for captions as lists of lines precisely so this cannot
    happen. It happened anyway on every request of the first live run, and a
    single stray newline destroyed a batch of finished scripts along with the
    quota that bought them.
    """
    try:
        return grow.parse_array(raw)
    except Exception:
        pass
    i, j = raw.find("["), raw.rfind("]")
    if i < 0 or j < 0:
        raise ValueError("no JSON array in response")
    out, instring, escaped = [], False, False
    for ch in raw[i:j + 1]:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            instring = not instring
        if instring and ch == "\n":
            out.append("\\n")          # the bug, escaped the way it should be
            continue
        if instring and ch == "\r":
            continue
        out.append(ch)
    repaired = "".join(out)
    try:
        return json.loads(repaired)
    except Exception:
        pass
    # Still broken - usually a stray double quote inside a caption. Take the
    # objects that do parse rather than losing the batch: one malformed script
    # should cost one script, not the four beside it.
    got = []
    for chunk in split_objects(repaired):
        try:
            got.append(json.loads(chunk))
        except Exception:
            continue
    if not got:
        raise ValueError("no usable objects in response")
    print("  recovered %d objects from a malformed response" % len(got), flush=True)
    return got


MAX_CAPTIONS = 14


def join_lines(d):
    """Captions arrive as lists of lines; the renderer wants one string each.

    The model is asked for eleven to thirteen captions, each a list of one or
    two on-screen lines. It frequently returns the lines flattened instead -
    twenty-two short strings rather than eleven pairs - and the validator threw
    the whole rewrite away as "phrases count 22". The content was right; only
    the nesting was lost. Pairing them back up recovers the script.
    """
    caps = d.get("phrases")
    if not isinstance(caps, list):
        return d
    caps = ["\n".join(str(x) for x in c) if isinstance(c, list) else c
            for c in caps]

    if len(caps) > MAX_CAPTIONS and all(isinstance(c, str) for c in caps):
        # Only if they really are single lines. Pairing genuine two-line
        # captions would produce four-line ones that overflow the frame.
        if all("\n" not in c and len(c) <= 34 for c in caps):
            caps = ["\n".join(caps[i:i + 2]) for i in range(0, len(caps), 2)]
            print("  re-paired %d flattened lines into %d captions"
                  % (len(d["phrases"]), len(caps)), flush=True)

    d["phrases"] = caps
    return d


def runway(key):
    """How many scripts this channel could still publish today.

    Not the bank size and not the count that clears the floor - the ones that
    clear it AND have never gone out. That is the number that decides whether a
    channel goes silent, so it is the number the repair order follows.
    """
    cfg = grow.CHANNELS[key]
    try:
        bank = json.load(io.open(os.path.join(ROOT, cfg["dir"], cfg["bank"]),
                                 encoding="utf-8"))
    except Exception:
        return 0
    published = load_published(key)
    return sum(1 for d in bank
               if not too_short(d)
               and grow.norm_title(d["title"]) not in published)


def load_published(key):
    p = os.path.join(ROOT, grow.CHANNELS[key]["dir"], "published_%s.json" % key)
    try:
        return set(grow.norm_title(t) for t in json.load(io.open(p, encoding="utf-8")))
    except Exception:
        return set()


def expand(key, limit, dry, gkey):
    cfg = grow.CHANNELS[key]
    path = os.path.join(ROOT, cfg["dir"], cfg["bank"])
    bank = json.load(io.open(path, encoding="utf-8"))
    published = load_published(key)

    before = sum(1 for d in bank if not too_short(d))
    todo = [i for i, d in enumerate(bank)
            if too_short(d) and grow.norm_title(d["title"]) not in published]
    # Spend the budget on the scripts this channel actually converts on. The
    # rewrite keeps the title, so lengthening a subject that already failed
    # buys a longer version of a video nobody responded to.
    if formula is not None:
        todo.sort(key=lambda i: -formula.score(key, bank[i]))
        best = formula.score(key, bank[todo[0]]) if todo else 0
        worst = formula.score(key, bank[todo[-1]]) if todo else 0
        print("  ordered by fit to what this channel converts on "
              "(best %d, worst %d)" % (best, worst), flush=True)
    print("%s: %d scripts, %d already clear 30s, %d unpublished and too short"
          % (key, len(bank), before, len(todo)), flush=True)
    if not todo:
        return 0

    todo = todo[:limit]
    fixed = 0
    for start in range(0, len(todo), PER_REQUEST):
        idxs = todo[start:start + PER_REQUEST]
        items = json.dumps([bank[i] for i in idxs], ensure_ascii=False, indent=1)
        prompt = PROMPT.format(name=cfg["name"], voice=VOICE[key],
                               items=items, n=len(idxs))
        try:
            out = parse_lenient(grow.gemini(prompt, gkey))
        except grow.BudgetSpent as e:
            print("  stopping: %s" % e, flush=True)
            break
        except Exception as e:
            print("  batch failed: %s" % str(e)[:180], flush=True)
            time.sleep(4)
            continue

        # The model is asked to return them in order, but it is not trustworthy
        # about that, so match on the title it was told to keep unchanged.
        by_title = {}
        for d in out:
            if isinstance(d, dict) and isinstance(d.get("title"), str):
                by_title[grow.norm_title(d["title"])] = d

        for i in idxs:
            orig = bank[i]
            cand = by_title.get(grow.norm_title(orig["title"]))
            if cand is None:
                continue
            cand = join_lines(dict(cand))
            # Keep the parts that must not drift, whatever came back.
            cand = {"title": orig["title"], "tags": orig["tags"], "img": orig["img"],
                    "narration": cand.get("narration"), "phrases": cand.get("phrases")}
            why = grow.valid(cand)
            if why:
                print("  keep original (%s)" % why, flush=True)
                continue
            bank[i] = cand
            fixed += 1

        # Written after every batch. A run killed by the job timeout once threw
        # away 113 finished scripts because the only write was at the end.
        if fixed and not dry:
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                json.dumps(bank, ensure_ascii=False, indent=1))
        print("  %d/%d repaired so far" % (fixed, len(todo)), flush=True)
        time.sleep(2)

    after = sum(1 for d in bank if not too_short(d))
    print("%s: clears 30s %d -> %d (+%d)%s"
          % (key, before, after, fixed, " [dry]" if dry else ""), flush=True)
    return fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channels", nargs="*", default=list(grow.CHANNELS))
    ap.add_argument("--limit", type=int, default=400,
                    help="most scripts to repair per channel this run")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    gkey = (os.environ.get("OWNER_GEMINI_KEY") or "").strip()
    if not gkey:
        print("no OWNER_GEMINI_KEY - nothing to do")
        return 0

    picked = [k for k in (a.channels or list(grow.CHANNELS)) if k in grow.CHANNELS]
    # Neediest first. The free tier is spent long before the budget is: every
    # run so far stopped with "rate limited on 3 requests in a row" partway
    # through the first channel, so whichever channel was named first got all
    # fifteen repairs and the other two got none, run after run. Rise reached
    # 47 usable scripts that way while History stayed at 18.
    picked.sort(key=lambda k: runway(k))
    if len(picked) > 1:
        print("order by need: %s" % ", ".join(
            "%s(%d usable)" % (k, runway(k)) for k in picked), flush=True)
    # Split the request budget evenly, otherwise the first channel spends the
    # whole allowance and the other two stay stuck at a day of runway.
    share = max(1, grow.REQUEST_BUDGET // max(1, len(picked)))
    total = 0
    for n, k in enumerate(picked):
        grow._cap = share * (n + 1)
        try:
            total += expand(k, a.limit, a.dry, gkey)
        except Exception as e:
            print("%s FAILED: %s" % (k, str(e)[:200]), flush=True)
    print("TOTAL REPAIRED %d (budget %d requests)" % (total, grow.REQUEST_BUDGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
