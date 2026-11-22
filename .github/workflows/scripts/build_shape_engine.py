#!/usr/bin/env python3
"""Build and package upstream's standalone Inkling and Hy4 runners."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from prepare_linux_hip_package import prepare


HIP_ARCHS = {
    "gfx1150": ["gfx1150"],
    "halo": ["gfx1151"],
    "strix": ["gfx1151"],
    "rx6000": ["gfx1030", "gfx1031", "gfx1032"],
    "rdna2": ["gfx1030", "gfx1031", "gfx1032"],
    "rx7900": ["gfx1100", "gfx1101", "gfx1102", "gfx1103", "gfx1150"],
    "rdna3": ["gfx1100", "gfx1101", "gfx1102", "gfx1103", "gfx1150"],
    "rx9070": ["gfx1200", "gfx1201"],
}


def architectures(backend: str, variant: str, platform: str) -> list[str]:
    override = os.environ.get("ARCHS")
    if backend == "hip":
        return override.split(";") if override else HIP_ARCHS[variant]
    if backend == "cuda":
        if platform == "linux-aarch64":
            if variant != "cuda13":
                raise ValueError("ARM64 CUDA requires cuda13")
            return ["121"]
        if variant == "cuda12":
            return ["60", "61", "70", "75", "80", "86", "120", "89"]
        if variant == "cuda13":
            return ["75", "80", "86", "89", "120"]
        raise ValueError(f"Unsupported CUDA variant: {variant}")
    return {"sycl": ["intel-arc"], "metal": ["apple-gpu"]}[backend]


def run(args: list[str], root: Path) -> None:
    print("+ " + subprocess.list2cmdline(args), flush=True)
    subprocess.run(args, cwd=root, check=True)


def build_inkling(root: Path, build: Path, backend: str, archs: list[str],
                  platform: str, sdk: Path | None) -> Path:
    args = [
        "cmake", "-S", str(root / "engine/src/inkling2"), "-B", str(build),
        "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
    ]
    if backend == "hip":
        if sdk is None:
            raise ValueError("HIP requires HP")
        compiler = sdk / ("lib/llvm/bin/clang++.exe" if platform.startswith("windows") else "llvm/bin/clang++")
        args += [
            "-DSTRATA_ENABLE_HIP=ON", f"-DSTRATA_HIP_ARCHS={';'.join(archs)}",
            f"-DSTRATA_HIP_CXX={compiler}", f"-DSTRATA_ROCM_PATH={sdk}",
            f"-DSTRATA_ROCM_BITCODE_PATH={sdk / 'lib/llvm/amdgcn/bitcode'}",
        ]
    elif backend == "cuda":
        # Plain numbers let upstream select the separate sm_120a/sm_121a translation unit.
        args += ["-DSTRATA_ENABLE_CUDA=ON", f"-DSTRATA_INK_CUDA_ARCHS={';'.join(archs)}"]
    elif backend == "sycl":
        args += [
            "-DSTRATA_ENABLE_SYCL=ON", "-DCMAKE_C_COMPILER=icx", "-DCMAKE_CXX_COMPILER=icpx",
            "-DSTRATA_SYCL_TARGETS=spir64,intel_gpu_acm_g10,intel_gpu_bmg_g21",
        ]
    elif backend == "metal":
        args += ["-DCMAKE_OSX_DEPLOYMENT_TARGET=14.0"]
    run(args, root)
    run(["cmake", "--build", str(build), "--target", "strata-inkling",
         "-j", os.environ.get("JOBS", str(os.cpu_count() or 2))], root)
    return build / ("strata-inkling.exe" if platform.startswith("windows") else "strata-inkling")


def build_hy4_objects(root: Path, build: Path) -> tuple[list[str], list[str]]:
    engine = root / "engine"
    source = engine / "src/hy4flash/run"
    zstd = engine / "third_party/zstd-dec"
    includes = [f"-I{engine / 'include'}", f"-I{source}", f"-I{engine / 'third_party/stb'}",
                f"-I{zstd}", f"-I{zstd / 'common'}", f"-I{zstd / 'decompress'}"]
    objects = []
    sources = sorted((zstd / "common").glob("*.c")) + sorted((zstd / "decompress").glob("*.c"))
    for path in sources:
        obj = build / (path.stem + ".o")
        run(["gcc", "-O3", "-DZSTD_DISABLE_ASM=1", *includes, "-c", str(path), "-o", str(obj)], root)
        objects.append(str(obj))
    for name in ("artifact/strata_reader.cpp", "quant/sk_codecs.cpp", "ngram/hy4_engram_reader.cpp",
                 "hy4flash/run/hy4_engram.cpp", "hy4flash/run/hy4_cpu_experts.cpp"):
        obj = build / (Path(name).stem + ".o")
        run(["g++", "-O3", "-std=c++17", "-mavx2", "-mfma", "-mf16c", "-pthread",
             *includes, "-c", str(engine / "src" / name), "-o", str(obj)], root)
        objects.append(str(obj))
    return includes, objects


def build_hy4_hip(root: Path, build: Path, sdk: Path, archs: list[str]) -> Path:
    includes, objects = build_hy4_objects(root, build)
    source = root / "engine/src/hy4flash/run"
    binary = build / "strata-hy4"
    run([str(sdk / "llvm/bin/clang++"), "-x", "hip", "-O3", "-std=c++17",
         f"--rocm-path={sdk}", f"--rocm-device-lib-path={sdk / 'lib/llvm/amdgcn/bitcode'}",
         *[f"--offload-arch={arch}" for arch in archs], *includes,
         str(source / "hy4_main.hip.cpp"), str(source / "mla_attn.hip.cpp"),
         "-x", "none", *objects, "-pthread", "-o", str(binary)], root)
    return binary


def build_hy4_sycl(root: Path, build: Path, version: str) -> Path:
    includes, objects = build_hy4_objects(root, build)
    source = root / "engine/src/hy4flash/sycl"
    mkl = Path(os.environ["MKLROOT"])
    binary = build / "strata-hy4"
    run(["icpx", "-O3", "-std=c++17", "-fiopenmp", "-fsycl",
         "-fsycl-targets=intel_gpu_acm_g10,intel_gpu_bmg_g21,spir64",
         "-DHY4S_DISABLE_SG8", "-DHY4S_ENABLE_SG16_XMX", "-DHY4S_USE_ONEMKL",
         f'-DHY4_VERSION="{version}"', *includes, f"-I{source}", f"-I{mkl / 'include'}",
         str(source / "sy_main.cpp"), str(source / "sy_mla.cpp"), str(source / "sy_gpuexp.cpp"),
         *objects, f"-L{mkl / 'lib'}", "-lmkl_sycl_blas", "-lmkl_intel_lp64",
         "-lmkl_sequential", "-lmkl_core", "-pthread", "-o", str(binary)], root)
    return binary


def main() -> None:
    root = Path("strata").resolve()
    family = os.environ["FAMILY"]
    backend = os.environ["BACKEND"]
    platform = os.environ["PLATFORM"]
    variant = os.environ.get("VARIANT", "")
    if family not in ("inkling", "hy4"):
        raise ValueError(f"Unsupported engine family: {family}")
    if family == "hy4" and (platform != "linux-x86_64" or backend not in ("hip", "sycl")):
        raise ValueError("Hy4 helper supports Linux x86_64 HIP and SYCL")
    version_file = root / ("engine/src/hy4flash/run/hy4_main.hip.cpp" if family == "hy4" and backend == "hip"
                           else "engine/CMakeLists.txt")
    pattern = r'#define HY4_VERSION "([0-9.]+)"' if version_file.suffix == ".cpp" else r"project\([^)]*VERSION\s+([0-9.]+)"
    match = re.search(pattern, version_file.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"No engine version found in {version_file}")
    version = match.group(1)
    archs = architectures(backend, variant, platform)
    sdk = Path(os.environ["HP"]).resolve() if backend == "hip" else None
    build = root / f"build-{family}"
    stage = root / f"stage-{family}"
    build.mkdir()
    stage.mkdir()
    if family == "inkling":
        binary = build_inkling(root, build, backend, archs, platform, sdk)
        shape = "inkling2"
    elif backend == "hip":
        if sdk is None:
            raise ValueError("HIP requires HP")
        binary = build_hy4_hip(root, build, sdk, archs)
        shape = "hy4"
    else:
        binary = build_hy4_sycl(root, build, version)
        shape = "hy4"
    entry = f"strata-{family}" + (".exe" if platform.startswith("windows") else "")
    shutil.copy2(binary, stage / entry)
    (stage / "BUILD.json").write_text(json.dumps({
        "version": version, "archs": archs, "shape": shape,
        "source": os.environ["COMMIT"], "portable": True, "vision": "builtin",
    }) + "\n", encoding="utf-8")
    if platform.startswith("linux"):
        collect = [sys.executable, "tools/packaging/collect_libs.py", "--binary", str(stage / entry),
                   "--out", str(stage)]
        if sdk is not None:
            collect += ["--search", str(sdk / "lib"), "--search", str(sdk / "lib/llvm/lib"),
                        "--also", "libamd_comgr.so*", "--also", "libhiprtc*.so*"]
            if (sdk / "lib/rocm_sysdeps/lib").is_dir():
                collect += ["--search", str(sdk / "lib/rocm_sysdeps/lib")]
        elif backend == "cuda":
            collect += ["--search", "/usr/local/cuda/lib64", "--also", "libcublasLt.so*"]
        else:
            collect += ["--search", "/opt/intel/oneapi/compiler/latest/lib",
                        "--search", "/opt/intel/oneapi/mkl/latest/lib",
                        "--also", "libur_adapter_level_zero*.so*", "--also", "libur_adapter_opencl*.so*",
                        "--bundle-system", "libz.so.1"]
        run(collect, root)
        for path in stage.iterdir():
            if path.name == entry or ".so" in path.name:
                run(["patchelf", "--set-rpath", "$ORIGIN", str(path)], root)
        if sdk is not None:
            prepare(stage, sdk)
    package = [
        sys.executable, "tools/packaging/package_engine.py", "--src", str(stage),
        "--backend", backend, "--version", version, "--platform", platform,
        "--out", str(root / f"out-engine-{family}"), "--shape", shape,
        "--build-id", os.environ["COMMIT"], "--tree",
    ]
    if variant:
        package += ["--variant", variant]
    package_archs = [f"sm_{arch}" for arch in archs] if backend == "cuda" else archs
    if backend == "cuda":
        package_archs += [f"compute_{archs[-1]}"]
        package += ["--min-driver", "nvidia=" + ("575.51" if variant == "cuda12" else "580.65")]
    for arch in package_archs:
        package += ["--arch", arch]
    if sdk is not None and platform.startswith("windows"):
        package += ["--search", str(sdk / "bin")]
    run(package, root)


if __name__ == "__main__":
    main()
