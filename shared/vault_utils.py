"""Shared utilities for reading vault/DATA_DIR content.

Thin wrapper around shared.frontmatter for callers that only need the
frontmatter dict (not the body text).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.frontmatter import parse_frontmatter as _parse_fm

if TYPE_CHECKING:
    from pathlib import Path


def parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file.

    Returns empty dict on any parse failure (missing file, missing markers,
    invalid YAML, etc.).
    """
    fm, _body = _parse_fm(path)
    return fm
