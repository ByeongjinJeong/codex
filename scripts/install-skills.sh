#!/usr/bin/env bash
set -euo pipefail

DESTINATION="${1:-$HOME/.codex/skills}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
SOURCE="$REPO_ROOT/skills"

if [ ! -d "$SOURCE" ]; then
  echo "Skills source directory not found: $SOURCE" >&2
  exit 1
fi

mkdir -p "$DESTINATION"

for skill_dir in "$SOURCE"/*; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  target="$DESTINATION/$skill_name"
  mkdir -p "$target"
  cp -R "$skill_dir"/. "$target"/
  echo "Installed skill: $skill_name -> $target"
done

echo "Done. Restart Codex if it was already running."
