#!/usr/bin/env bash
set -euo pipefail

curl -fsSL https://developer.apple.com/metal/cpp/files/metal-cpp_26.zip -o metal-cpp.zip
echo "4df3c078b9aadcb516212e9cb03004cbc5ce9a3e9c068fa3144d021db585a3a4  metal-cpp.zip" \
  | shasum -a 256 -c -
unzip -q metal-cpp.zip -d metal-cpp
