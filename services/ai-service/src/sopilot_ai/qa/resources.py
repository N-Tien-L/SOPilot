"""Loader for the YAML rule files that sit next to the ``qa`` modules (TECH-V2-ai-service §7.1).

Rules, vocabularies and fixed sentences live in YAML, not in code, so the owner can review them.
"""
from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

_DIR = Path(__file__).resolve().parent


@cache
def load_yaml(name: str) -> dict[str, Any]:
    """Parse ``qa/<name>`` once. Callers must treat the result as read-only."""
    data = yaml.safe_load((_DIR / name).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a mapping at the top level")
    return data
