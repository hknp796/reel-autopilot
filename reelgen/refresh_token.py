"""Renew a long-lived Instagram Login token (they last 60 days; renew any time after 24 hours).

Prints the new token to stdout and nothing else, so the workflow can pipe it into
`gh secret set IG_ACCESS_TOKEN`. Facebook Login Page tokens made from a long-lived user
token don't expire, so this is only needed for IG_LOGIN=instagram.
"""
import os
import sys

import requests


def main():
    token = os.environ["IG_ACCESS_TOKEN"]
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    data = r.json()
    if r.status_code >= 400 or "access_token" not in data:
        print(f"refresh failed: {r.status_code} {data}", file=sys.stderr)
        return 1
    days = int(data.get("expires_in", 0)) // 86400
    print(f"token renewed, valid for ~{days} days", file=sys.stderr)
    print(data["access_token"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
