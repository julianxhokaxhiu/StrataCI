#!/usr/bin/env bash
set -euo pipefail

version="10.2.0a20260930"
lt_version=100500

case "${VARIANT:?VARIANT is required}" in
  halo)
    family="gfx1151"
    sha256="6ce1f678024f6467080fdddfa0666d2c2c249763235329a41eaac413f05f7b6c"
    tuning_archs="gfx1151"
    ;;
  gfx1150)
    family="gfx1150"
    sha256="a85a55eccf21ba8bfda8f537b4c11fab2a58c4b2599f6f8d00ad3328c23ea804"
    tuning_archs="gfx1150"
    ;;
  rx6000)
    family="gfx103X-all"
    sha256="b022082ff948644cac7637d922fbbfb199b1c7cec665db05e16909ab1cc2ccc0"
    tuning_archs=""
    ;;
  rx7900)
    family="gfx110X-all"
    sha256="5b252faab2b94c7254adc0e99979fb14b4ae70243268ef9d6e4db5729e974ff4"
    tuning_archs="gfx1100"
    ;;
  rx9070)
    family="gfx120X-all"
    sha256="38ff606cf7b5c9658995e6b9d52532720ab2e5544cf96c2a16f1b1f198cfa90b"
    tuning_archs="gfx1201"
    ;;
  *)
    echo "Unsupported HIP variant: $VARIANT" >&2
    exit 1
    ;;
esac

archive="$RUNNER_TEMP/therock-dist-linux-$family-$version.tar.gz"
sdk="$RUNNER_TEMP/therock-$family-$version"
curl --fail --location --retry 3 \
  "https://nightly.repo.amd.com/rocm/core/tarball/therock-dist-linux-$family-$version.tar.gz" \
  --output "$archive"
echo "$sha256  $archive" | sha256sum --check
mkdir -p "$sdk"
tar -xzf "$archive" -C "$sdk"
rm "$archive"
for path in "$sdk/llvm/bin/clang++" "$sdk/include/hipblaslt/hipblaslt-version.h" \
  "$sdk/lib/rocblas/library"; do
  [[ -e "$path" ]] || { echo "Missing ROCm SDK path: $path" >&2; exit 1; }
done
if [[ "$VARIANT" != rx6000 && ! -d "$sdk/lib/hipblaslt/library" ]]; then
  echo "Missing ROCm SDK path: $sdk/lib/hipblaslt/library" >&2
  exit 1
fi

actual_lt_version=$(awk '
  /^#define HIPBLASLT_VERSION_MAJOR[[:space:]]/ { major = $3 }
  /^#define HIPBLASLT_VERSION_MINOR[[:space:]]/ { minor = $3 }
  /^#define HIPBLASLT_VERSION_PATCH[[:space:]]/ { patch = $3 }
  END { print major * 100000 + minor * 100 + patch }
' "$sdk/include/hipblaslt/hipblaslt-version.h")
[[ "$actual_lt_version" == "$lt_version" ]] || {
  echo "Expected hipBLASLt $lt_version, found $actual_lt_version in $family SDK" >&2
  exit 1
}
echo "Verified ROCm $version ($family), hipBLASLt $lt_version"
{
  echo "HP=$sdk"
  echo "CORE=$sdk"
  echo "LIBW=$sdk"
  echo "STRATA_HIPBLASLT_VERSION=$lt_version"
  echo "STRATA_REQUIRED_TUNING_ARCHS=$tuning_archs"
} >> "$GITHUB_ENV"
