#!/usr/bin/env python3
"""Upload one signed AAB to a protected Google Play internal-testing edit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote

SCOPE = "https://www.googleapis.com/auth/androidpublisher"
API = "https://androidpublisher.googleapis.com/androidpublisher/v3"
UPLOAD_API = "https://androidpublisher.googleapis.com/upload/androidpublisher/v3"
LANGUAGE_FILES = {"ar": "ar.txt", "en-US": "en.txt", "el-GR": "el.txt"}


def checked(response: requests.Response, label: str) -> dict:
    if response.status_code < 200 or response.status_code >= 300:
        body = response.text[:2000]
        raise SystemExit(f"{label} failed: HTTP {response.status_code}: {body}")
    if not response.content:
        return {}
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-account", type=Path)
    parser.add_argument("--aab", type=Path, required=True)
    parser.add_argument("--package", default="com.orthodoxprayers.privateapp")
    parser.add_argument("--track", default="internal")
    parser.add_argument("--status", choices=["draft", "completed"], default="completed")
    parser.add_argument("--release-name", required=True)
    parser.add_argument("--notes-dir", type=Path, default=Path("play-store/release-notes"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("release/play-internal-upload.json"))
    args = parser.parse_args()

    if not args.aab.is_file() or args.aab.stat().st_size < 1024:
        raise SystemExit(f"AAB is missing or empty: {args.aab}")
    notes = []
    for language, filename in LANGUAGE_FILES.items():
        path = args.notes_dir / filename
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise SystemExit(f"Release notes are empty: {path}")
        notes.append({"language": language, "text": text})

    report = {
        "schema_version": 1,
        "package": args.package,
        "track": args.track,
        "status": args.status,
        "release_name": args.release_name,
        "aab": str(args.aab),
        "bytes": args.aab.stat().st_size,
        "dry_run": args.dry_run,
    }
    if args.dry_run:
        report["result"] = "VALIDATED_ONLY"
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("PLAY_INTERNAL_DRY_RUN_OK")
        return

    if args.service_account is None or not args.service_account.is_file():
        raise SystemExit("A Google Play service-account JSON file is required for publishing")
    import requests
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_file(
        str(args.service_account), scopes=[SCOPE]
    )
    credentials.refresh(Request())
    headers = {"Authorization": f"Bearer {credentials.token}"}
    package = quote(args.package, safe="")

    edit = checked(
        requests.post(f"{API}/applications/{package}/edits", headers=headers, json={}, timeout=60),
        "create edit",
    )
    edit_id = edit.get("id")
    if not edit_id:
        raise SystemExit("Google Play did not return an edit id")

    with args.aab.open("rb") as stream:
        bundle = checked(
            requests.post(
                f"{UPLOAD_API}/applications/{package}/edits/{quote(str(edit_id), safe='')}/bundles",
                headers={**headers, "Content-Type": "application/octet-stream"},
                data=stream,
                timeout=180,
            ),
            "upload bundle",
        )
    version_code = bundle.get("versionCode")
    if not version_code:
        raise SystemExit("Google Play did not return the uploaded versionCode")

    track_body = {
        "track": args.track,
        "releases": [{
            "name": args.release_name,
            "versionCodes": [str(version_code)],
            "status": args.status,
            "releaseNotes": notes,
        }],
    }
    checked(
        requests.put(
            f"{API}/applications/{package}/edits/{quote(str(edit_id), safe='')}/tracks/{quote(args.track, safe='')}",
            headers={**headers, "Content-Type": "application/json"},
            json=track_body,
            timeout=60,
        ),
        "update track",
    )
    checked(
        requests.post(
            f"{API}/applications/{package}/edits/{quote(str(edit_id), safe='')}:commit",
            headers=headers,
            timeout=60,
        ),
        "commit edit",
    )
    report.update({"result": "COMMITTED", "edit_id": edit_id, "version_code": version_code})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PLAY_INTERNAL_UPLOAD_OK version_code={version_code} track={args.track}")


if __name__ == "__main__":
    main()
