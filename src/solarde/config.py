"""Tiny YAML config loader shared by all CLI entry points.

Training runs will move to Hydra (see docs/ROADMAP.md, M4); the label and split
steps only need plain YAML so they stay dependency-light.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve(path: str | Path) -> Path:
    """Resolve a repo-relative path to an absolute one."""
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p
