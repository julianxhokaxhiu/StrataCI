# StrataCI

StrataCI builds the engine packages from [Niko1221/Strata](https://github.com/Niko1221/Strata) across the Linux, macOS, and Windows targets used by Strata's release. It collects the verified packages and publishes them as assets in a GitHub Release in this repository.

## Run a build

In the **Actions** tab, run **Build Strata engines**. The workflow uses `STRATA_TAG` for both the upstream Strata checkout and this repository's release tag.

Only Linux AMD HIP gfx1150 Qwen (`strata-engine`) is currently enabled. Strata 0.2.20's official Linux `rx7900` packages cover gfx1150 for Inkling 2 Mini (`strata-inkling`) and Hy4-Flash (`strata-hy4`), so those jobs are disabled. Their matrix templates and all build helpers remain available for future targets. Other GPU/platform entries remain commented out, including ARM64 CUDA/DGX Spark, Hy4 SYCL, and Windows Inkling Strix Halo.

All five Linux HIP targets use AMD's TheRock `10.2.0a20260930` SDK with hipBLASLt 1.5.0 (`100500`). Each GPU-family tarball is verified against its own pinned SHA-256; RX 7000 uses `gfx110X-all`. Windows retains upstream's separate HIP toolchain setup.

Linux HIP package versions come from the upstream HIP recipe's staged `BUILD.json`, not the top-level CMake project version. These versions can intentionally differ: Strata 0.2.6 keeps Qwen engine packages at 0.1.50 while Control and DeepSeek use 0.1.51. The package manifest and archive name follow the staged package version; a source-built binary can still report the CMake build version.

### Strata 0.2.20

The workflow checks out [Strata](https://github.com/Niko1221/Strata) and publishes under the same tag.

The release uses engine version 0.1.66. Its [official release feed](https://github.com/Niko1221/Strata/releases/download/v0.2.20/strata-feed.json) lists gfx1150 in the Linux HIP `rx7900` packages for Inkling and Hy4, but not Qwen. Only Qwen therefore needs a custom gfx1150 build here; use the upstream packages for Inkling and Hy4.

Upstream moved its engine into `engine/`, Terminal dependencies and readers into `terminal/`, and packaging recipes into `tools/packaging/`. All build paths follow this layout. Builds use vendored ggml: they no longer download or override it with llama.cpp. Metal uses upstream's current packaging recipe, including the full quant-header text needed by runtime-compiled kernels.

The Linux HIP toolchain stays pinned to TheRock `10.2.0a20260930`, with hipBLASLt `100500`. Our `lib/` and `.kpack/` staging repair is retained. The enabled Qwen runner is compiled for **gfx1150 only** and includes separate CPU/GPU picture readers. The retained Inkling helper also honors architecture overrides; Inkling and Hy4 have built-in vision and distinct shape-component manifests. DeepSeek remains outside this workflow.

The Qwen source automatically enables its supported gfx11 prompt/decode paths and uses Strata's own prompt kernels instead of the removed llama.cpp MMQ path. No speculative environment overrides are applied. Measurements on RX 7900 or Strix Halo are not gfx1150 measurements; inference correctness, stability, and performance still need testing on the actual card.

Qwen Linux HIP builds check required tuning tables before compilation and require them in the verified final package before archiving: `gfx1150`, `gfx1151`, `gfx1100`, and `gfx1201`. Architectures without a matching upstream table, including RX 6000, retain the engine's untuned fallback. RX 6000 does not require the SDK's hipBLASLt kernel-data directory; its rocBLAS data remains required. The native engine automatically selects a packaged table by GPU architecture and loaded hipBLASLt version. Inkling and Hy4 use their own kernels and do not require Qwen's tuning tables or BLAS kernel-data bundles. Inkling's optional dynamically loaded hipBLASLt acceleration is not bundled; its native HIP kernels remain available. When changing the shared SDK pin, update all five checksums and verify library versions and upstream table coverage together; tuning solution IDs are not interchangeable between library versions.

Each enabled matrix job verifies and uploads its engine package as a temporary workflow artifact. After all enabled builds succeed, the publish job attaches the `.tar.gz` packages to a GitHub Release using `STRATA_TAG`. Disabled targets do not block publishing. Publishing to an existing release does not remove assets from previously enabled targets.

Linux HIP packages retain runtime libraries and rocBLAS/hipBLASLt data under `lib/`, with their referenced SDK kernel sidecars under `.kpack/`. Flattening libraries or omitting those sidecars breaks the SDK's relative kernel lookup, even when hipBLASLt tuning initializes successfully. Staging repairs this layout before upstream generates the hashed package manifest; archive validation checks sidecar references again.

## Enable or add a target

Edit `jobs.build.strategy.matrix.include` in [the workflow](.github/workflows/build-strata-engines.yml). To re-enable an existing OS/GPU combination, uncomment its entire entry, from `- id:` through its last field.

To add Inkling for an existing target, copy its entry, give it a unique `id`, and set `family: inkling`. Inkling supports all existing CUDA/HIP/Metal/SYCL targets and ARM64 CUDA. Hy4 builds currently support Linux x86_64 HIP and SYCL only; use `family: hy4`. Unsupported Hy4 combinations fail explicitly. Omitted `family` defaults to Qwen.

For a new combination, copy an entry with the same OS and backend, then set:

| Field | Purpose |
| --- | --- |
| `id` | Unique artifact/job name, such as `linux-hip-gfx1150`. |
| `os` | Runner label: `ubuntu-24.04`, `ubuntu-24.04-arm`, `windows-2022`, or `macos-26`. |
| `family` | `qwen` (default), `inkling`, or `hy4`. Each produces its own component and asset name. |
| `backend` | `cuda`, `hip`, `sycl` (Linux only), or `metal` (macOS only). |
| `variant` | Toolchain/package family recognized by the build helpers; use `""` for SYCL and Metal. |
| `platform` | Package platform: `linux-x86_64`, `windows-x86_64`, or `macos-arm64`. |
| `archs` | Optional Linux HIP architecture override, separated by semicolons for multiple GPUs. |

Example of a Linux/GPU-specific entry:

```yaml
- id: linux-hip-gfx1150
  os: ubuntu-24.04
  backend: hip
  variant: gfx1150
  archs: gfx1150
  platform: linux-x86_64
```

Adding a matrix row alone does not add support for a new compiler, GPU architecture, or package layout. Wire the corresponding helpers as needed:

- **Linux HIP:** add the variant to [install-rocm-linux.sh](.github/workflows/scripts/install-rocm-linux.sh), with its SDK family, pinned archive checksum, and required tuning architectures. Supply `archs` for a custom variant not recognized by upstream's `packaging/build_hip_linux.sh`. Keep the engine and GPU picture reader on the same architectures. Preserve the runtime layout and tuning checks in [build-linux-engine.sh](.github/workflows/scripts/build-linux-engine.sh) and [archive-linux-engine.sh](.github/workflows/scripts/archive-linux-engine.sh).
- **Windows HIP:** add the same variant and architecture list to both [install-windows-hip.ps1](.github/workflows/scripts/install-windows-hip.ps1) and [archive-windows-engine.ps1](.github/workflows/scripts/archive-windows-engine.ps1). The former selects engine/reader architectures; the latter records them in package metadata.
- **CUDA:** the supported variants are `cuda12` and `cuda13`. For a new toolkit family, update the workflow's toolkit-version selection and the appropriate build recipe: upstream's `tools/packaging/build_cuda_linux.sh` for Linux, or [build-windows-cuda.ps1](.github/workflows/scripts/build-windows-cuda.ps1) for Windows. Set engine and picture-reader architectures, package architecture metadata, and minimum driver requirements consistently. CUDA 12 now includes `sm_120` machine code while retaining `compute_89` PTX. ARM64 uses CUDA 13.0 and `sm_121`; a hosted ARM runner builds the package but does not qualify DGX Spark hardware.
- **macOS Metal / Linux SYCL:** use the existing entries and helpers for the supported platform. A different CPU architecture or runner OS requires checking upstream support and package platform metadata, not just changing `id`.

Linux conditions use `runner.os`, including the ARM runner. Desktop setup still matches the documented runner labels. If adding another OS, ensure the job selects exactly one build path and one archive path.

Before publishing, verify unique IDs and asset names, run `python -m unittest discover -s .github/workflows/scripts -p 'test_*.py'`, and run the enabled matrix end-to-end. All enabled builds must pass before publishing; compilation and packaging checks do not replace GPU hardware testing. The archives are unsigned local components, not additions to upstream's signed update feed.

## Repository layout

- `.github/workflows/build-strata-engines.yml` defines build matrices, hosted runners, and release publishing.
- `.github/workflows/scripts/` contains the platform-specific setup, build, packaging, and archive helpers.

The Strata source is checked out during each workflow run; it is not vendored in this repository. Only the Qwen gfx1150 Ubuntu job is currently enabled.
