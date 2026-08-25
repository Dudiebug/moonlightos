#!/bin/bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

printf 'commit=%s\n' "$(git rev-parse HEAD)"
printf 'tree=%s\n' "$(git rev-parse HEAD^{tree})"
printf 'archive_sha256='
git archive --format=tar HEAD | sha256sum | cut -d ' ' -f 1
if [[ -n $(git status --porcelain --untracked-files=normal) ]]; then
  printf 'working_tree=modified\n'
else
  printf 'working_tree=clean\n'
fi
