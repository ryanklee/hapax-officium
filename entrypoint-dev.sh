#!/usr/bin/env bash
set -euo pipefail

# entrypoint-dev.sh — Initialize Claude Code home on first run
# Copies baked-in config to persistent volume, preserving existing data.

CLAUDE_HOME="$HOME/.claude"
CLAUDE_CONFIG_SRC="/app/claude-config"

# First-run: seed Claude Code config from baked-in defaults
if [ ! -f "$CLAUDE_HOME/.initialized" ]; then
    echo "hapax-dev: First run — initializing Claude Code configuration..."

    mkdir -p "$CLAUDE_HOME"

    # Copy config files (don't overwrite if they exist from a previous volume)
    for f in settings.json mcp_servers.json; do
        [ ! -f "$CLAUDE_HOME/$f" ] && cp "$CLAUDE_CONFIG_SRC/$f" "$CLAUDE_HOME/$f"
    done

    # Copy directories
    for d in rules commands agents; do
        if [ ! -d "$CLAUDE_HOME/$d" ] || [ -z "$(ls -A "$CLAUDE_HOME/$d" 2>/dev/null)" ]; then
            mkdir -p "$CLAUDE_HOME/$d"
            cp -r "$CLAUDE_CONFIG_SRC/$d/"* "$CLAUDE_HOME/$d/" 2>/dev/null || true
        fi
    done

    # Ensure audit dir exists on data volume
    mkdir -p "${HAPAX_AUDIT_DIR:-/data/.cache/axiom-audit}"
    mkdir -p "${HAPAX_CACHE_DIR:-/data/.cache}/logos/precedents"

    touch "$CLAUDE_HOME/.initialized"
    echo "hapax-dev: Configuration initialized."
fi

exec "$@"
