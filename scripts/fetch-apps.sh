#!/bin/bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DEST="$ROOT/build/downloads"
mkdir -p "$DEST"

for lock in "$ROOT/build/applications.lock" "$ROOT/build/sources.lock"; do
  while IFS='|' read -r name version url expected filename; do
    [[ -z "$name" || "$name" == \#* ]] && continue
    target="$DEST/$filename"
    if [[ -f "$target" ]] && printf '%s  %s\n' "$expected" "$target" | sha256sum -c - >/dev/null 2>&1; then
      printf '%s %s already verified\n' "$name" "$version"
      continue
    fi
    tmp=$(mktemp "$DEST/.download.XXXXXX")
    trap 'rm -f -- "$tmp"' EXIT
    curl --fail --location --proto '=https' --tlsv1.2 --retry 3 --output "$tmp" "$url"
    printf '%s  %s\n' "$expected" "$tmp" | sha256sum -c -
    chmod 0644 "$tmp"
    mv -f -- "$tmp" "$target"
    trap - EXIT
  done < "$lock"
done
