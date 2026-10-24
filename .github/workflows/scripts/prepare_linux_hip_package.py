#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess


KPACK_REFERENCE = re.compile(rb"\.\./\.kpack/([A-Za-z0-9_@.-]+\.kpack)")


def required_kpacks(library: Path, directory: Path, archs: list[str]) -> set[Path]:
    result: set[Path] = set()
    for reference in KPACK_REFERENCE.findall(library.read_bytes()):
        name = reference.decode("ascii")
        names = {name.replace("@GFXARCH@", arch) for arch in archs}
        for filename in names:
            payload = directory / filename
            if not payload.is_file():
                raise RuntimeError(f"{library.name} requires missing kernel payload: {filename}")
            result.add(payload)
    return result


def verify(stage: Path) -> None:
    metadata = json.loads((stage / "BUILD.json").read_text(encoding="utf-8"))
    archs = metadata["archs"]
    if not archs:
        raise RuntimeError("HIP package must list its GPU architectures")
    libraries = list((stage / "lib").glob("*.so*"))
    if not libraries:
        raise RuntimeError(f"No runtime libraries in {stage / 'lib'}")
    for library in libraries:
        required_kpacks(library, stage / ".kpack", archs)
    if metadata.get("lib_dirs") != ["lib"]:
        raise RuntimeError("HIP package must advertise its lib directory")


def prepare(stage: Path, sdk: Path) -> None:
    metadata_path = stage / "BUILD.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    archs = metadata["archs"]
    if not archs:
        raise RuntimeError("HIP package must list its GPU architectures")
    libraries = [path for path in stage.glob("*.so*") if path.is_file()]
    if not libraries:
        raise RuntimeError(f"No staged runtime libraries in {stage}")
    payloads: set[Path] = set()
    for library in libraries:
        payloads.update(required_kpacks(library, sdk / ".kpack", archs))
    lib = stage / "lib"
    lib.mkdir()
    for library in libraries:
        shutil.move(str(library), lib / library.name)
    for name in ("rocblas", "hipblaslt"):
        source = stage / name
        if source.exists():
            shutil.move(str(source), lib / name)
    if payloads:
        destination = stage / ".kpack"
        destination.mkdir()
        for payload in sorted(payloads):
            shutil.copy2(payload, destination / payload.name)
            print(f"Bundled SDK kernel payload: {payload.name}")
    for name in ("strata", "strata-vision", "strata-vision-hip"):
        binary = stage / name
        if binary.is_file():
            subprocess.run(
                ["patchelf", "--set-rpath", "$ORIGIN/lib:$ORIGIN", str(binary)],
                check=True,
            )
    metadata["lib_dirs"] = ["lib"]
    metadata_path.write_text(json.dumps(metadata, indent=1) + "\n", encoding="utf-8")
    verify(stage)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sdk", type=Path)
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify(args.stage)
    else:
        prepare(args.stage, args.sdk)


if __name__ == "__main__":
    main()
