"""Thin git helpers (read-only)."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


def run_git(cwd: Path, args: list[str]) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return ""
    return r.stdout


def has_git(cwd: Path) -> bool:
    return (cwd / ".git").exists()


def ref_exists(cwd: Path, ref: str) -> bool:
    if ref == "HEAD":
        return True
    if ref.startswith("origin/"):
        return (
            subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/{ref}"],
                cwd=cwd,
            ).returncode
            == 0
        )
    return (
        subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{ref}"],
            cwd=cwd,
        ).returncode
        == 0
    )


def pick_ref(cwd: Path, prefs: list[str]) -> str | None:
    for ref in prefs:
        if ref_exists(cwd, ref):
            return ref
    return None


def author_args(emails: list[str]) -> list[str]:
    args: list[str] = []
    for email in emails:
        args.extend(["--author", email])
    return args


def _window(until: date) -> str:
    return (until + timedelta(days=1)).isoformat()


def count_commits(
    cwd: Path,
    ref: str,
    emails: list[str],
    since: date,
    until: date,
    merges_only: bool = False,
) -> int:
    args = ["rev-list", "--count"]
    if merges_only:
        args.append("--merges")
    args += [
        ref,
        *author_args(emails),
        f"--since={since.isoformat()}",
        f"--until={_window(until)}",
    ]
    out = run_git(cwd, args).strip()
    try:
        return int(out or "0")
    except ValueError:
        return 0


def daily_counts(
    cwd: Path,
    ref: str,
    emails: list[str],
    since: date,
    until: date,
) -> dict[str, int]:
    args = [
        "log",
        ref,
        *author_args(emails),
        f"--since={since.isoformat()}",
        f"--until={_window(until)}",
        "--format=%ad",
        "--date=short",
    ]
    out = run_git(cwd, args)
    counts: dict[str, int] = defaultdict(int)
    for line in out.splitlines():
        d = line.strip()
        if d:
            counts[d] += 1
    return dict(counts)


def daily_merge_subjects(
    cwd: Path,
    ref: str,
    emails: list[str],
    since: date,
    until: date,
) -> dict[str, list[str]]:
    args = [
        "log",
        ref,
        "--merges",
        *author_args(emails),
        f"--since={since.isoformat()}",
        f"--until={_window(until)}",
        "--format=%ad%x00%s",
        "--date=short",
    ]
    out = run_git(cwd, args)
    by_day: dict[str, list[str]] = defaultdict(list)
    for line in out.splitlines():
        if "\x00" not in line:
            continue
        d, subj = line.split("\x00", 1)
        d, subj = d.strip(), subj.strip()
        if d:
            by_day[d].append(subj)
    return dict(by_day)


def is_mr_merge_into(subject: str, into_branch: str) -> bool:
    """Match GitLab-style: Merge branch 'x' into 'dev'."""
    s = subject.lower()
    target = into_branch.lower()
    return s.startswith("merge branch") and (
        f" into '{target}'" in s or f' into "{target}"' in s
    )


def first_last(
    cwd: Path,
    ref: str,
    emails: list[str],
    since: date,
    until: date,
) -> tuple[str | None, str | None]:
    args = [
        "log",
        ref,
        *author_args(emails),
        f"--since={since.isoformat()}",
        f"--until={_window(until)}",
        "--format=%ad",
        "--date=short",
    ]
    dates = [ln.strip() for ln in run_git(cwd, args).splitlines() if ln.strip()]
    if not dates:
        return None, None
    return dates[-1], dates[0]
