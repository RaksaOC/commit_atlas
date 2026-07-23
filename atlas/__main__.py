"""CLI: python -m atlas --config configs/chanraksa.toml"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyze import analyze
from .config import load_config
from .report import write_html, write_json, write_markdown


def main(argv: list[str] | None = None) -> int:
    tool_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="Build a commit atlas from local git history.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=tool_root / "configs" / "chanraksa.toml",
        help="Path to TOML config (default: configs/chanraksa.toml)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory (default: from config or ./out)",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=tool_root / "templates" / "atlas.html.template",
        help="HTML template path",
    )
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"Config not found: {args.config}", file=sys.stderr)
        print("Copy config.example.toml → config.toml (or use configs/chanraksa.toml).", file=sys.stderr)
        return 1

    cfg = load_config(args.config)
    if args.output_dir:
        cfg.output_dir = args.output_dir.resolve()

    out = cfg.output_dir
    assert out is not None
    out.mkdir(parents=True, exist_ok=True)

    data = analyze(cfg, verbose=not args.quiet)

    json_path = out / "contributions-data.json"
    md_path = out / "contributions.md"
    html_path = out / "contribution.html"
    index_path = tool_root / "index.html"

    write_json(data, json_path)
    write_markdown(data, md_path, count_mr_events=cfg.count_mr_events)

    if args.template.exists():
        write_html(data, args.template, html_path)
        write_html(data, args.template, index_path)
    elif not args.quiet:
        print(f"WARN: template missing at {args.template}; skipped HTML")

    s = data["summary"]
    if not args.quiet:
        print()
        print(
            f"TOTAL={s['total_commits']} regular={s['regular_commits']} "
            f"merges={s['merge_commits']} active_days={s['active_days']}"
        )
        print(f"Wrote {json_path}")
        print(f"Wrote {md_path}")
        if html_path.exists():
            print(f"Wrote {html_path}")
        if index_path.exists():
            print(f"Wrote {index_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
