# Commit Atlas

**v1.0.0** — Local git → interactive contribution report (heatmap + breakdown). No server, no deps beyond Python 3.11+ and `git`.

For deep technical detail (TOML keys, counting rules, pipeline), see **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## Quick start

```bash
cd commit_atlas
cp config.example.toml config.toml   # edit author, dates, repos
python3 generate.py -c config.toml
open out/contribution.html
```

Shipped profile example:

```bash
python3 generate.py -c config.toml
open out/contribution.html
```

## What’s in 1.0.0

- Multi-repo TOML config (`display` aliases, privacy-safe outputs)
- Commit + optional GitLab-style MR open/accept estimates
- Static HTML atlas (animations, color palette) + JSON/Markdown exports
- Skip missing optional repos without failing the run

## Host on GitHub Pages

The report is a single static file — fork the repo, generate with your config, commit `out/contribution.html`, then in **Settings → Pages** point the source at the `out/` folder (or copy/rename that file to `index.html` and publish from `/` or `/docs`). No build step on Pages required.

## Later

More flexible counting, pluggable / themeable UI, optional GitLab/GitHub APIs, packaged install — see the roadmap section in [ARCHITECTURE.md](ARCHITECTURE.md#9-versioning).

## License

MIT — [LICENSE](LICENSE).
