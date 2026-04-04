#!/usr/bin/env bash
# install-units.sh — Symlink systemd user units from repo to ~/.config/systemd/user/
# and reload the daemon. Safe to run idempotently.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../units" && pwd)"
DEST_DIR="${HOME}/.config/systemd/user"

mkdir -p "$DEST_DIR"

changed=0
for unit in "$REPO_DIR"/*.service "$REPO_DIR"/*.timer "$REPO_DIR"/*.target "$REPO_DIR"/*.path; do
    [ -f "$unit" ] || continue
    name="$(basename "$unit")"
    dest="$DEST_DIR/$name"
    if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$unit" ]; then
        continue
    fi
    ln -sf "$unit" "$dest"
    echo "linked: $name"
    changed=$((changed + 1))
done

if [ "$changed" -gt 0 ]; then
    systemctl --user daemon-reload
    echo "daemon-reload done ($changed units linked)"
else
    echo "all units up to date"
fi
