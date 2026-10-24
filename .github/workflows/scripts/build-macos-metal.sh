#!/usr/bin/env bash
set -euo pipefail

llama="$PWD/strata/third_party/llama.cpp"
test -d "$llama/ggml"

cmake -S strata/metal -B strata/build-metal -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DMETAL_CPP_DIR="$PWD/metal-cpp/metal-cpp" -DSTRATA_GGML_DIR="$llama"
cmake --build strata/build-metal --target strata
bash strata/packaging/build_vision_mac.sh --llama "$llama" --out "$PWD/strata/vision"
python .github/workflows/scripts/package-macos-metal.py "$PWD/strata"
