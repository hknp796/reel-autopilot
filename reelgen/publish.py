"""Post the next approved Reel.

    python -m reelgen.publish              # build + post the oldest reels/*.json with "status": "approved"
    python -m reelgen.publish --id 002-slow-website
    python -m reelgen.publish --dry-run    # build only, post nothing

After a successful post the spec is marked "posted" with the media id, permalink and time,
so it is never posted twice. The GitHub workflow commits that change back to the repo.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .build import build

REELS = Path(__file__).resolve().parent.parent / "reels"


def next_approved(only_id=None):
    for p in sorted(REELS.glob("*.json")):
        if only_id and p.stem != only_id:
            continue
        spec = json.loads(p.read_text())
        if spec.get("status") == "approved":
            return p, spec
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    path, spec = next_approved(a.id)
    if not path:
        print("Nothing approved to post. Set \"status\": \"approved\" in a reels/*.json file.")
        return 0

    print(f"Next up: {path.stem}")
    video = build(path, Path("out") / f"{path.stem}.mp4")
    if a.dry_run:
        print("Dry run: built, not posted.")
        return 0

    from .instagram import Instagram
    ig = Instagram()
    media_id = ig.publish_reel(video, spec["caption"])
    link = ig.permalink(media_id)
    spec.update(status="posted", media_id=media_id, permalink=link,
                posted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    print(f"Posted {path.stem}: {link or media_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
