#!/usr/bin/env python3
"""Tiny GitHub API helper for the KiCad-IOS spike (uses the stored
custom.github surrogate credential; never prints it).

Usage:
  gh.py create-repo NAME "description"
  gh.py get-repo OWNER/NAME
  gh.py patch-repo OWNER/NAME DESCRIPTION TOPIC1,TOPIC2
  gh.py put-file OWNER/NAME PATH LOCALFILE "message"
  gh.py dispatch OWNER/NAME WORKFLOW REF
  gh.py runs OWNER/NAME [N]
  gh.py run OWNER/NAME RUN_ID
  gh.py artifacts OWNER/NAME RUN_ID
  gh.py download OWNER/NAME ARTIFACT_ID OUTFILE
  gh.py logs OWNER/NAME RUN_ID OUTFILE.zip
"""
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    ensure_allowed_url,
)

API = "https://api.github.com"


class _StripAuthRedirect(urllib.request.HTTPRedirectHandler):
    """Artifact downloads 302 to signed storage URLs; forwarding the
    Authorization header there makes the storage service reject (401)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = urllib.request.Request(newurl, method="GET")
        return new
ALLOWED = ["api.github.com"]


def req(method, path, data=None, raw_out=None):
    url = API + path
    ensure_allowed_url(url, ALLOWED)
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body:
        r.add_header("Content-Type", "application/json")
    add_surrogate_to_request(r, "custom.github", allowed_hosts=ALLOWED)
    resp = urllib.request.build_opener(_StripAuthRedirect()).open(r)
    if raw_out:
        with open(raw_out, "wb") as f:
            f.write(resp.read())
        return {"saved": raw_out, "status": resp.status}
    if resp.status == 204 or resp.headers.get("Content-Length") == "0":
        return {"status": resp.status}
    return read_json_response(resp)


def main():
    cmd = sys.argv[1]
    if cmd == "create-repo":
        name, desc = sys.argv[2], sys.argv[3]
        out = req("POST", "/user/repos", {
            "name": name, "description": desc, "private": False,
            "auto_init": False, "license_template": None,
        })
        print(json.dumps({k: out.get(k) for k in ("full_name", "html_url", "default_branch")}, indent=1))
    elif cmd == "get-repo":
        out = req("GET", f"/repos/{sys.argv[2]}")
        print(json.dumps({k: out.get(k) for k in ("full_name", "description", "topics", "license", "default_branch", "size")}, indent=1))
    elif cmd == "patch-repo":
        owner_repo, desc, topics = sys.argv[2], sys.argv[3], sys.argv[4].split(",")
        out = req("PATCH", f"/repos/{owner_repo}", {"description": desc})
        out2 = req("PUT", f"/repos/{owner_repo}/topics", {"names": topics})
        print(json.dumps({"desc": out.get("description"), "topics": out2.get("names")}, indent=1))
    elif cmd == "put-file":
        import base64
        owner_repo, path, local, msg = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
        with open(local, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        data = {"message": msg, "content": content,
                "author": {"name": "user", "email": "user@users.noreply.github.com"},
                "committer": {"name": "user", "email": "user@users.noreply.github.com"}}
        try:
            existing = req("GET", f"/repos/{owner_repo}/contents/{path}")
            data["sha"] = existing["sha"]
        except Exception:
            pass
        out = req("PUT", f"/repos/{owner_repo}/contents/{path}", data)
        print(json.dumps({"path": path, "commit": out["commit"]["sha"]}, indent=1))
    elif cmd == "dispatch":
        owner_repo, wf, ref = sys.argv[2], sys.argv[3], sys.argv[4]
        req("POST", f"/repos/{owner_repo}/actions/workflows/{wf}/dispatches", {"ref": ref})
        print("dispatched")
    elif cmd == "runs":
        owner_repo = sys.argv[2]
        n = sys.argv[3] if len(sys.argv) > 3 else "8"
        out = req("GET", f"/repos/{owner_repo}/actions/runs?per_page={n}")
        for run in out.get("workflow_runs", []):
            print(run["id"], run["status"], run.get("conclusion"), run["name"], run["head_sha"][:8], run["created_at"])
    elif cmd == "run":
        out = req("GET", f"/repos/{sys.argv[2]}/actions/runs/{sys.argv[3]}")
        print(json.dumps({k: out.get(k) for k in ("id", "status", "conclusion", "name", "html_url")}, indent=1))
        jobs = req("GET", f"/repos/{sys.argv[2]}/actions/runs/{sys.argv[3]}/jobs")
        for j in jobs.get("jobs", []):
            print(" job:", j["id"], j["status"], j.get("conclusion"), j["name"])
            for s in j.get("steps", []):
                print("   step:", s["number"], s["status"], s.get("conclusion"), s["name"])
    elif cmd == "artifacts":
        out = req("GET", f"/repos/{sys.argv[2]}/actions/runs/{sys.argv[3]}/artifacts")
        for a in out.get("artifacts", []):
            print(a["id"], a["name"], a["size_in_bytes"], a["expired"])
    elif cmd == "download":
        req("GET", f"/repos/{sys.argv[2]}/actions/artifacts/{sys.argv[3]}/zip", raw_out=sys.argv[4])
        print("saved", sys.argv[4])
    elif cmd == "logs":
        req("GET", f"/repos/{sys.argv[2]}/actions/runs/{sys.argv[3]}/logs", raw_out=sys.argv[4])
        print("saved", sys.argv[4])
    else:
        sys.exit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
