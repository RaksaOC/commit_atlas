"""Write markdown + HTML atlas outputs."""

from __future__ import annotations

import json
from pathlib import Path


def write_markdown(data: dict, path: Path, *, count_mr_events: bool = True) -> None:
    s = data["summary"]
    author = data["author"]
    rng = data["range"]
    emails = ", ".join(f"`{e}`" for e in author["emails"])

    lines = [
        f"# Commit Atlas — {author['name']}",
        "",
        f"**Author:** {author['name']}  ",
        f"**Emails counted:** {emails}  ",
        f"**Window:** {rng['since']} → {rng['until']}  ",
        f"**Generated:** {data['generated_at']}",
        "",
        "## Totals",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| All contributions | **{s['total_commits']}** |",
        f"| Regular commits | {s['regular_commits']} |",
        f"| Merges | {s['merge_commits']} |",
        f"| Active days | {s['active_days']} |",
        f"| Busiest day | {s['max_day_count']} on {s['max_day_date'] or '—'} |",
        f"| Repos with activity | {s['repos_with_activity']} / {s['repo_count']} |",
        "",
        "## Per repository",
        "",
        "| Repo | Branch | Total | Regular | Merges | First | Last |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for r in data["repos"]:
        lines.append(
            f"| `{r['repo']}` | `{r['branch']}` | **{r['total']}** | {r['regular']} | "
            f"{r['merges']} | {r['first'] or '—'} | {r['last'] or '—'} |"
        )

    method = [
        "",
        "### Method",
        "",
        "- Counts commits on the first available configured branch per repo.",
        "- Author match uses the emails listed above.",
    ]
    if count_mr_events:
        method.append(
            "- **Merges** include merge commits plus estimated GitLab-style "
            "open/accept MR events (~+2 per `Merge branch … into '<branch>'`)."
        )
    method += [
        "- Interactive report: open `contribution.html` (JSON embedded at build time).",
        "",
    ]
    lines.extend(method)
    path.write_text("\n".join(lines) + "\n")


def write_html(data: dict, template_path: Path, out_path: Path) -> None:
    tpl = template_path.read_text()
    embedded = json.dumps(data).replace("</", "<\\/")
    if "__DATA__" not in tpl:
        raise ValueError(f"Template missing __DATA__ placeholder: {template_path}")
    out_path.write_text(tpl.replace("__DATA__", embedded))


def write_json(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")
