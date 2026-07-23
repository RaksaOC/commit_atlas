"""Load and validate atlas config (TOML)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class RepoConfig:
    name: str
    path: str
    branches: list[str]
    display: str | None = None

    @property
    def label(self) -> str:
        return self.display or self.name


@dataclass
class AtlasConfig:
    author_name: str
    author_emails: list[str]
    since: date
    until: date
    workspace_root: Path
    repos: list[RepoConfig]
    subtitle: str = "Commits across the selected period"
    disclaimer: str = ""
    aliases: dict[str, str] = field(default_factory=dict)
    count_mr_events: bool = True
    mr_into_branch: str = "dev"
    include_paths: bool = False
    output_dir: Path | None = None
    config_path: Path | None = None

    def resolve_repo_path(self, repo: RepoConfig) -> Path:
        raw = os.path.expandvars(repo.path)
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (self.workspace_root / p).resolve()
        return p


def _require(d: dict, key: str, ctx: str) -> object:
    if key not in d:
        raise ValueError(f"Missing `{key}` in {ctx}")
    return d[key]


def load_config(path: Path) -> AtlasConfig:
    path = path.resolve()
    raw = tomllib.loads(path.read_text())

    author = _require(raw, "author", "config")
    assert isinstance(author, dict)
    name = str(_require(author, "name", "[author]"))
    emails = _require(author, "emails", "[author]")
    if not isinstance(emails, list) or not emails:
        raise ValueError("[author].emails must be a non-empty list")

    rng = _require(raw, "range", "config")
    assert isinstance(rng, dict)
    since = date.fromisoformat(str(_require(rng, "since", "[range]")))
    until = date.fromisoformat(str(_require(rng, "until", "[range]")))
    if until < since:
        raise ValueError("[range].until must be >= since")

    tool_root = path.parent if path.parent.name != "configs" else path.parent.parent
    workspace = raw.get("workspace_root", "..")
    workspace_root = Path(os.path.expandvars(str(workspace))).expanduser()
    if not workspace_root.is_absolute():
        # Relative to the config file's directory
        workspace_root = (path.parent / workspace_root).resolve()

    display = raw.get("display") or {}
    options = raw.get("options") or {}
    privacy = raw.get("privacy") or {}

    repos_raw = _require(raw, "repos", "config")
    if not isinstance(repos_raw, list) or not repos_raw:
        raise ValueError("`repos` must be a non-empty list")

    repos: list[RepoConfig] = []
    aliases: dict[str, str] = dict(display.get("aliases") or {})

    for i, item in enumerate(repos_raw):
        if not isinstance(item, dict):
            raise ValueError(f"repos[{i}] must be a table")
        rname = str(_require(item, "name", f"repos[{i}]"))
        rpath = str(item.get("path") or rname)
        branches = item.get("branches") or ["origin/main", "main", "origin/master", "master", "HEAD"]
        if not isinstance(branches, list) or not branches:
            raise ValueError(f"repos[{i}].branches must be a non-empty list")
        disp = item.get("display")
        if disp:
            aliases[rname] = str(disp)
        repos.append(
            RepoConfig(
                name=rname,
                path=rpath,
                branches=[str(b) for b in branches],
                display=str(disp) if disp else None,
            )
        )

    out = options.get("output_dir")
    output_dir = None
    if out:
        output_dir = Path(str(out))
        if not output_dir.is_absolute():
            output_dir = (tool_root / output_dir).resolve()

    return AtlasConfig(
        author_name=name,
        author_emails=[str(e) for e in emails],
        since=since,
        until=until,
        workspace_root=workspace_root,
        repos=repos,
        subtitle=str(display.get("subtitle") or "Commits across the selected period"),
        disclaimer=str(display.get("disclaimer") or ""),
        aliases=aliases,
        count_mr_events=bool(options.get("count_mr_events", True)),
        mr_into_branch=str(options.get("mr_into_branch") or "dev"),
        include_paths=bool(privacy.get("include_paths", False)),
        output_dir=output_dir or (tool_root / "out"),
        config_path=path,
    )
