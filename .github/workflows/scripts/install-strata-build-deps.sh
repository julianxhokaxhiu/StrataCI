#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --break-system-packages \
  -r strata/terminal/requirements.txt \
  -r strata/terminal/requirements-build.txt
