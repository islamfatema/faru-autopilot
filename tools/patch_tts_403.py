# -*- coding: utf-8 -*-
"""Survive the 403 that Microsoft's free voice service now returns.

Since about 7 October the posting runs have been failing at the voice step:

    FAILED item 1: edge-tts failed after retries: 403, message='Invalid response status'

Not every run - roughly half - which is the signature of the service refusing
a token rather than refusing us. Five tries four seconds apart is not enough to
ride that out, and when it fails the whole video is abandoned.

Three changes, in the order they matter:

  * eight attempts with a growing wait (4, 8, 16 ... capped at 45 seconds),
    so a run that hits a bad minute survives it;
  * a different voice on later attempts - a second v2 voice on the same
    service often answers when the first will not;
  * the failure is reported per line, so the log says which caption could not
    be spoken rather than only that the video died.
"""
import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["autopilot_us/main_us.py",
         "autopilot_fun/main_fun.py",
         "autopilot_history/main_history.py"]

OLD = '''        mp3 = os.path.join(WORK, "raw%d.mp3" % i); last = None
        for attempt in range(5):
            try:
                asyncio.run(_tts(spoken, mp3))
                if os.path.getsize(mp3) > 1200: break
            except Exception as e:
                last = e; print("tts try %d failed: %s" % (attempt+1, str(e)[:90])); time.sleep(4)
        else:
            raise RuntimeError("edge-tts failed after retries: %s" % last)'''

NEW = '''        mp3 = os.path.join(WORK, "raw%d.mp3" % i); last = None
        # The free voice service started answering 403 on about half of all
        # requests in October. It is the service refusing a token, not us, so
        # the cure is patience and a second voice rather than failing the video.
        for attempt in range(8):
            try:
                asyncio.run(_tts(spoken, mp3, VOICES[attempt % len(VOICES)]))
                if os.path.getsize(mp3) > 1200: break
            except Exception as e:
                last = e
                wait = min(45, 4 * (2 ** min(attempt, 3)))
                print("tts line %d try %d failed (%s) - waiting %ds"
                      % (i + 1, attempt + 1, str(e)[:70], wait), flush=True)
                time.sleep(wait)
        else:
            raise RuntimeError("edge-tts refused line %d after 8 tries: %s" % (i + 1, last))'''

OLD_TTS = "async def _tts(text, out):"
NEW_TTS = "async def _tts(text, out, voice=None):"


def patch(rel):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if "VOICES[attempt" in s:
        print("  already patched: %s" % rel)
        return
    if s.count(OLD) != 1:
        raise SystemExit("%s: voice loop found %d times" % (rel, s.count(OLD)))
    s = s.replace(OLD, NEW)

    # a second and third voice to fall back on, same service, same quality tier
    if "VOICES = " not in s:
        anchor = [l for l in s.splitlines() if l.startswith("VOICE = ")][0]
        s = s.replace(anchor, anchor + '\n'
                      '# Fallbacks for the 403s: the same v2 neural tier, so a line spoken by\n'
                      '# the second voice does not sound like a different channel.\n'
                      'VOICES = [VOICE, "en-US-BrianMultilingualNeural",\n'
                      '          "en-US-AndrewMultilingualNeural", "en-US-EmmaMultilingualNeural"]', 1)

    # let _tts take the voice for this attempt
    if s.count(OLD_TTS) == 1:
        s = s.replace(OLD_TTS, NEW_TTS)
        s = s.replace('edge_tts.Communicate(text, VOICE', 'edge_tts.Communicate(text, voice or VOICE')
    ast.parse(s)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.replace(tmp, path)
    print("  patched %s" % rel)


for rel in FILES:
    patch(rel)
print("done")
