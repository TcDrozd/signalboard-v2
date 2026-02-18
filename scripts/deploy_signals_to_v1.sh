#!/usr/bin/env bash
set -euo pipefail

V2_ROOT="/home/tcd/signalboard-v2"
V1_ROOT="/home/tcd/signalboard"

SRC="${V2_ROOT}/signals"
DEST="${V1_ROOT}/signals"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: v2 signals dir not found: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST"

# Copy only *new* files (no overwrites)
# -n = --no-clobber
# --parents keeps nested subdirs if you have them (optional; harmless if flat)
echo "Copying NEW signals from:"
echo "  $SRC"
echo "to:"
echo "  $DEST"
echo

# If you only want signal modules named like *.py
# and want to skip __pycache__ and such:
shopt -s globstar nullglob
new_count=0

for f in "$SRC"/**/*.py; do
  # skip caches / hidden dirs if any
  [[ "$f" == *"__pycache__"* ]] && continue

  rel="${f#$SRC/}"
  target="${DEST}/${rel}"

  if [[ -e "$target" ]]; then
    continue
  fi

  mkdir -p "$(dirname "$target")"
  cp -v "$f" "$target"
  new_count=$((new_count + 1))
done

echo
echo "Done. New signals copied: ${new_count}"
