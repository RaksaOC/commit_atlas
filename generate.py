#!/usr/bin/env python3
"""Generate a commit atlas from a TOML config.

Writes JSON/markdown/HTML under the configured output dir, plus index.html
at the repo root (for GitHub Pages).

Usage:
  python generate.py
  python generate.py -c config.toml
  python generate.py -c config.toml -o out
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent))

from atlas.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
