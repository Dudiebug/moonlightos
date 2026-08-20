#!/bin/bash
set -Eeuo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -d "$ROOT/build/work" ]] && command -v lb >/dev/null && [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  (cd "$ROOT/build/work" && lb clean --purge) || true
fi
for target in "$ROOT/build/work" "$ROOT/build/out"; do
  [[ -d "$target" ]] || continue
  find "$target" -depth -mindepth 1 -delete
  rmdir "$target"
done
