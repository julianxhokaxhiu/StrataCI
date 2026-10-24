#!/usr/bin/env bash
set -euo pipefail

echo "commit=$(git -C strata rev-parse HEAD)" >> "$GITHUB_OUTPUT"
