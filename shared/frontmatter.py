"""Canonical YAML frontmatter parsing for markdown files.

Single source of truth for the frontmatter regex and parsing logic used by
management_bridge, cockpit/data/management, cockpit/engine/watcher, and
shared/vault_utils.

All markdown files in DATA_DIR use the ``---`` delimited YAML frontmatter
format.  This module provides two entry points:

- ``parse_frontmatter(path)`` — returns (dict, body_str)
- ``parse_frontmatter_text(text)`` — same, from a string
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pathlib import Path

# The canonical regex.  Captures:
#   group(1) = raw YAML between the --- delimiters
#   group(2) = body text after the closing ---
_FM_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?(.*)", re.DOTALL)


def parse_frontmatter_text(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown string.

    Returns ``(frontmatter_dict, body_text)``.  On any error returns
    ``({}, text)`` so callers always get usable values.
    """
    match = _FM_RE.match(text)
    if not match:
        return {}, text

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}, text

    if not isinstance(fm, dict):
        return {}, text

    return fm, match.group(2)


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown file on disk.

    Returns ``(frontmatter_dict, body_text)``.  On any I/O or parse error
    returns ``({}, "")``.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, ""

    fm, body = parse_frontmatter_text(text)
    if not fm and not body:
        # File was readable but frontmatter didn't match — return raw text as body
        return {}, text
    return fm, body
