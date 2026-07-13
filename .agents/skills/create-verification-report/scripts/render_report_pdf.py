#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SUBTITLE = "Verification Report"
DEFAULT_AUTHOR = "anadeto"
DEFAULT_COMPANY = "anadeto"
DEFAULT_CITY = "Moscow"


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def title_from_filename(path: Path) -> str:
    return re.sub(r"[_-]+", " ", path.stem).strip() or path.stem


def extract_h1(md_text: str) -> str | None:
    in_fence = False
    for line in md_text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def remove_first_h1(md_text: str) -> str:
    in_fence = False
    removed = False
    out: list[str] = []
    for line in md_text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence and not removed and re.match(r"^#\s+.+", line):
            removed = True
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"


def yaml_quote(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def write_meta(path: Path, args: argparse.Namespace, title: str, logo_path: Path) -> None:
    fields = {
        "subtitle": args.subtitle or DEFAULT_SUBTITLE,
        "title": args.title or title,
        "author": args.author or DEFAULT_AUTHOR,
        "company": args.company or DEFAULT_COMPANY,
        "city": args.city or DEFAULT_CITY,
        "year": args.year or str(datetime.now().year),
        "logo_path": str(logo_path),
    }
    lines = [f"{key}: {yaml_quote(value)}" for key, value in fields.items()]
    lines += ["", f"toc: {'true' if args.toc else 'false'}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_pandoc(report_md: Path, template_tex: Path, meta_yaml: Path, output_pdf: Path, report_dir: Path, engine: str) -> None:
    cmd = [
        "pandoc",
        str(report_md),
        "--from",
        "markdown",
        f"--template={template_tex}",
        f"--metadata-file={meta_yaml.name if meta_yaml.parent == report_dir else meta_yaml}",
        "--shift-heading-level-by=-1",
        f"--pdf-engine={engine}",
        f"--output={output_pdf}",
    ]
    eprint("[render_report_pdf] " + " ".join(shlex.quote(part) for part in cmd))
    subprocess.run(cmd, cwd=report_dir, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Markdown verification report to PDF.")
    parser.add_argument("report_md")
    parser.add_argument("--output")
    parser.add_argument("--title")
    parser.add_argument("--subtitle")
    parser.add_argument("--author")
    parser.add_argument("--company")
    parser.add_argument("--city")
    parser.add_argument("--year")
    parser.add_argument("--toc", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force-assets", action="store_true", help="Accepted for compatibility; assets are no longer copied.")
    parser.add_argument("--pdf-engine")
    args = parser.parse_args()

    report_path = Path(args.report_md).expanduser().resolve()
    if not report_path.exists():
        eprint(f"ERROR: report not found: {report_path}")
        return 2

    script_dir = Path(__file__).resolve().parent
    assets_dir = script_dir.parent / "assets"
    template_src = assets_dir / "template.tex"
    logo_src = assets_dir / "logo.png"
    if not template_src.exists() or not logo_src.exists():
        eprint(f"ERROR: missing bundled PDF assets in {assets_dir}")
        return 3

    report_dir = report_path.parent
    output_pdf = Path(args.output).expanduser().resolve() if args.output else report_path.with_suffix(".pdf")
    md_text = report_path.read_text(encoding="utf-8", errors="replace")
    title = args.title or extract_h1(md_text) or title_from_filename(report_path)

    if not cmd_exists("pandoc"):
        eprint("ERROR: pandoc not found in PATH")
        return 4

    engines = [args.pdf_engine] if args.pdf_engine else [engine for engine in ("xelatex", "lualatex") if cmd_exists(engine)]
    if not engines or any(engine and not cmd_exists(engine) for engine in engines):
        eprint("ERROR: xelatex or lualatex not found in PATH")
        return 4

    meta_yaml = report_dir / f".{report_path.stem}.__meta.yaml"
    tmp_md = report_dir / f".{report_path.stem}.__pdf.md"
    try:
        write_meta(meta_yaml, args, title, logo_src)
        tmp_md.write_text(remove_first_h1(md_text), encoding="utf-8")
        last_error: subprocess.CalledProcessError | None = None
        for index, engine in enumerate(engines):
            try:
                run_pandoc(tmp_md, template_src, meta_yaml, output_pdf, report_dir, engine)
                last_error = None
                break
            except subprocess.CalledProcessError as exc:
                last_error = exc
                if index + 1 < len(engines):
                    eprint(f"[render_report_pdf] {engine} failed, retrying")
        if last_error is not None:
            return last_error.returncode or 1
    finally:
        tmp_md.unlink(missing_ok=True)
        meta_yaml.unlink(missing_ok=True)

    print(output_pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
