"""Build a Reel MP4 from a spec.

    python -m reelgen.build reels/001-invisible-on-google.json            # -> out/001-invisible-on-google.mp4
    python -m reelgen.build reels/001-invisible-on-google.json --stills   # contact sheet only, no voice
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import soundfile as sf
from PIL import Image

from .render import FPS, H, W, BG, frame, min_beats

ENC = ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def run(cmd):
    subprocess.run(cmd, check=True)


def render_scene(scene, path, first, last):
    tmp = path.with_suffix(".tmp.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", *ENC, str(tmp)], stdin=subprocess.PIPE)
    dur = scene["duration"]
    blank = Image.new("RGB", (W, H), BG)
    for i in range(int(round(dur * FPS))):
        t = i / FPS
        im = frame(scene, t, scene["beats"])
        a = 1.0
        if not first:
            a = min(a, t / 0.12)
        if not last:
            a = min(a, (dur - t) / 0.15)
        if a < 1:
            im = Image.blend(blank, im, max(0.0, a))
        p.stdin.write(im.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        sys.exit(f"ffmpeg failed on {path.name}")
    os.replace(tmp, path)


def build(spec_path, out_path):
    spec = json.loads(Path(spec_path).read_text())
    from .voice import SR, timeline
    scenes, audio = timeline(spec)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        parts = []
        for i, s in enumerate(scenes):
            part = td / f"s{i}.mp4"
            render_scene(s, part, i == 0, i == len(scenes) - 1)
            parts.append(part)
        (td / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(td / "list.txt"),
             "-c", "copy", str(td / "silent.mp4")])
        sf.write(td / "vo.wav", audio, SR)
        tmp = out_path.with_suffix(".tmp.mp4")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(td / "silent.mp4"), "-i", str(td / "vo.wav"),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
             "-shortest", "-movflags", "+faststart", str(tmp)])
        os.replace(tmp, out_path)
    total = sum(s["duration"] for s in scenes)
    print(f"built {out_path} ({total:.1f}s)")
    return out_path


def stills(spec_path, out_path):
    """One frame per scene at its fullest moment, without generating voice (fast layout check)."""
    spec = json.loads(Path(spec_path).read_text())
    frames = []
    for s in spec["scenes"]:
        beats = min_beats(s)
        # space beats ~1s apart, as a voice would
        beats = [max(b, (beats_prev + 1.0) if i else b) for i, (b, beats_prev) in
                 enumerate(zip(beats, [0] + beats[:-1]))]
        frames.append(frame(s, beats[-1] + 2.0, beats).resize((360, 640)))
    sheet = Image.new("RGB", (360 * min(3, len(frames)), 640 * ((len(frames) + 2) // 3)), BG)
    for i, f in enumerate(frames):
        sheet.paste(f, ((i % 3) * 360, (i // 3) * 640))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=88)
    print(f"wrote {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("-o", "--out")
    ap.add_argument("--stills", action="store_true", help="contact sheet only (no voice, fast)")
    a = ap.parse_args()
    stem = Path(a.spec).stem
    if a.stills:
        stills(a.spec, a.out or f"out/{stem}-stills.jpg")
    else:
        build(a.spec, a.out or f"out/{stem}.mp4")


if __name__ == "__main__":
    main()
