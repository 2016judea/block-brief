#!/usr/bin/env python3
"""Deploy site/ to Vercel production over the REST API (project: block-brief).

Ported from buying-window/scripts/deploy.py. Static files upload under public/
(outputDirectory "public" in vercel.json AND the payload: the payload wins), api/
and vercel.json at the root. Polls readyState and exits non-zero on anything but
READY, because a BLOCKED deploy looks like success from the CLI.

Needs VERCEL_TOKEN (bricks/.env has one). Run pipeline/brief.py --example first;
the landing page reads public/example.json.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "site"
TEAM = "team_XnhPzBEcaSfEmZFo9M2isLFY"
PROJECT = "block-brief"
SKIP_DIRS = {".git", "node_modules", ".vercel", "__pycache__"}
SKIP_FILES = {".env", ".DS_Store"}


def request(url, token, data=None, headers=None):
    head = {"Authorization": f"Bearer {token}"}
    head.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=head)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def collect():
    assert (ROOT / "public" / "example.json").exists(), "run pipeline/brief.py --example first"
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(p in SKIP_DIRS for p in rel.parts) or rel.name in SKIP_FILES:
            continue
        if rel.parts[0] not in ("api", "public") and str(rel) != "vercel.json":
            continue
        yield rel, path


def main():
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        sys.exit("VERCEL_TOKEN is not set.")
    files, total = [], 0
    for rel, path in collect():
        body = path.read_bytes()
        sha = hashlib.sha1(body).hexdigest()
        code, out = request("https://api.vercel.com/v2/files", token, data=body,
                            headers={"Content-Type": "application/octet-stream", "x-vercel-digest": sha, "x-vercel-team-id": TEAM})
        if code >= 400:
            sys.exit(f"upload {rel} failed: {code} {out}")
        files.append({"file": str(rel), "sha": sha, "size": len(body)})
        total += len(body)
    print(f"  {len(files)} files, {total:,} bytes")
    payload = json.dumps({"name": PROJECT, "project": PROJECT, "target": "production", "files": files,
                          "projectSettings": {"framework": None, "outputDirectory": "public"}}).encode()
    code, out = request(f"https://api.vercel.com/v13/deployments?teamId={TEAM}&skipAutoDetectionConfirmation=1", token,
                        data=payload, headers={"Content-Type": "application/json"})
    if code >= 400 or out.get("error"):
        sys.exit(f"create failed: {code} {json.dumps(out.get('error'))}")
    url = out["url"]
    print(f"  deploying https://{url}")
    for _ in range(80):
        time.sleep(3)
        _, d = request(f"https://api.vercel.com/v13/deployments/{url}?teamId={TEAM}", token)
        state = d.get("readyState")
        if state in ("READY", "ERROR", "BLOCKED", "CANCELED"):
            print(f"  {state} {d.get('errorMessage') or ''}")
            sys.exit(0 if state == "READY" else 1)
    sys.exit("timed out waiting for the deployment to settle")


if __name__ == "__main__":
    main()
