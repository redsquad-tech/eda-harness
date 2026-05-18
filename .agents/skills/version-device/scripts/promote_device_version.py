#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_semver(text: str) -> tuple[int, int, int]:
    m = SEMVER_RE.match(text.strip())
    if not m:
        raise ValueError(f"Invalid semver: {text!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def format_semver(major: int, minor: int, patch: int) -> str:
    return f"v{major}.{minor}.{patch}"


def bump_semver(current: str, bump: str) -> str:
    major, minor, patch = parse_semver(current)
    if bump == "major":
        return format_semver(major + 1, 0, 0)
    if bump == "minor":
        return format_semver(major, minor + 1, 0)
    if bump == "patch":
        return format_semver(major, minor, patch + 1)
    raise ValueError(f"Unsupported bump: {bump}")


def git_output(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def git_ref_exists(ref: str, cwd: Path) -> bool:
    proc = subprocess.run(["git", "show-ref", "--verify", "--quiet", ref], cwd=str(cwd))
    return proc.returncode == 0


def ensure_clean(repo: Path) -> None:
    changed = subprocess.run(["git", "status", "--porcelain"], cwd=str(repo), capture_output=True, text=True, check=True).stdout.strip()
    if changed:
        raise SystemExit("Working tree is not clean. Commit/stash changes before promote.")


def load_index(index_path: Path, device: str) -> dict:
    if not index_path.exists():
        return {"device": device, "entries": []}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"device": device, "entries": []}
    data.setdefault("device", device)
    data.setdefault("entries", [])
    return data


def save_index(index_path: Path, data: dict) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Promote a frozen device line version into main and assign release tag")
    ap.add_argument("--device", required=True)
    ap.add_argument("--line", required=True)
    ap.add_argument("--version", required=True, help="Line freeze version, e.g. v0.2.0")
    ap.add_argument("--release-version", help="Explicit release version for main, e.g. v1.3.0")
    ap.add_argument("--release-bump", choices=["major", "minor", "patch"], default="patch")
    args = ap.parse_args()

    repo = Path.cwd()
    ensure_clean(repo)

    line_version = format_semver(*parse_semver(args.version))
    freeze_tag = f"device/{args.device}/{args.line}/{line_version}"
    line_branch = f"device/{args.device}/{args.line}"

    if not git_ref_exists(f"refs/heads/{line_branch}", repo):
        raise SystemExit(f"Line branch not found: {line_branch}")
    if not git_ref_exists(f"refs/tags/{freeze_tag}", repo):
        raise SystemExit(f"Freeze tag not found: {freeze_tag}")

    if not git_ref_exists("refs/heads/main", repo):
        raise SystemExit("Main branch not found")

    subprocess.run(["git", "switch", "main"], cwd=str(repo), check=True)
    subprocess.run(["git", "merge", "--no-ff", line_branch, "-m", f"Merge {line_branch} {line_version}"], cwd=str(repo), check=True)
    merge_commit = git_output(["rev-parse", "HEAD"], repo)

    release_version_file = repo / "devices" / args.device / "RELEASE_VERSION"
    if args.release_version:
        release_version = format_semver(*parse_semver(args.release_version))
    else:
        if release_version_file.exists():
            current = release_version_file.read_text(encoding="utf-8").strip()
            try:
                release_version = bump_semver(current, args.release_bump)
            except ValueError as exc:
                raise SystemExit(
                    f"Invalid RELEASE_VERSION ({current!r}). Pass --release-version explicitly or fix file."
                ) from exc
        else:
            release_version = "v0.1.0"

    release_tag = f"release/{args.device}/{release_version}"
    if git_ref_exists(f"refs/tags/{release_tag}", repo):
        raise SystemExit(f"Release tag already exists: {release_tag}")

    subprocess.run(["git", "tag", "-a", release_tag, "-m", f"{args.device} {release_version}"], cwd=str(repo), check=True)
    release_version_file.write_text(release_version + "\n", encoding="utf-8")

    index_path = repo / "devices" / args.device / "VERSION_INDEX.json"
    data = load_index(index_path, args.device)
    entries = data["entries"]
    found = False
    for item in entries:
        if item.get("freeze_tag") == freeze_tag:
            item["promoted_to_main"] = True
            item["release_tag"] = release_tag
            item["main_merge_commit"] = merge_commit
            item["promoted_at"] = utc_now()
            found = True
            break

    if not found:
        entries.append(
            {
                "device": args.device,
                "line": args.line,
                "version": line_version,
                "created_at": utc_now(),
                "freeze_tag": freeze_tag,
                "freeze_commit": git_output(["rev-list", "-n", "1", freeze_tag], repo),
                "source_branch": line_branch,
                "artifact_dir": f"devices/{args.device}/versions/{args.line}/{line_version}",
                "status": "passed",
                "promoted_to_main": True,
                "release_tag": release_tag,
                "main_merge_commit": merge_commit,
                "promoted_at": utc_now(),
                "metrics_files": [],
            }
        )

    entries.sort(key=lambda e: (e.get("created_at", ""), e.get("line", ""), e.get("version", "")))
    data["updated_at"] = utc_now()
    save_index(index_path, data)

    subprocess.run(["git", "add", str(release_version_file), str(index_path)], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", f"Promote {args.device} {args.line} {line_version} as {release_version}"], cwd=str(repo), check=True)
    promote_commit = git_output(["rev-parse", "HEAD"], repo)

    print(
        json.dumps(
            {
                "status": "passed",
                "device": args.device,
                "line": args.line,
                "line_version": line_version,
                "freeze_tag": freeze_tag,
                "release_version": release_version,
                "release_tag": release_tag,
                "merge_commit": merge_commit,
                "promote_commit": promote_commit,
                "branch": "main",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
