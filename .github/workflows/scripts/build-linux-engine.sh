#!/usr/bin/env bash
set -euo pipefail

case "${BACKEND:?BACKEND is required}" in
  cuda)
    cd strata
    VARIANT="${VARIANT:?VARIANT is required}" bash packaging/build_cuda_linux.sh
    ;;
  hip)
    scripts="$PWD/.github/workflows/scripts"
    cd strata
    if [[ -n "${STRATA_REQUIRED_TUNING_ARCHS?ROCm toolchain setup must run before the HIP build}" ]]; then
      mkdir -p "$RUNNER_TEMP/strata-tuning-check"
      python3 packaging/stage_tuning.py \
        --stage "$RUNNER_TEMP/strata-tuning-check" \
        --archs "$STRATA_REQUIRED_TUNING_ARCHS" --rocm "${HP:?HP is required}" \
        --expect "$STRATA_REQUIRED_TUNING_ARCHS"
    fi
    jobs=${JOBS:-$(nproc)}
    if [[ -n "${ARCHS:-}" ]]; then
      VARIANT="${VARIANT:?VARIANT is required}" \
        ARCHS="$ARCHS" \
        JOBS="$jobs" \
        LLAMA="$PWD/third_party/llama.cpp" \
        COMMIT="${COMMIT:?COMMIT is required}" \
        NO_PACKAGE=1 \
        bash packaging/build_hip_linux.sh
    else
      VARIANT="${VARIANT:?VARIANT is required}" \
        JOBS="$jobs" \
        LLAMA="$PWD/third_party/llama.cpp" \
        COMMIT="${COMMIT:?COMMIT is required}" \
        NO_PACKAGE=1 \
        bash packaging/build_hip_linux.sh
    fi
    stage="$PWD/work-$VARIANT/stage"
    pkgver=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$stage/BUILD.json")
    [[ "$pkgver" =~ ^[0-9]+(\.[0-9]+)+$ ]] || { echo "Invalid engine package version in $stage/BUILD.json: $pkgver" >&2; exit 1; }
    python3 "$scripts/prepare_linux_hip_package.py" --stage "$stage" --sdk "$HP"
    arch_list=$(python3 -c 'import json, sys; print("\n".join(json.load(open(sys.argv[1]))["archs"]))' "$stage/BUILD.json")
    arch_args=()
    while IFS= read -r arch; do
      arch_args+=(--arch "$arch")
    done <<< "$arch_list"
    notes="AMD $VARIANT build: engine, CPU picture reader, GPU picture reader"
    if [[ "$VARIANT" == rx6000 ]]; then
      notes+=" (built, not tested on a real RX 6000 card)"
    fi
    python3 packaging/package_engine.py --src "$stage" --backend hip --version "$pkgver" \
      --out "$PWD/work-$VARIANT/components/engine" "${arch_args[@]}" \
      --variant "$VARIANT" --build-id "$COMMIT+rocm" --tree --notes "$notes"
    ;;
  sycl)
    cd strata
    ONEAPI=/opt/intel/oneapi \
      COMMIT="${COMMIT:?COMMIT is required}" \
      bash packaging/build_sycl_linux.sh
    ;;
  *)
    echo "Unsupported Linux engine backend: $BACKEND" >&2
    exit 1
    ;;
esac
