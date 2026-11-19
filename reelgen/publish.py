"""Post the next approved Reel: build it, host it on GitHub Pages, publish it with Buffer.

The publish workflow runs this in two halves around the GitHub Pages deploy:

    python -m reelgen.publish build [--id ID]           # build next approved Reel into out/site/
    python -m reelgen.publish post --id ID --base-url URL  # post out/site/ID.mp4 (served at URL) via Buffer

    python -m reelgen.publish build --id 002-slow-website   # local: just build it

After Buffer reports the post as sent, the spec is marked "posted" with the Instagram link,
so it is never posted twice. If Buffer is still processing when we stop waiting, it's marked
"submitted" (never re-posted; check it in Buffer). If Buffer reports an error it's marked
"failed" with the reason; set it back to "approved" to try again.
"""
import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .build import build

ROOT = Path(__file__).resolve().parent.parent
REELS = ROOT / "reels"
SITE = Path("out") / "site"


def next_approved(only_id=None):
    for p in sorted(REELS.glob("*.json")):
        if only_id and p.stem != only_id:
            continue
        spec = json.loads(p.read_text())
        if spec.get("status") == "approved":
            return p, spec
    return None, None


def set_output(key, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"{key}={value}\n")


def cmd_build(a):
    path, spec = next_approved(a.id)
    if not path:
        msg = f"Reel {a.id} is not approved." if a.id else "Nothing approved to post."
        print(msg + ' Set "status": "approved" in a reels/*.json file.')
        set_output("reel", "")
        return 0
    print(f"Next up: {path.stem}")
    video = build(path, Path("out") / f"{path.stem}.mp4")
    SITE.mkdir(parents=True, exist_ok=True)
    shutil.copy(video, SITE / video.name)
    (SITE / "index.html").write_text("<!doctype html><title>reel-autopilot</title>Media for scheduled Reels.\n")
    set_output("reel", path.stem)
    return 0


def wait_for_url(url, timeout_s=300):
    """GitHub Pages can take a minute to serve a fresh deploy everywhere."""
    deadline = time.time() + timeout_s
    while True:
        try:
            r = requests.head(url, timeout=30, allow_redirects=False)
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and ctype.startswith("video/mp4"):
                print(f"  live: {url} ({int(r.headers.get('content-length', 0)) // 1024} KB, {ctype})")
                return
            print(f"  waiting for {url}: {r.status_code} {ctype}", flush=True)
        except requests.RequestException as e:
            print(f"  waiting for {url}: {e}", flush=True)
        if time.time() > deadline:
            raise RuntimeError(f"{url} never became available as video/mp4")
        time.sleep(10)


def cmd_post(a):
    path = REELS / f"{a.id}.json"
    spec = json.loads(path.read_text())
    if spec.get("status") != "approved":
        sys.exit(f"{a.id} is {spec.get('status')}, not approved; not posting.")
    url = a.base_url.rstrip("/") + f"/{a.id}.mp4"
    wait_for_url(url)

    from .buffer import Buffer
    buf = Buffer()
    channel = buf.instagram_channel_id()
    post_id = buf.post_reel_now(channel, url, spec["caption"], spec.get("cover_ms", 2600))
    print(f"  sent to Buffer as post {post_id}", flush=True)
    # Record the Buffer id straight away, so a later failure can never post this twice.
    spec.pop("error", None)
    spec.update(status="submitted", buffer_post_id=post_id)
    path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

    from .buffer import BufferError
    try:
        p = buf.wait_until_sent(post_id)
    except BufferError as e:
        spec.update(status="failed", error=str(e))
        path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
        print(f"::error::{a.id}: {e}. Fix it, set status back to approved to retry.")
        return 1
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if p["status"] == "sent":
        spec.update(status="posted", permalink=p.get("externalLink"), posted_at=p.get("sentAt") or now)
        print(f"Posted {a.id}: {p.get('externalLink') or post_id}")
    else:
        spec.update(submitted_at=now)
        print(f"::warning::{a.id} was handed to Buffer but is still '{p['status']}'. Check it in Buffer.")
    path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--id")
    p = sub.add_parser("post")
    p.add_argument("--id", required=True)
    p.add_argument("--base-url", required=True)
    a = ap.parse_args()
    return cmd_build(a) if a.cmd == "build" else cmd_post(a)


if __name__ == "__main__":
    sys.exit(main())
