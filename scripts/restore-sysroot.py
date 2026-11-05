# [KiCad-IOS port] Restore cross-run sysroot artifacts into work/sysroot-ios.
# GPLv3-or-later, matching upstream KiCad.
#
# actions/download-artifact only sees artifacts from the SAME workflow run,
# but the iOS sysroot is produced piecemeal by earlier stage runs (deps,
# occ, ngspice, python). This fetches the newest non-expired artifact of
# each requested name through the GitHub API and merges them. The archive
# download URL 302-redirects to blob storage, which rejects the
# Authorization header, so it is stripped on redirect.
#
# Usage: restore-sysroot.py <artifact-name> [more names...]
# Env:   GH_TOKEN (or GITHUB_TOKEN), GITHUB_REPOSITORY
import json
import os
import sys
import urllib.request
import zipfile
import io


class NoAuthRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        r = super().redirect_request(req, fp, code, msg, headers, newurl)
        if r is not None:
            r.remove_header("Authorization")
        return r


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ.get("GH_TOKEN") or os.environ["GITHUB_TOKEN"]
    opener = urllib.request.build_opener(NoAuthRedirect)

    def get(url):
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
            },
        )
        return opener.open(req)

    arts = json.load(
        get(f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100")
    )["artifacts"]
    os.makedirs("work/sysroot-ios", exist_ok=True)
    got = []
    for name in sys.argv[1:]:
        cands = [a for a in arts if a["name"] == name and not a["expired"]]
        if not cands:
            print("MISSING artifact:", name)
            continue
        a = cands[0]
        data = get(a["archive_download_url"]).read()
        zipfile.ZipFile(io.BytesIO(data)).extractall("work/sysroot-ios")
        got.append(f"{name} ({a['size_in_bytes']} B, run {a['workflow_run']['id']})")
    print("merged:", "; ".join(got))
    if len(got) != len(sys.argv[1:]):
        sys.exit("sysroot restore incomplete")


if __name__ == "__main__":
    main()
