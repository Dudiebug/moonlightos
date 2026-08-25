#!/bin/bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

usage() {
  echo 'usage: release-evidence.sh artifact FILE [EXPECTED_SHA256] | provenance TAG SOURCE_TARBALL' >&2
  exit 64
}

[[ $# -ge 2 ]] || usage
mode=$1
shift

case "$mode" in
  artifact)
    [[ $# -le 2 && -f $1 ]] || usage
    file=$1
    actual=$(sha256sum "$file" | cut -d ' ' -f 1)
    printf 'file=%s\nbytes=%s\nsha256=%s\n' "$file" "$(stat -c %s "$file")" "$actual"
    if [[ -n ${2:-} && $actual != "$2" ]]; then
      echo "SHA-256 mismatch: expected $2" >&2
      exit 1
    fi
    ;;
  provenance)
    [[ $# == 2 && -f $2 ]] || usage
    tag=$1
    archive=$2
    git -C "$ROOT" rev-parse --verify "$tag^{commit}" >/dev/null
    work=$(mktemp -d)
    trap 'find "$work" -depth -delete' EXIT
    mkdir "$work/archive"
    tar -xzf "$archive" --strip-components=1 -C "$work/archive"
    while IFS= read -r -d '' record; do
      metadata=${record%%$'\t'*}
      path=${record#*$'\t'}
      read -r _mode type object <<< "$metadata"
      [[ $type == blob ]] || { echo "Unsupported Git tree entry: $record" >&2; exit 1; }
      digest=$(git -C "$ROOT" cat-file blob "$object" | sha256sum | cut -d ' ' -f 1)
      printf '%s\t%s\n' "$path" "$digest"
    done < <(git -C "$ROOT" ls-tree -rz "$tag") | LC_ALL=C sort > "$work/tag.map"
    (
      cd "$work/archive"
      while IFS= read -r -d '' path; do
        relative=${path#./}
        if [[ -L $path ]]; then
          digest=$(printf %s "$(readlink "$path")" | sha256sum | cut -d ' ' -f 1)
        else
          digest=$(sha256sum "$path" | cut -d ' ' -f 1)
        fi
        printf '%s\t%s\n' "$relative" "$digest"
      done < <(find . \( -type f -o -type l \) -print0)
    ) | LC_ALL=C sort > "$work/archive.map"
    cmp "$work/tag.map" "$work/archive.map"
    printf 'tag=%s\ncommit=%s\nsource_file=%s\nsource_bytes=%s\nsource_sha256=%s\nrelative_file_map=match\n' \
      "$tag" "$(git -C "$ROOT" rev-parse "$tag^{commit}")" "$archive" \
      "$(stat -c %s "$archive")" "$(sha256sum "$archive" | cut -d ' ' -f 1)"
    ;;
  *) usage ;;
esac
