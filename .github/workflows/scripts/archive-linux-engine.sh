#!/usr/bin/env bash
set -euo pipefail

case "${BACKEND:?BACKEND is required}" in
  cuda) output="strata/out-engine-${VARIANT:?VARIANT is required}" ;;
  hip) output="strata/work-${VARIANT:?VARIANT is required}/components/engine" ;;
  sycl) output="strata/out-engine-sycl" ;;
  *) echo "Unsupported Linux engine backend: $BACKEND" >&2; exit 1 ;;
esac

package=$(find "$output" -mindepth 1 -maxdepth 1 -type d ! -name '.*' -print -quit)
[[ -n "$package" ]] || { echo "No engine package produced in $output" >&2; exit 1; }
python3 strata/packaging/package_engine.py --verify "$package"

if [[ "$BACKEND" == hip ]]; then
  python3 .github/workflows/scripts/prepare_linux_hip_package.py --stage "$package" --verify
  lt_version=$(sed -n 's/.*"hipblaslt_version":[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$package/BUILD.json")
  [[ "$lt_version" == "${STRATA_HIPBLASLT_VERSION:?ROCm toolchain setup must run before archiving}" ]] || {
    echo "Unexpected hipBLASLt version in $package/BUILD.json: $lt_version" >&2
    exit 1
  }
  for arch in ${STRATA_REQUIRED_TUNING_ARCHS?ROCm toolchain setup must run before archiving}; do
    table="$package/tuning/$arch-hipblaslt-$lt_version.txt"
    [[ -s "$table" ]] || { echo "Missing required tuning table: $table" >&2; exit 1; }
    grep -qx "STRATA_HIPBLASLT_TUNING_V1 $arch $lt_version" "$table" || {
      echo "Invalid tuning table header: $table" >&2
      exit 1
    }
    echo "Verified $arch tuning table for hipBLASLt $lt_version"
  done
fi

version=${package##*/}
version=${version%%-*}
asset="strata-engine-$version-${PLATFORM:?PLATFORM is required}-$BACKEND"
[[ -z "${VARIANT:-}" ]] || asset="$asset-$VARIANT"
mkdir -p dist
tar -C "$package" -czf "dist/$asset.tar.gz" .
echo "Built dist/$asset.tar.gz"
