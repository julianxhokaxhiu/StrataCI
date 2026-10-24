#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --break-system-packages \
  -r strata/requirements.txt \
  -r strata/requirements-build.txt
python3 -c "import sys; sys.path.insert(0, 'strata'); import setup; setup.get_llama_cpp()"
