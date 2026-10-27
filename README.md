# StrataCI

StrataCI builds the engine packages from [Niko1221/Strata](https://github.com/Niko1221/Strata) across the Linux, macOS, and Windows targets used by Strata's release. It collects the verified packages and publishes them as assets in a GitHub Release in this repository.

## Run a build

In the **Actions** tab, run **Build Strata engines**. The workflow uses `STRATA_TAG` for both the upstream Strata checkout and this repository's release tag.

Only Linux AMD HIP gfx1150 is currently enabled. The other 13 matrix entries are preserved as comments: Linux CUDA 12 and 13, Linux AMD HIP (Halo, RX 6000, RX 7900, and RX 9070), Linux Intel SYCL, macOS Apple Silicon Metal, Windows CUDA 12 and 13, and Windows AMD HIP (RDNA2, RDNA3, and RX 9070).

All five Linux HIP targets use AMD's TheRock `10.2.0a20260930` SDK with hipBLASLt 1.5.0 (`100500`). Each GPU-family tarball is verified against its own pinned SHA-256; RX 7000 uses `gfx110X-all`. Windows retains upstream's separate HIP toolchain setup.

Linux HIP package versions come from the upstream HIP recipe's staged `BUILD.json`, not the top-level CMake project version. These versions can intentionally differ: Strata 0.2.6 keeps Qwen engine packages at 0.1.50 while Control and DeepSeek use 0.1.51. The package manifest and archive name follow the staged package version; a source-built binary can still report the CMake build version.

### Strata 0.2.7

The workflow checks out [Strata v0.2.7](https://github.com/Niko1221/Strata/releases/tag/v0.2.7) and publishes under the same tag. Upstream now versions both Qwen and DeepSeek engine packages as **0.1.52**. The enabled gfx1150 target picks up this version from the HIP recipe automatically; no package-version override is needed.

The release includes Qwen performance changes for small NVIDIA cards and RX 9000 GPUs, faster DeepSeek prompting, Windows Strix Halo DeepSeek support, expanded chat UI, French localization, and engine correctness fixes. Performance improvements measured on those GPUs should not be assumed to apply to gfx1150.

The Linux HIP toolchain stays pinned to TheRock `10.2.0a20260930`: the 0.2.7 HIP recipe retains its compiler/runtime layout, and its gfx1150 tuning table still targets hipBLASLt `100500`. Our `lib/` and `.kpack/` staging repair remains necessary. The new Windows Strix Halo DeepSeek package targets **gfx1151**, not gfx1150; this workflow still builds the gfx1150 Qwen engine and its CPU/GPU picture readers, not a DeepSeek engine for that GPU. Other targets remain commented out.

Linux HIP builds check required tuning tables before compilation and require them in the verified final package before archiving: `gfx1150`, `gfx1151`, `gfx1100`, and `gfx1201`. Architectures without a matching upstream table, including RX 6000, retain the engine's untuned fallback. RX 6000 does not require the SDK's hipBLASLt kernel-data directory; its rocBLAS data remains required. The native engine automatically selects a packaged table by GPU architecture and loaded hipBLASLt version. When changing the shared SDK pin, update all five checksums and verify library versions and upstream table coverage together; tuning solution IDs are not interchangeable between library versions. Builds validate packaging, not inference correctness or performance on each GPU; hardware qualification is still required.

Each enabled matrix job verifies and uploads its engine package as a temporary workflow artifact. After all enabled builds succeed, the publish job attaches the `.tar.gz` packages to a GitHub Release using `STRATA_TAG`. Disabled targets do not block publishing. Publishing to an existing release does not remove assets from previously enabled targets.

Linux HIP packages retain runtime libraries and rocBLAS/hipBLASLt data under `lib/`, with their referenced SDK kernel sidecars under `.kpack/`. Flattening libraries or omitting those sidecars breaks the SDK's relative kernel lookup, even when hipBLASLt tuning initializes successfully. Staging repairs this layout before upstream generates the hashed package manifest; archive validation checks sidecar references again.

## Enable or add a target

Edit `jobs.build.strategy.matrix.include` in [the workflow](.github/workflows/build-strata-engines.yml). To re-enable an existing OS/GPU combination, uncomment its entire entry, from `- id:` through its last field. No helper changes are needed for the existing commented entries.

For a new combination, copy an entry with the same OS and backend, then set:

| Field | Purpose |
| --- | --- |
| `id` | Unique artifact/job name, such as `linux-hip-gfx1150`. |
| `os` | Runner label: currently `ubuntu-24.04`, `windows-2022`, or `macos-26`. |
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
- **CUDA:** the supported variants are `cuda12` and `cuda13`. For a new toolkit family, update the workflow's toolkit-version selection and the appropriate build recipe: upstream's `packaging/build_cuda_linux.sh` for Linux, or [build-windows-cuda.ps1](.github/workflows/scripts/build-windows-cuda.ps1) for Windows. Set engine and picture-reader architectures, package architecture metadata, and minimum driver requirements consistently.
- **macOS Metal / Linux SYCL:** use the existing entries and helpers for the supported platform. A different CPU architecture or runner OS requires checking upstream support and package platform metadata, not just changing `id`.

Workflow step conditions currently match exact runner labels. If adding or changing an `os` label, update every affected setup, build, and archive condition so the job selects exactly one build path and one archive path.

Before publishing, verify unique IDs and asset names, run the applicable helper tests (Linux HIP: `python -m unittest discover -s .github/workflows/scripts -p 'test_prepare_linux_hip_package.py'`), and run the enabled matrix end-to-end. All enabled builds must pass before publishing; compilation and packaging checks do not replace GPU hardware testing.

## Repository layout

- `.github/workflows/build-strata-engines.yml` defines build matrices, hosted runners, and release publishing.
- `.github/workflows/scripts/` contains the platform-specific setup, build, packaging, and archive helpers.

The Strata source is checked out during each workflow run; it is not vendored in this repository. The matrix entries use Ubuntu 24.04, macOS 26, and Windows Server 2022 runners; only the gfx1150 Ubuntu entry is currently enabled.
