"""Analyze local repos and build the atlas data payload."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from .config import AtlasConfig
from . import gitops


def build_weeks(
    since,
    until,
    global_daily: dict[str, int],
    by_repo_day: dict[str, dict[str, int]],
) -> list:
    pad_start = (since.weekday() + 1) % 7
    grid_start = since - timedelta(days=pad_start)
    pad_end = (6 - ((until.weekday() + 1) % 7)) % 7
    grid_end = until + timedelta(days=pad_end)

    weeks: list[list[dict]] = []
    col: list[dict] = []
    cur = grid_start
    while cur <= grid_end:
        ds = cur.isoformat()
        in_range = since <= cur <= until
        col.append(
            {
                "date": ds,
                "count": global_daily.get(ds, 0) if in_range else 0,
                "in_range": in_range,
                "by_repo": dict(by_repo_day.get(ds, {})) if in_range else {},
            }
        )
        if len(col) == 7:
            weeks.append(col)
            col = []
        cur += timedelta(days=1)
    if col:
        while len(col) < 7:
            col.append({"date": None, "count": 0, "in_range": False, "by_repo": {}})
        weeks.append(col)
    return weeks


def analyze(cfg: AtlasConfig, *, verbose: bool = True) -> dict:
    emails = cfg.author_emails
    since, until = cfg.since, cfg.until

    if verbose:
        print(f"Author: {cfg.author_name} <{', '.join(emails)}>")
        print(f"Window: {since} → {until}")
        print(f"Workspace: {cfg.workspace_root}")
        print()

    repos: list[dict] = []
    global_daily: dict[str, int] = defaultdict(int)
    by_repo_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for repo in cfg.repos:
        label = repo.label
        path = cfg.resolve_repo_path(repo)

        if not path.exists():
            if verbose:
                print(f"SKIP {label} (missing path {path})")
            continue
        if not gitops.has_git(path):
            if verbose:
                print(f"SKIP {label} (no .git at {path})")
            continue

        ref = gitops.pick_ref(path, repo.branches)
        if not ref:
            if verbose:
                print(f"SKIP {label} (no branch among {repo.branches})")
            repos.append(
                {
                    "repo": label,
                    "id": repo.name,
                    "branch": "-",
                    "status": "missing-branch",
                    "total": 0,
                    "regular": 0,
                    "merges": 0,
                    "first": None,
                    "last": None,
                    "daily": {},
                }
            )
            continue

        total = gitops.count_commits(path, ref, emails, since, until, merges_only=False)
        merge_commits = gitops.count_commits(
            path, ref, emails, since, until, merges_only=True
        )
        regular = total - merge_commits
        daily = gitops.daily_counts(path, ref, emails, since, until)
        merge_subjects = gitops.daily_merge_subjects(path, ref, emails, since, until)
        first, last = gitops.first_last(path, ref, emails, since, until)

        mr_by_day: dict[str, int] = {}
        mr_events = 0
        if cfg.count_mr_events:
            for d, subjects in merge_subjects.items():
                n = sum(
                    1
                    for s in subjects
                    if gitops.is_mr_merge_into(s, cfg.mr_into_branch)
                )
                if n:
                    mr_by_day[d] = n * 2
                    mr_events += n * 2

        merges = merge_commits + mr_events
        total = regular + merges

        for d, c in list(daily.items()):
            bonus = mr_by_day.get(d, 0)
            day_total = c + bonus
            global_daily[d] += day_total
            by_repo_day[d][label] += day_total
            daily[d] = day_total

        if verbose:
            print(
                f"{label} @ {ref}  total={total}  regular={regular}  "
                f"merges={merges} (commits={merge_commits} + mr={mr_events})  "
                f"({first} → {last})"
            )

        entry = {
            "repo": label,
            "id": repo.name,
            "branch": ref,
            "status": "ok",
            "total": total,
            "regular": regular,
            "merges": merges,
            "merge_commits": merge_commits,
            "mr_events": mr_events,
            "first": first,
            "last": last,
            "daily": daily,
        }
        if cfg.include_paths:
            entry["path"] = str(path)
        repos.append(entry)

    days = []
    d = since
    while d <= until:
        ds = d.isoformat()
        days.append(
            {
                "date": ds,
                "count": global_daily.get(ds, 0),
                "by_repo": dict(by_repo_day.get(ds, {})),
                "weekday": d.weekday(),
            }
        )
        d += timedelta(days=1)

    grand_total = sum(r["total"] for r in repos)
    grand_regular = sum(r["regular"] for r in repos)
    grand_merges = sum(r["merges"] for r in repos)
    active_days = sum(1 for x in days if x["count"] > 0)
    max_day = max((x["count"] for x in days), default=0)
    max_day_date = (
        next((x["date"] for x in days if x["count"] == max_day), None) if max_day else None
    )

    return {
        "author": {"name": cfg.author_name, "emails": list(emails)},
        "range": {"since": since.isoformat(), "until": until.isoformat()},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "display": {
            "subtitle": cfg.subtitle,
            "disclaimer": cfg.disclaimer,
            "aliases": dict(cfg.aliases),
        },
        "summary": {
            "total_commits": grand_total,
            "regular_commits": grand_regular,
            "merge_commits": grand_merges,
            "active_days": active_days,
            "max_day_count": max_day,
            "max_day_date": max_day_date,
            "repos_with_activity": sum(1 for r in repos if r["total"] > 0),
            "repo_count": len(repos),
        },
        "repos": sorted(repos, key=lambda r: (-r["total"], r["repo"])),
        "days": days,
        "weeks": build_weeks(
            since,
            until,
            dict(global_daily),
            {k: dict(v) for k, v in by_repo_day.items()},
        ),
    }
