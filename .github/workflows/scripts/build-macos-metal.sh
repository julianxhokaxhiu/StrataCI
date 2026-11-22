#!/usr/bin/env bash
set -euo pipefail

version=$(sed -n 's/^[[:space:]]*project([^)]*VERSION[[:space:]]*\([0-9][0-9.]*\).*/\1/p' strata/engine/CMakeLists.txt | head -1)
METAL_CPP_DIR="$PWD/metal-cpp/metal-cpp" \
  bash strata/tools/packaging/mac/build_engine.sh --version "$version" \
  --work "$PWD/strata/pkg-mac-work" --jobs "$(sysctl -n hw.ncpu)"
mkdir -p strata/out-engine-metal
mv strata/pkg-mac-work/pkg-mac/* strata/out-engine-metal/
