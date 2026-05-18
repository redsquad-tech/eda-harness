#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
LINE_BRANCH_RE_TPL = r"^device/{device}/(?P<line>[a-zA-Z0-9._-]+)$"


@dataclass
class TestRun:
    name: str
    command: list[str]
    exit_code: int
    passed: bool
    log_path: str


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


def run_cmd(cmd: list[str], cwd: Path, log_path: Path) -> int:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "# COMMAND\n"
        + " ".join(cmd)
        + "\n\n# STDOUT\n"
        + (proc.stdout or "")
        + "\n# STDERR\n"
        + (proc.stderr or ""),
        encoding="utf-8",
    )
    return proc.returncode


def git_output(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def git_ref_exists(ref: str, cwd: Path) -> bool:
    proc = subprocess.run(["git", "show-ref", "--verify", "--quiet", ref], cwd=str(cwd))
    return proc.returncode == 0


def git_switch(branch: str, cwd: Path) -> None:
    subprocess.run(["git", "switch", branch], cwd=str(cwd), check=True)


def copy_matching_files(root: Path, patterns: list[str], out_dir: Path) -> list[str]:
    copied: list[str] = []
    if not patterns:
        return copied
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        if any(fnmatch.fnmatch(rel, pat) for pat in patterns):
            dst = out_dir / rel.replace("/", "__")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(p.read_bytes())
            copied.append(str(dst))
    return copied


def ensure_git_clean_for_scope(cwd: Path, device: str, allow_dirty: bool) -> None:
    if allow_dirty:
        return

    device_prefix = f"devices/{device}/"
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    changed = [p.strip() for p in [*tracked, *untracked] if p.strip()]
    disallowed = [p for p in changed if not p.startswith(device_prefix)]
    if disallowed:
        raise RuntimeError(
            "Working tree has pending changes outside target device. "
            "Commit/stash them first or pass --allow-dirty.\n" + "\n".join(disallowed)
        )


def prepend_changelog(path: Path, version: str, quick_target: str, full_target: str) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else "# Changelog\n\n"
    entry = (
        f"## {version} - {datetime.now(timezone.utc).date().isoformat()}\n\n"
        f"- Freeze snapshot created\n"
        f"- Validation targets: `{quick_target}`, `{full_target}`\n\n"
    )
    if old.startswith("# Changelog"):
        head, _, tail = old.partition("\n\n")
        new = head + "\n\n" + entry + tail
    else:
        new = "# Changelog\n\n" + entry + old
    path.write_text(new, encoding="utf-8")


def load_device_versioning_config(device_dir: Path) -> dict:
    cfg_path = device_dir / "versioning.json"
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid versioning config: {cfg_path}") from exc


def ensure_line_branch(repo: Path, device: str, line: str, base_ref: str) -> str:
    target_branch = f"device/{device}/{line}"
    current = git_output(["branch", "--show-current"], repo)
    if current == target_branch:
        return target_branch
    if git_ref_exists(f"refs/heads/{target_branch}", repo):
        git_switch(target_branch, repo)
        return target_branch
    subprocess.run(["git", "switch", "-c", target_branch, base_ref], cwd=str(repo), check=True)
    return target_branch


def infer_line_from_branch(device: str, branch: str) -> str | None:
    rx = re.compile(LINE_BRANCH_RE_TPL.format(device=re.escape(device)))
    m = rx.match(branch)
    if not m:
        return None
    return m.group("line")


def update_index_in_main(
    repo: Path,
    device: str,
    record: dict,
    source_branch: str,
    python_bin: str,
) -> str | None:
    del python_bin  # reserved for future hooks
    main_branch = "main"
    current = git_output(["branch", "--show-current"], repo)

    if not git_ref_exists("refs/heads/main", repo):
        return None

    git_switch(main_branch, repo)
    try:
        index_path = repo / "devices" / device / "VERSION_INDEX.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        if index_path.exists():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {"device": device, "entries": []}
        else:
            data = {"device": device, "entries": []}

        if data.get("device") != device:
            data["device"] = device
        entries = data.setdefault("entries", [])

        freeze_tag = record["freeze_tag"]
        replaced = False
        for idx, item in enumerate(entries):
            if item.get("freeze_tag") == freeze_tag:
                entries[idx] = record
                replaced = True
                break
        if not replaced:
            entries.append(record)

        entries.sort(key=lambda e: (e.get("created_at", ""), e.get("line", ""), e.get("version", "")))
        data["updated_at"] = utc_now()

        index_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        subprocess.run(["git", "add", str(index_path)], cwd=str(repo), check=True)
        diff = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(repo), capture_output=True, text=True, check=True)
        if diff.stdout.strip():
            subprocess.run(
                ["git", "commit", "-m", f"Update {device} version index for {record['freeze_tag']}"],
                cwd=str(repo),
                check=True,
            )
            return git_output(["rev-parse", "HEAD"], repo)
        return None
    finally:
        git_switch(source_branch, repo)


def main() -> int:
    ap = argparse.ArgumentParser(description="Freeze a device version: run tests, save artifacts, commit, tag, and index")
    ap.add_argument("--device", required=True, help="Device directory name under devices/")
    ap.add_argument("--line", help="Device development line name. If omitted, inferred from current branch.")
    ap.add_argument("--base-ref", default="main", help="Base ref when creating a new line branch")
    ap.add_argument("--version", help="Explicit version string, e.g. 0.1.0 or v0.1.0")
    ap.add_argument("--bump", choices=["major", "minor", "patch"], default="patch")
    ap.add_argument("--quick-target", default="quick")
    ap.add_argument("--full-target", default="char")
    ap.add_argument("--python", default=os.environ.get("PYTHON", "python"))
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--no-tag", action="store_true")
    ap.add_argument("--no-main-index", action="store_true", help="Do not update devices/<device>/VERSION_INDEX.json on main")
    args = ap.parse_args()

    repo = Path.cwd()
    device_dir = repo / "devices" / args.device
    if not device_dir.exists():
        raise SystemExit(f"Device not found: {device_dir}")
    if not (device_dir / "run_tests.py").exists():
        raise SystemExit(f"Missing run_tests.py in {device_dir}")

    ensure_git_clean_for_scope(repo, args.device, args.allow_dirty)

    current_branch = git_output(["branch", "--show-current"], repo)
    inferred_line = infer_line_from_branch(args.device, current_branch)
    line = args.line or inferred_line
    if not line:
        raise SystemExit(
            "Cannot infer device line. Use branch device/<device>/<line> or pass --line <line>."
        )

    branch = ensure_line_branch(repo, args.device, line, args.base_ref)

    cfg = load_device_versioning_config(device_dir)
    quick_target = str(cfg.get("quick_target", args.quick_target)) if args.quick_target == "quick" else args.quick_target
    full_target = str(cfg.get("full_target", args.full_target)) if args.full_target == "char" else args.full_target

    version_file = device_dir / "VERSION"
    if args.version:
        try:
            version = format_semver(*parse_semver(args.version))
        except ValueError:
            raise SystemExit("--version must be semver, e.g. 0.2.0 or v0.2.0")
    else:
        if version_file.exists():
            current = version_file.read_text(encoding="utf-8").strip()
            try:
                version = bump_semver(current, args.bump)
            except ValueError as exc:
                raise SystemExit(
                    f"Invalid current VERSION file ({current!r}). Pass --version explicitly or fix VERSION file."
                ) from exc
        else:
            version = "v0.1.0"

    versions_dir = device_dir / "versions" / line / version
    logs_dir = versions_dir / "logs"
    metrics_dir = versions_dir / "metrics"
    versions_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    module = f"devices.{args.device}.run_tests"
    quick_cmd = [args.python, "-m", module, quick_target]
    full_cmd = [args.python, "-m", module, full_target]

    quick_code = run_cmd(quick_cmd, repo, logs_dir / f"{quick_target}.log")
    full_code = run_cmd(full_cmd, repo, logs_dir / f"{full_target}.log")

    runs = [
        TestRun(quick_target, quick_cmd, quick_code, quick_code == 0, str((logs_dir / f"{quick_target}.log").relative_to(repo))),
        TestRun(full_target, full_cmd, full_code, full_code == 0, str((logs_dir / f"{full_target}.log").relative_to(repo))),
    ]
    status = "passed" if all(r.passed for r in runs) else "failed"

    freeze_tag = f"device/{args.device}/{line}/{version}"
    summary = {
        "device": args.device,
        "line": line,
        "version": version,
        "freeze_tag": freeze_tag,
        "status": status,
        "runs": [asdict(r) for r in runs],
    }
    (versions_dir / "test-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    changelog_file = device_dir / "CHANGELOG.md"
    version_file.write_text(version + "\n", encoding="utf-8")
    prepend_changelog(changelog_file, version, quick_target, full_target)

    head_before = git_output(["rev-parse", "HEAD"], repo)
    manifest = {
        "device_name": args.device,
        "line": line,
        "version": version,
        "freeze_tag": freeze_tag,
        "timestamp_utc": utc_now(),
        "branch": branch,
        "git_commit_before_freeze": head_before,
        "test_commands": [quick_cmd, full_cmd],
        "status": status,
    }
    (versions_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    metrics_globs = cfg.get("metrics_globs", ["tests/*metrics*.json", "tests/**/*.json"])
    copied_metrics = copy_matching_files(device_dir, [str(p) for p in metrics_globs], metrics_dir)
    extra_globs = cfg.get("extra_artifacts_globs", [])
    copied_extras = copy_matching_files(device_dir, [str(p) for p in extra_globs], versions_dir / "artifacts")

    if not copied_metrics:
        (metrics_dir / "README.md").write_text(
            "# Metrics\n\nNo metric files matched configured patterns. Add device-specific metrics globs in versioning.json.\n",
            encoding="utf-8",
        )

    summary["copied_metrics"] = [str(Path(p).relative_to(repo)) for p in copied_metrics]
    summary["copied_artifacts"] = [str(Path(p).relative_to(repo)) for p in copied_extras]
    (versions_dir / "test-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if status != "passed":
        print(json.dumps({"status": "failed", "reason": "validation_failed", "artifact_dir": str(versions_dir)}, indent=2))
        return 2

    if not args.no_commit:
        subprocess.run(["git", "add", str(device_dir)], cwd=str(repo), check=True)
        subprocess.run(["git", "commit", "-m", f"Freeze {args.device} {line} {version}"], cwd=str(repo), check=True)

    head_after = git_output(["rev-parse", "HEAD"], repo)

    if not args.no_tag:
        subprocess.run(["git", "tag", "-a", freeze_tag, "-m", f"{args.device} {line} {version}"], cwd=str(repo), check=True)

    index_commit = None
    if not args.no_main_index:
        record = {
            "device": args.device,
            "line": line,
            "version": version,
            "created_at": utc_now(),
            "freeze_tag": freeze_tag,
            "freeze_commit": head_after,
            "source_branch": branch,
            "artifact_dir": str(versions_dir.relative_to(repo)),
            "status": status,
            "promoted_to_main": False,
            "release_tag": None,
            "main_merge_commit": None,
            "metrics_files": summary.get("copied_metrics", []),
        }
        index_commit = update_index_in_main(repo, args.device, record, branch, args.python)

    print(
        json.dumps(
            {
                "status": "passed",
                "device": args.device,
                "line": line,
                "version": version,
                "branch": branch,
                "git_commit": head_after,
                "freeze_tag": None if args.no_tag else freeze_tag,
                "artifact_dir": str(versions_dir),
                "copied_metrics": summary.get("copied_metrics", []),
                "copied_artifacts": summary.get("copied_artifacts", []),
                "index_commit_on_main": index_commit,
                "runs": [asdict(r) for r in runs],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
