"""Voiceover with Kokoro (open-source TTS, runs on CPU) and the timeline it implies.

Each scene's `say` list holds one line per beat. A line starts no earlier than the beat's
minimum time and no sooner than 0.18 s after the previous line ends; the beat (the moment
its text appears) is set to when the line starts. An empty line ("") is a silent beat that
lands 0.35 s after the previous one. Scenes stretch to fit their lines.
"""
import os
import urllib.request
from pathlib import Path

import numpy as np

from .render import min_beats

SR = 24000
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODEL_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
MIN_SCENE = {"statement": 3.2, "search": 4.4, "list": 3.2, "rank_up": 3.4, "cta": 3.6}

_kokoro = None


def model_dir():
    d = Path(os.environ.get("KOKORO_DIR", Path(__file__).resolve().parent.parent / "models"))
    d.mkdir(parents=True, exist_ok=True)
    for f in MODEL_FILES:
        if not (d / f).exists():
            print(f"downloading {f} ...", flush=True)
            urllib.request.urlretrieve(MODEL_URL + f, d / f)
    return d


def tts(text, voice, speed):
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        d = model_dir()
        _kokoro = Kokoro(str(d / MODEL_FILES[0]), str(d / MODEL_FILES[1]))
    a, sr = _kokoro.create(text, voice=voice, speed=speed, lang="en-us")
    assert sr == SR
    idx = np.where(np.abs(a) > 0.005)[0]
    return a[max(0, idx[0] - 200): idx[-1] + 1200] if len(idx) else a


def timeline(spec):
    """Returns (scenes_with_timing, audio). Each scene gets 'beats' and 'duration'."""
    voice = spec.get("voice", "am_michael")
    speed = spec.get("speed", 1.08)
    out, clips = [], []
    for si, scene in enumerate(spec["scenes"]):
        mins = min_beats(scene)
        says = scene.get("say", [])
        if len(says) > len(mins):
            raise ValueError(f"scene {si} ({scene['type']}) has {len(says)} say lines but only {len(mins)} beats")
        beats, cur, placed = [], 0.0, []
        for i, m in enumerate(mins):
            text = says[i] if i < len(says) else ""
            if text.strip():
                start = max(m, cur + (0.18 if i else 0))
                a = tts(text, voice, speed)
                placed.append((start, a))
                cur = start + len(a) / SR
            else:  # silent beat: shortly after the previous beat
                start = max(m, (beats[-1] + 0.35) if beats else m)
                cur = max(cur, start)
            beats.append(start)
        last = si == len(spec["scenes"]) - 1
        dur = max(MIN_SCENE[scene["type"]], cur + (0.8 if last else 0.35))
        out.append({**scene, "beats": beats, "duration": round(dur * 30) / 30})
        clips.append(placed)

    total = sum(s["duration"] for s in out)
    track = np.zeros(int(total * SR) + SR, dtype=np.float32)
    off = 0.0
    for s, placed in zip(out, clips):
        for st, a in placed:
            i = int((off + st) * SR)
            track[i:i + len(a)] += a
        off += s["duration"]
    track = track[: int(total * SR)]
    peak = np.abs(track).max()
    if peak > 0:
        track = track / peak * 0.89
    return out, track
