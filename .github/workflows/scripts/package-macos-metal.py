#!/usr/bin/env python3
"""Stage and package the macOS Metal engine built by build-macos-metal.sh."""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys


def main() -> None:
    root = pathlib.Path(sys.argv[1]).resolve()
    version_text = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    match = re.search(r"project\([^)]*VERSION\s+([0-9.]+)", version_text, re.IGNORECASE)
    if not match:
        raise SystemExit("Could not determine the engine version from CMakeLists.txt")

    stage = root / "stage-metal"
    stage.mkdir()
    shutil.copy2(root / "build-metal" / "strata", stage / "strata")
    shutil.copy2(root / "vision" / "strata-vision", stage / "strata-vision")

    metal = stage / "metal"
    shutil.copytree(root / "metal" / "kernels", metal / "kernels")
    shutil.copytree(root / "metal" / "src" / "engine" / "msl", metal / "engine-msl")
    (metal / "data").mkdir()
    shutil.copy2(root / "third_party" / "ggml" / "ggml-common.h", metal / "ggml-common.h")
    for data_file in (root / "data").glob("*.bin"):
        shutil.copy2(data_file, metal / "data" / data_file.name)

    subprocess.run(
        [
            sys.executable,
            str(root / "packaging" / "package_engine.py"),
            "--src",
            str(stage),
            "--backend",
            "metal",
            "--version",
            match.group(1),
            "--out",
            str(root / "out-engine-metal"),
            "--arch",
            "apple-silicon",
            "--platform",
            "macos-arm64",
            "--tree",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
