# -*- coding: utf-8 -*-
"""A voice that cannot be switched off by somebody else's server.

Since 7 October Microsoft's free endpoint has answered 403 to every request
from the runners - eight tries, four voices, all refused - and a video with no
narration is not a video. Everything else in this project survived that day;
the channels did not.

Piper runs the model on the runner itself: no account, no key, no rate limit,
nothing to refuse us. It is a smaller model than the v2 neural voices, so it
is the fallback and not the default - edge-tts is tried first every time, and
this speaks only when that fails.

    from tools import localvoice
    localvoice.speak("the first webcam watched a coffee pot", "line1.wav")

The voice model is ~60 MB, downloaded once per run into _voice/ and reused for
every line after that.
"""
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VOICE_DIR = os.path.join(ROOT, "_voice")
# A clear, unhurried American male - closest of the free Piper voices to the
# narration these channels already use.
MODEL = "en_US-ryan-medium.onnx"
BASE = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/"
        "ryan/medium/")


def _fetch(name, dst):
    url = BASE + name + "?download=true"
    req = urllib.request.Request(url, headers={"User-Agent": "faru-autopilot/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return dst


def model_path():
    """The model file, downloaded on first use."""
    os.makedirs(VOICE_DIR, exist_ok=True)
    onnx = os.path.join(VOICE_DIR, MODEL)
    cfg = onnx + ".json"
    if not os.path.exists(onnx) or os.path.getsize(onnx) < 1000000:
        print("  downloading the local voice model (~60 MB, once)", flush=True)
        _fetch(MODEL, onnx)
    if not os.path.exists(cfg):
        _fetch(MODEL + ".json", cfg)
    return onnx


_VOICE = None


def speak(text, out_wav):
    """Write one spoken line as a wav. True if it worked."""
    global _VOICE
    try:
        import wave
        from piper import PiperVoice
        if _VOICE is None:
            _VOICE = PiperVoice.load(model_path())
        with wave.open(out_wav, "wb") as w:
            # the API gained and lost names across versions; try each shape
            if hasattr(_VOICE, "synthesize_wav"):
                _VOICE.synthesize_wav(text, w)
            else:
                _VOICE.synthesize(text, w)
        ok = os.path.exists(out_wav) and os.path.getsize(out_wav) > 2000
        if ok:
            print("  spoken locally (piper): %s" % text[:48], flush=True)
        return ok
    except Exception as e:
        print("  local voice failed: %s" % str(e)[:120], flush=True)
        return False


if __name__ == "__main__":
    out = sys.argv[2] if len(sys.argv) > 2 else "piper_test.wav"
    print("ok" if speak(sys.argv[1] if len(sys.argv) > 1 else
                        "This animal is older than trees.", out) else "failed")
