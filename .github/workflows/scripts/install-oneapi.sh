#!/usr/bin/env bash
set -euo pipefail

key_url="https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB"
key_file=$(mktemp)
keyring_file=$(mktemp)
trap 'rm -f "$key_file" "$keyring_file"' EXIT
curl -fsSL "$key_url" -o "$key_file"
gpg --batch --yes --dearmor --output "$keyring_file" "$key_file"
sudo install -m 0644 "$keyring_file" /usr/share/keyrings/oneapi-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" \
  | sudo tee /etc/apt/sources.list.d/oneAPI.list
sudo apt-get update
sudo apt-get install -y ocl-icd-libopencl1 intel-oneapi-compiler-dpcpp-cpp intel-oneapi-mkl-devel
