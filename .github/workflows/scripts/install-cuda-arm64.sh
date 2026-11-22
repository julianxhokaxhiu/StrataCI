#!/usr/bin/env bash
set -euo pipefail

keyring="$RUNNER_TEMP/cuda-keyring.deb"
curl --fail --location --retry 3 \
  https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/sbsa/cuda-keyring_1.1-1_all.deb \
  --output "$keyring"
sudo dpkg -i "$keyring"
sudo apt-get update
sudo apt-get install -y cuda-toolkit-13-0
echo "/usr/local/cuda-13.0/bin" >> "$GITHUB_PATH"
echo "CUDA_PATH=/usr/local/cuda-13.0" >> "$GITHUB_ENV"
