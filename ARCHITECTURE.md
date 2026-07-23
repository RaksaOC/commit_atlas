# Architecture — Commit Atlas

Deep technical reference for **Commit Atlas v1.0.0**.  
For a short how-to, see [README.md](README.md).

---

## 1. Purpose

Commit Atlas turns **local git history** into a static, shareable report:

1. Scan one or more clones with read-only `git` commands  
2. Aggregate commits (and optional GitLab-style MR open/accept estimates)  
3. Emit **JSON** + **Markdown** + a self-contained **HTML** page (`file://` friendly)

No server, no database, no network API. The HTML embeds the JSON at build time so you can host or email a single file.

---

## 2. High-level pipeline

```
┌─────────────────┐
│  TOML config    │  author, range, repos, display, options
└────────┬────────┘
         │  atlas.config.load_config()
         ▼
┌─────────────────┐
│  AtlasConfig    │  resolved paths, validated dates
└────────┬────────┘
         │  atlas.analyze.analyze()
         │    └─ atlas.gitops.*  (git rev-list / log)
         ▼
┌─────────────────┐
│  data dict      │  summary, repos[], days[], weeks[][], display
└────────┬────────┘
         │  atlas.report.write_*()
         ▼
┌──────────────────────────────────────────┐
│  out/contributions-data.json             │
│  out/contributions.md                    │
│  out/contribution.html  ← template+JSON  │
└──────────────────────────────────────────┘
```

CLI entry points:

| Command | Role |
|---|---|
| `python generate.py -c …` | Thin wrapper; preferred |
| `python -m atlas -c …` | Same via `atlas/__main__.py` |

---

## 3. Package layout

```
commit_atlas/
├── generate.py                 # CLI shim
├── config.example.toml         # starter config
├── chanraksa.toml              # example public profile
├── atlas/
│   ├── __init__.py             # __version__
│   ├── __main__.py             # argparse CLI
│   ├── config.py               # TOML → AtlasConfig
│   ├── gitops.py               # read-only git helpers
│   ├── analyze.py              # aggregation + payload
│   └── report.py               # JSON / MD / HTML writers
├── templates/
│   └── atlas.html.template     # UI; __DATA__ placeholder
└── out/                        # generated artifacts (gitignored)
```

**Design rules**

- **stdlib only** (Python 3.11+ for `tomllib`)  
- **No mutation** of git repos (only `git log` / `rev-list` / `show-ref`)  
- **Config owns identity** — the template is generic; names/subtitles/aliases come from JSON  

---

## 4. Configuration (TOML)

Configs are plain TOML. **Top-level keys must not sit under a table** — e.g. `workspace_root` belongs at the root of the file, not under `[range]`.

### 4.1 Root keys

| Key | Type | Required | Description |
|---|---|---|---|
| `workspace_root` | string | no (default `".."`) | Base directory for relative `repos[].path`. Resolved relative to the **config file’s directory**. Supports `~` and `$ENV` via expanduser/expandvars. |

### 4.2 `[author]`

| Key | Type | Required | Description |
|---|---|---|---|
| `name` | string | **yes** | Display name in splash, header, markdown, `<title>` |
| `emails` | string[] | **yes** | Passed to `git log --author` / `rev-list --author` (one flag per email). Use every casing you commit with. |

### 4.3 `[range]`

| Key | Type | Required | Description |
|---|---|---|---|
| `since` | `YYYY-MM-DD` | **yes** | Inclusive start (author date) |
| `until` | `YYYY-MM-DD` | **yes** | Inclusive end. Internally git uses `--until=(until+1 day)` so the full calendar day is included. |

### 4.4 `[display]`

| Key | Type | Required | Description |
|---|---|---|---|
| `subtitle` | string | no | Header blurb under the name |
| `disclaimer` | string | no | Small note under the breakdown table (`*` prefixed in UI). Empty → hidden |
| `aliases` | table | no | Extra `id → label` map. Prefer per-repo `display` instead; both merge into `display.aliases` in the JSON |

### 4.5 `[options]`

| Key | Type | Default | Description |
|---|---|---|---|
| `count_mr_events` | bool | `true` | When true, each GitLab-style merge commit into `mr_into_branch` adds **+2** (open MR + accept MR) to merges + daily totals |
| `mr_into_branch` | string | `"dev"` | Target branch name matched in merge subjects: `Merge branch '…' into 'dev'` |
| `output_dir` | string | `"out"` | Relative to the tool root (`commit_atlas/`), unless absolute |

### 4.6 `[privacy]`

| Key | Type | Default | Description |
|---|---|---|---|
| `include_paths` | bool | `false` | If true, each repo entry in JSON includes absolute `path`. Keep **false** for shareable HTML/JSON |

### 4.7 `[[repos]]` (array of tables)

| Key | Type | Required | Description |
|---|---|---|---|
| `name` | string | **yes** | Stable id (often the folder name). Used as `id` in JSON |
| `path` | string | no (defaults to `name`) | Relative to `workspace_root`, or absolute / env-expanded |
| `display` | string | no | Public label in UI and heatmap (`repo` field). If set, also registered in aliases |
| `branches` | string[] | no | Tried **in order**; first existing ref wins. Default: `origin/main`, `main`, `origin/master`, `master`, `HEAD` |

**Branch resolution** (`gitops.pick_ref`):

- `origin/foo` → `refs/remotes/origin/foo`  
- `foo` → `refs/heads/foo`  
- `HEAD` → always valid  

Missing path or missing `.git` → repo is **skipped** (no fatal error). Useful for optional sibling projects.

### 4.8 Example (minimal)

```toml
workspace_root = "."

[author]
name = "Ada Lovelace"
emails = ["ada@example.com"]

[range]
since = "2025-01-01"
until = "2025-03-31"

[display]
subtitle = "Commits across 3 months"

[options]
count_mr_events = false
output_dir = "out"

[privacy]
include_paths = false

[[repos]]
name = "engine"
path = "engine"
branches = ["origin/main", "main"]
```

---

## 5. Counting semantics

### 5.1 What is a “commit” here?

For each resolved `(repo, ref)`:

| Metric | Source |
|---|---|
| All commits on ref in window by author | `git rev-list --count <ref> --author … --since … --until …` |
| Merge commits | same + `--merges` |
| Regular | all − merges |
| Daily buckets | `git log --format=%ad --date=short` → histogram by day |

Author date (`%ad`) drives day buckets (same as typical contribution calendars).

### 5.2 MR event inflation (`count_mr_events`)

GitLab’s contribution feed often counts **open MR** and **accept MR** separately from pushes. Local git cannot see MR API events, so we approximate:

1. Find merge commits whose subject matches  
   `merge branch … into '<mr_into_branch>'` (case-insensitive)  
2. For each such merge on day `D`, add **+2** to that day’s count and to the repo’s `merges` / `total`

Stored fields per repo:

| Field | Meaning |
|---|---|
| `merge_commits` | Real git merge commits |
| `mr_events` | Estimated open+accept count (`2 ×` matching merges) |
| `merges` | `merge_commits + mr_events` (UI “merge” bucket when shown) |
| `total` | `regular + merges` |

This is intentionally a **heuristic**, not a GitLab API sync.

### 5.3 Heatmap grid (`weeks`)

- Pad to full Sun→Sat weeks around `[since, until]`  
- Each cell: `{ date, count, in_range, by_repo }`  
- `by_repo` keys use **display labels** (public names), not filesystem paths  

---

## 6. Output payload (`contributions-data.json`)

Top-level shape:

```json
{
  "author": { "name": "…", "emails": ["…"] },
  "range": { "since": "…", "until": "…" },
  "generated_at": "ISO-8601",
  "display": {
    "subtitle": "…",
    "disclaimer": "…",
    "aliases": { "mobile-ccn": "mobile-nurse" }
  },
  "summary": {
    "total_commits": 0,
    "regular_commits": 0,
    "merge_commits": 0,
    "active_days": 0,
    "max_day_count": 0,
    "max_day_date": "YYYY-MM-DD",
    "repos_with_activity": 0,
    "repo_count": 0
  },
  "repos": [ /* sorted by total desc */ ],
  "days": [ /* one entry per calendar day in range */ ],
  "weeks": [ /* heatmap columns */ ]
}
```

The HTML template substitutes `__DATA__` with this JSON (escaped for `</script>` safety).

---

## 7. HTML / UI layer

`templates/atlas.html.template` is a single-file UI:

- **No build step** beyond string replace of `__DATA__`  
- Reads `DATA.author`, `DATA.display`, `DATA.summary`, `DATA.weeks`, `DATA.repos`  
- Client-only animations (splash curtains, heatmap reveal, count-up, table staircase)  
- Palette picker mutates CSS variables; choice stored in `localStorage`  
- Repo labels: `display.aliases[id] || name` (and analyze already emits display labels as `repo`)

UI presentation choices (e.g. hiding regular/merge split, showing peak day) live in the template JS — the JSON still contains the full breakdown for tools/markdown.

---

## 8. Privacy model (v1)

| Concern | Behavior |
|---|---|
| Absolute paths | Omitted unless `privacy.include_paths = true` |
| Internal repo names | Override with `display` / aliases |
| Optional repos | Missing dirs → skip, don’t fail the run |
| Network | Never called |

Emails in JSON are still present (needed for provenance). Don’t publish a config that contains emails you’re unwilling to share.

---

## 9. Versioning

| Version | Status |
|---|---|
| **1.0.0** | Current — config-driven multi-repo atlas, MR heuristic, static HTML |

`atlas.__version__` tracks the library version.

### Current feature set (1.0.0)

- Multi-repo TOML config  
- Author email filtering (multiple casings)  
- Branch preference lists  
- Daily heatmap + per-repo breakdown  
- Optional GitLab-style MR open/accept inflation  
- Display aliases + disclaimer  
- Static HTML with intro animations + theme palette  
- Markdown + JSON exports  

### Likely directions (post-1.0)

Not implemented yet — sketched for roadmap only:

- More flexible counting (commit types, path filters, timezone policy)  
- Pluggable UI themes / layout variants (dashboard vs one-pager)  
- Optional remote providers (GitLab/GitHub contribution APIs) instead of heuristics  
- Config schema validation CLI / JSON Schema  
- Packaging (`pip install`) and versioned template themes  

---

## 10. Extension points

| Goal | Where to change |
|---|---|
| New git metric | `gitops.py` + fold into `analyze.py` |
| New config knobs | `config.py` + document here |
| New export format | `report.py` |
| New look & feel | `templates/atlas.html.template` |
| New CLI flags | `atlas/__main__.py` |

Keep the data contract (`summary` / `repos` / `weeks`) stable when possible so older HTML templates keep working.
