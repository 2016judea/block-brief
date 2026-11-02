#!/usr/bin/env python3
"""Upsert env vars on the block-brief Vercel project from the repo's .env, by name.

    python3 scripts/vercel_env.py CLOVER_ENV CLOVER_APP_ID CLOVER_APP_SECRET

Needs VERCEL_TOKEN (bricks/.env). Reads back each value with decrypt=true and
refuses to report success unless it matches, because a PATCH that 200s on the
wrong id looks the same as one that worked.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

TEAM = "team_XnhPzBEcaSfEmZFo9M2isLFY"
PROJECT = "prj_xt4Me7p7w1mTG5fOC9DkWQx5GKWR"
ROOT = Path(__file__).resolve().parent.parent


def env_file():
    out = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def call(method, path, body=None):
    req = urllib.request.Request(f"https://api.vercel.com{path}", method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['VERCEL_TOKEN']}", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main(keys):
    local = env_file()
    existing = {e["key"]: e for e in call("GET", f"/v9/projects/{PROJECT}/env?teamId={TEAM}")["envs"]}
    for k in keys:
        v = local[k]
        if k in existing:
            call("PATCH", f"/v9/projects/{PROJECT}/env/{existing[k]['id']}?teamId={TEAM}", {"value": v, "target": ["production", "preview", "development"], "type": "encrypted"})
        else:
            call("POST", f"/v10/projects/{PROJECT}/env?teamId={TEAM}&upsert=true", {"key": k, "value": v, "target": ["production", "preview", "development"], "type": "encrypted"})
        # the LIST endpoint returns the encrypted blob even with decrypt=true; only the per-id GET decrypts
        eid = existing[k]["id"] if k in existing else {e["key"]: e for e in call("GET", f"/v9/projects/{PROJECT}/env?teamId={TEAM}")["envs"]}[k]["id"]
        back = call("GET", f"/v9/projects/{PROJECT}/env/{eid}?teamId={TEAM}&decrypt=true")["value"]
        print(k, "ok" if back == v else "MISMATCH", file=sys.stderr)
        if back != v:
            sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
