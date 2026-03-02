#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version-tag>" >&2
  echo "Examples: $0 v2.0.0-rc1 | $0 v2.0.0" >&2
  exit 1
fi

TAG="$1"
if [[ ! "$TAG" =~ ^v2\.0\.0(-rc[0-9]+)?$ ]]; then
  echo "Refusing unexpected tag: $TAG" >&2
  exit 1
fi

git tag -a "$TAG" -m "ECIMS release $TAG"
echo "Created annotated tag $TAG"
