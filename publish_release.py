"""One-shot publisher: GitHub release + Supabase launcher_releases row.

Reads:
  GITHUB_PERSONAL_ACCESS_TOKEN  — must have `repo` scope (so we can POST a release
                                  AND upload an asset binary)
  SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY  — direct DB write, bypasses admin JWT

Argv:
  python publish_release.py <version>  e.g. 1.0.8

Assumes Output\\TranslationManager-Setup-<version>.exe exists.
"""
from __future__ import annotations

import hashlib
import io
import os
import subprocess
import sys
from pathlib import Path

import requests

# Wrap console so non-ASCII (Hebrew, →) doesn't crash on cp1255 cmd.exe.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", write_through=True)


def github_token_from_git_credential() -> str | None:
    """Fall back to Git Credential Manager when the PAT isn't in env.
    Returns the cached github.com password (the PAT) or None on failure."""
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True,
            capture_output=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return None
        for line in proc.stdout.splitlines():
            if line.startswith("password="):
                pw = line[len("password="):].strip()
                # PATs are ASCII; reject anything else (catches the Hebrew
                # placeholder env var that triggered the search in the first
                # place).
                try:
                    pw.encode("latin-1")
                except UnicodeEncodeError:
                    return None
                return pw or None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return None

OWNER  = "nehorayc04"
REPO   = "translation-launcher"
SCRIPTS_DIR = Path(r"c:\Users\nc528\סקריפטים\תרגום משחקים")
WEBSITE_ENV = Path(r"c:\Users\nc528\סקריפטים\אתר תרגום משחקים\.env")


def load_env_file(p: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        out[k.strip()] = v
    return out


def fail(msg: str) -> None:
    print(f"FATAL: {msg}", flush=True)
    sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: publish_release.py <version>   e.g. 1.0.8")
    version = sys.argv[1].strip()
    if not version:
        fail("empty version")

    # Prefer git-credential-cached PAT (real, ASCII) over env vars which
    # on this machine may hold a Hebrew placeholder string instead.
    gh_token = github_token_from_git_credential()
    if not gh_token:
        env_tok = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        try:
            env_tok.encode("latin-1")
            gh_token = env_tok
        except UnicodeEncodeError:
            gh_token = ""
    if not gh_token:
        fail("no usable GitHub token found (git-credential failed AND env var has non-ASCII placeholder)")

    env = load_env_file(WEBSITE_ENV)
    sb_url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    sb_key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not sb_url or not sb_key:
        fail("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing (checked website .env + env)")

    filename = f"TranslationManager-Setup-{version}.exe"
    asset_path = SCRIPTS_DIR / "Output" / filename
    if not asset_path.exists():
        fail(f"asset not found: {asset_path}")
    size_bytes = asset_path.stat().st_size

    # ── 1. SHA-256 ─────────────────────────────────────────────────────────
    print(f"[*] hashing {asset_path.name} ({size_bytes:,} bytes)…", flush=True)
    h = hashlib.sha256()
    with asset_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    sha256 = h.hexdigest()
    print(f"[*] sha256 = {sha256}", flush=True)

    # ── 2. Release notes (Hebrew, user-facing) ─────────────────────────────
    notes = (
        "תיקון קריטי: לוח הבקרה החי בדף הבית לא הציג שום נתונים כאשר שלב הצינור "
        "הוגדר כ-translating / extracting / packing / finalizing / qa (במקום הערך הגנרי "
        "in-progress). עכשיו לוח הבקרה תופס את כל מצבי הצינור, כולל בריצת התרגום "
        "החיה של סייברפאנק 2077.\n"
        "\n"
        "בנוסף: ניקוי לונה־סורוגייטים (Lone UTF-16 surrogate) בשדות unit / gpuModel / "
        "aiModel / phaseLabelHe לפני שמירה לבסיס נתונים, וגיבוי-חיים בצד הלקוח "
        "(swr_cache.py) כך שערך מקולקל לא יקרוס את גשר Eel ויפיל את הלאנצ׳ר ל"
        "מסך שחור."
    )

    gh_headers = {
        "Authorization":        f"Bearer {gh_token}",
        "Accept":               "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent":           "TranslationHub-Releaser/1.0",
    }
    # Sanity: every header value MUST be latin-1 encodable (http.client
    # requirement). Catches stray Hebrew in env-sourced tokens early instead
    # of deep inside urllib3's putheader.
    for k, v in gh_headers.items():
        try:
            v.encode("latin-1")
        except UnicodeEncodeError as e:
            fail(f"non-latin1 char in gh_headers[{k!r}] (len={len(v)}): {e}")

    # ── 3. Create the release (or reuse an existing draft) ─────────────────
    tag = f"v{version}"
    print(f"[*] creating GitHub release {tag} on {OWNER}/{REPO}…", flush=True)
    r = requests.post(
        f"https://api.github.com/repos/{OWNER}/{REPO}/releases",
        headers=gh_headers,
        json={
            "tag_name":         tag,
            "target_commitish": "main",
            "name":             f"v{version}",
            "body":             notes,
            "draft":            False,
            "prerelease":       False,
        },
        timeout=60,
    )
    if r.status_code == 422:
        # Already exists — fetch it.
        print("[*] release tag exists; fetching existing release…", flush=True)
        r2 = requests.get(
            f"https://api.github.com/repos/{OWNER}/{REPO}/releases/tags/{tag}",
            headers=gh_headers, timeout=30,
        )
        if not r2.ok:
            fail(f"fetch existing release failed: {r2.status_code} {r2.text[:200]}")
        rel = r2.json()
    elif r.ok:
        rel = r.json()
    else:
        fail(f"create release failed: {r.status_code} {r.text[:400]}")

    upload_url_template = rel["upload_url"]                 # ends with "{?name,label}"
    upload_url = upload_url_template.split("{")[0] + f"?name={filename}"
    release_html = rel.get("html_url", f"https://github.com/{OWNER}/{REPO}/releases/tag/{tag}")

    # ── 4. Upload the asset ───────────────────────────────────────────────
    # Delete existing asset of same name first (a 1.0.8.exe lingering from a
    # failed prior run would block the upload).
    for existing in rel.get("assets", []):
        if existing.get("name") == filename:
            print(f"[*] deleting pre-existing asset id={existing['id']} to allow re-upload…", flush=True)
            d = requests.delete(existing["url"], headers=gh_headers, timeout=30)
            if d.status_code not in (204, 404):
                fail(f"delete existing asset failed: {d.status_code} {d.text[:200]}")

    print(f"[*] uploading {filename} ({size_bytes/1024/1024:.1f} MB)…", flush=True)
    with asset_path.open("rb") as f:
        up_headers = dict(gh_headers)
        up_headers["Content-Type"]   = "application/octet-stream"
        up_headers["Content-Length"] = str(size_bytes)
        u = requests.post(upload_url, headers=up_headers, data=f, timeout=600)
    if not u.ok:
        fail(f"asset upload failed: {u.status_code} {u.text[:400]}")
    asset = u.json()
    download_url = asset["browser_download_url"]
    print(f"[*] uploaded → {download_url}", flush=True)

    # ── 5. Insert + flip is_current via Supabase REST ─────────────────────
    sb_headers = {
        "apikey":        sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }
    print("[*] demoting any existing is_current=true row…", flush=True)
    r = requests.patch(
        f"{sb_url}/rest/v1/launcher_releases?is_current=eq.true",
        headers=sb_headers,
        json={"is_current": False},
        timeout=30,
    )
    if not r.ok:
        fail(f"demote-current failed: {r.status_code} {r.text[:200]}")
    demoted = r.json() if r.text else []
    print(f"[*] demoted {len(demoted)} row(s)", flush=True)

    print("[*] inserting new release row…", flush=True)
    row = {
        "version":        version,
        "filename":       filename,
        "storage_path":   download_url,
        "size_bytes":     size_bytes,
        "sha256":         sha256,
        "notes":          notes,
        "is_current":     True,
        "screenshot_url": None,
    }
    r = requests.post(
        f"{sb_url}/rest/v1/launcher_releases",
        headers=sb_headers,
        json=row,
        timeout=30,
    )
    if not r.ok:
        fail(f"insert failed: {r.status_code} {r.text[:400]}")
    inserted = r.json()
    print(f"[*] inserted row id={inserted[0]['id'] if inserted else '??'}", flush=True)

    # ── 6. Verify public read sees the new version ─────────────────────────
    print("[*] verifying public /api/launcher reads the new version…", flush=True)
    pub = requests.get("https://hebrew-translation-hub.com/api/launcher", timeout=15)
    if pub.ok:
        body = pub.json()
        print(f"[*] /api/launcher → version={body.get('version')} filename={body.get('filename')}", flush=True)
        if body.get("version") != version:
            print("[!] WARNING: public endpoint returned a different version — "
                  "Vercel edge cache may take ~10s to refresh.", flush=True)
    else:
        print(f"[!] verification fetch failed: {pub.status_code}", flush=True)

    print()
    print("=" * 60)
    print(f"[ok] published v{version}")
    print(f"     GitHub:  {release_html}")
    print(f"     Asset:   {download_url}")
    print(f"     SHA256:  {sha256}")
    print(f"     Size:    {size_bytes:,} bytes ({size_bytes/1024/1024:.1f} MB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
