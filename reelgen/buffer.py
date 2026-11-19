"""Post a Reel through Buffer's GraphQL API (https://developers.buffer.com).

Env: BUFFER_API_KEY (Buffer → Settings → API), optional BUFFER_CHANNEL_ID.
Without BUFFER_CHANNEL_ID the Instagram channel is found automatically; that needs
exactly one connected Instagram channel in your Buffer account.

    python -m reelgen.buffer channels     # list your Buffer channels and their ids
"""
import os
import sys
import time

import requests

API = "https://api.buffer.com"


class BufferError(RuntimeError):
    pass


class Buffer:
    def __init__(self, api_key=None):
        self.key = api_key or os.environ["BUFFER_API_KEY"]

    def gql(self, query, variables=None):
        r = requests.post(API, json={"query": query, "variables": variables or {}}, timeout=60,
                          headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        try:
            data = r.json()
        except ValueError:
            raise BufferError(f"Buffer API {r.status_code}: {r.text[:300]}")
        if r.status_code >= 400 or data.get("errors"):
            raise BufferError(f"Buffer API {r.status_code}: {data.get('errors') or data}")
        return data["data"]

    def channels(self):
        orgs = self.gql("query { account { organizations { id name } } }")["account"]["organizations"]
        out = []
        for org in orgs:
            q = """query($input: ChannelsInput!) {
                     channels(input: $input) { id service name displayName isDisconnected type } }"""
            for c in self.gql(q, {"input": {"organizationId": org["id"]}})["channels"]:
                out.append({**c, "organization": org["name"]})
        return out

    def instagram_channel_id(self):
        if os.environ.get("BUFFER_CHANNEL_ID"):
            return os.environ["BUFFER_CHANNEL_ID"]
        ig = [c for c in self.channels() if str(c["service"]).lower() == "instagram"]
        if len(ig) != 1:
            names = ", ".join(f"{c['name']} ({c['id']})" for c in ig) or "none"
            raise BufferError(f"Expected one Instagram channel in Buffer, found: {names}. "
                              "Set the BUFFER_CHANNEL_ID variable to pick one.")
        if ig[0]["isDisconnected"]:
            raise BufferError(f"Instagram channel {ig[0]['name']} is disconnected in Buffer. Reconnect it there.")
        return ig[0]["id"]

    def post_reel_now(self, channel_id, video_url, caption, cover_ms=None):
        video = {"url": video_url}
        if cover_ms is not None:
            video["metadata"] = {"thumbnailOffset": int(cover_ms)}
        q = """mutation($input: CreatePostInput!) {
                 createPost(input: $input) {
                   __typename
                   ... on PostActionSuccess { post { id status } }
                   ... on MutationError { message }
                 } }"""
        res = self.gql(q, {"input": {
            "channelId": channel_id,
            "text": caption,
            "schedulingType": "automatic",
            "mode": "shareNow",
            "assets": [{"video": video}],
            "metadata": {"instagram": {"type": "reel", "shouldShareToFeed": True}},
        }})["createPost"]
        if res["__typename"] != "PostActionSuccess":
            raise BufferError(f"createPost failed ({res['__typename']}): {res.get('message')}")
        return res["post"]["id"]

    def post_status(self, post_id):
        q = """query($input: PostInput!) {
                 post(input: $input) { id status sentAt externalLink error { message rawError supportUrl } } }"""
        return self.gql(q, {"input": {"id": post_id}})["post"]

    def wait_until_sent(self, post_id, timeout_s=900, every_s=20):
        """Buffer accepts the post at once but fetches and publishes the video afterwards,
        so success only counts once the post's status is `sent`."""
        deadline = time.time() + timeout_s
        while True:
            p = self.post_status(post_id)
            print(f"  buffer post {post_id}: {p['status']}", flush=True)
            if p["status"] == "sent":
                return p
            if p["status"] == "error":
                e = p.get("error") or {}
                raise BufferError(f"Buffer could not publish: {e.get('message')} {e.get('rawError') or ''}".strip())
            if time.time() > deadline:
                return p  # still sending: caller records it so it isn't posted twice
            time.sleep(every_s)


def main():
    if sys.argv[1:] == ["channels"]:
        for c in Buffer().channels():
            flag = "  (disconnected)" if c["isDisconnected"] else ""
            print(f"{c['service']:<12} {c['id']}  {c['displayName'] or c['name']}  [{c['organization']}]{flag}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
