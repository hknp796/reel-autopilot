"""Publish a Reel through Meta's Instagram API.

Two ways in, picked with IG_LOGIN:

  instagram (default)  Instagram API with Instagram Login. No Facebook Page needed. Meta only
                       documents video uploads by public URL here, so the MP4 is first put in a
                       public Supabase Storage bucket (see hosting below) and removed after.
  facebook             Instagram API with Facebook Login for Business (Instagram account linked
                       to a Facebook Page, Page access token). Uploads the file directly to
                       rupload.facebook.com, so no hosting is needed.

Env: IG_USER_ID, IG_ACCESS_TOKEN, IG_LOGIN, IG_API_VERSION (default v26.0)
     for IG_LOGIN=instagram: SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET (default "reels")
"""
import os
import time
from pathlib import Path

import requests

API_VERSION = os.environ.get("IG_API_VERSION", "v26.0")
TIMEOUT = 60


class InstagramError(RuntimeError):
    pass


def _check(r):
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:500]}
    if r.status_code >= 400 or (isinstance(data, dict) and "error" in data):
        raise InstagramError(f"{r.request.method} {r.url.split('?')[0]} -> {r.status_code}: {data}")
    return data


class Instagram:
    def __init__(self, user_id=None, token=None, login=None):
        self.user_id = user_id or os.environ["IG_USER_ID"]
        self.token = token or os.environ["IG_ACCESS_TOKEN"]
        self.login = (login or os.environ.get("IG_LOGIN", "instagram")).lower()
        host = "graph.instagram.com" if self.login == "instagram" else "graph.facebook.com"
        self.base = f"https://{host}/{API_VERSION}"

    def _post(self, path, data):
        return _check(requests.post(f"{self.base}/{path}", data={**data, "access_token": self.token}, timeout=TIMEOUT))

    def _get(self, path, params):
        return _check(requests.get(f"{self.base}/{path}", params={**params, "access_token": self.token}, timeout=TIMEOUT))

    # --- steps ---
    def create_container_from_url(self, video_url, caption):
        return self._post(f"{self.user_id}/media", {
            "media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"})["id"]

    def create_container_resumable(self, caption):
        return self._post(f"{self.user_id}/media", {
            "media_type": "REELS", "upload_type": "resumable", "caption": caption, "share_to_feed": "true"})["id"]

    def upload_file(self, container_id, path):
        data = Path(path).read_bytes()
        r = requests.post(f"https://rupload.facebook.com/ig-api-upload/{API_VERSION}/{container_id}",
                          headers={"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(len(data))},
                          data=data, timeout=600)
        return _check(r)

    def wait_until_ready(self, container_id, timeout_s=600, every_s=15):
        deadline = time.time() + timeout_s
        while True:
            info = self._get(container_id, {"fields": "status_code,status"})
            code = info.get("status_code")
            print(f"  container {container_id}: {code}", flush=True)
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise InstagramError(f"container {container_id} {code}: {info.get('status')}")
            if time.time() > deadline:
                raise InstagramError(f"container {container_id} still {code} after {timeout_s}s")
            time.sleep(every_s)

    def publish_container(self, container_id):
        return self._post(f"{self.user_id}/media_publish", {"creation_id": container_id})["id"]

    def permalink(self, media_id):
        try:
            return self._get(media_id, {"fields": "permalink"}).get("permalink")
        except InstagramError:
            return None

    def publishing_quota(self):
        return self._get(f"{self.user_id}/content_publishing_limit", {"fields": "quota_usage,config"})

    # --- whole flow ---
    def publish_reel(self, video_path, caption):
        if self.login == "facebook":
            cid = self.create_container_resumable(caption)
            print(f"  uploading {Path(video_path).name} to rupload ...", flush=True)
            self.upload_file(cid, video_path)
            self.wait_until_ready(cid)
            return self.publish_container(cid)

        host = SupabaseHost()
        url = host.upload(video_path)
        try:
            cid = self.create_container_from_url(url, caption)
            self.wait_until_ready(cid)
            return self.publish_container(cid)
        finally:
            host.delete(video_path)


class SupabaseHost:
    """Public Supabase Storage bucket used only while Instagram fetches the video."""

    def __init__(self):
        self.url = os.environ["SUPABASE_URL"].rstrip("/")
        self.key = os.environ["SUPABASE_SERVICE_KEY"]
        self.bucket = os.environ.get("SUPABASE_BUCKET", "reels")

    def _obj(self, path):
        return f"{self.url}/storage/v1/object/{self.bucket}/{Path(path).name}"

    def upload(self, path):
        r = requests.post(self._obj(path), data=Path(path).read_bytes(), timeout=300, headers={
            "Authorization": f"Bearer {self.key}", "apikey": self.key,
            "Content-Type": "video/mp4", "x-upsert": "true"})
        _check(r)
        public = f"{self.url}/storage/v1/object/public/{self.bucket}/{Path(path).name}"
        print(f"  hosted at {public}", flush=True)
        return public

    def delete(self, path):
        try:
            requests.delete(self._obj(path), timeout=60,
                            headers={"Authorization": f"Bearer {self.key}", "apikey": self.key})
        except requests.RequestException as e:
            print(f"  warning: could not delete hosted file: {e}")
