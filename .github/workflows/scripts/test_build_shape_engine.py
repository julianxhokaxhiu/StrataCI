import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_shape_engine as build


class ShapeBuildTests(unittest.TestCase):
    def test_inkling_hip_uses_only_requested_gpu_architectures(self) -> None:
        with patch("build_shape_engine.run") as run:
            binary = build.build_inkling(
                Path("source"), Path("build"), "hip", ["gfx1150"], "linux-x86_64", Path("sdk")
            )
        configure = run.call_args_list[0].args[0]
        self.assertIn("-DSTRATA_HIP_ARCHS=gfx1150", configure)
        self.assertIn("-DSTRATA_ENABLE_HIP=ON", configure)
        self.assertIn("-DSTRATA_HIP_CXX=" + str(Path("sdk/llvm/bin/clang++")), configure)
        self.assertEqual(binary.name, "strata-inkling")
        self.assertEqual(run.call_args_list[1].args[0][3:5], ["--target", "strata-inkling"])

    def test_cuda_uses_plain_archs_for_native_blackwell_translation_unit(self) -> None:
        with patch("build_shape_engine.run") as run:
            build.build_inkling(Path("source"), Path("build"), "cuda", ["121"], "linux-aarch64", None)
        self.assertIn("-DSTRATA_INK_CUDA_ARCHS=121", run.call_args_list[0].args[0])
        with patch.dict(os.environ, {"ARCHS": ""}):
            self.assertEqual(build.architectures("cuda", "cuda13", "linux-aarch64"), ["121"])
            self.assertIn("120", build.architectures("cuda", "cuda12", "windows-x86_64"))

    def test_packages_are_distinct_shapes_with_builtin_vision(self) -> None:
        for family, shape, version in (("inkling", "inkling2", "0.1.65"), ("hy4", "hy4", "0.1.64")):
            with self.subTest(family=family), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "engine/src/hy4flash/run").mkdir(parents=True)
                (root / "engine/CMakeLists.txt").write_text("project(strata VERSION 0.1.65)")
                (root / "engine/src/hy4flash/run/hy4_main.hip.cpp").write_text('#define HY4_VERSION "0.1.64"')
                binary = root / "runner"
                binary.write_bytes(b"binary")
                env = {"FAMILY": family, "BACKEND": "hip", "PLATFORM": "linux-x86_64",
                       "VARIANT": "gfx1150", "ARCHS": "gfx1150", "HP": str(root / "sdk"),
                       "COMMIT": "abc123"}
                with patch.dict(os.environ, env), patch("build_shape_engine.Path.resolve", return_value=root), \
                        patch("build_shape_engine.build_inkling", return_value=binary), \
                        patch("build_shape_engine.build_hy4_hip", return_value=binary), \
                        patch("build_shape_engine.prepare"), patch("build_shape_engine.run") as run:
                    build.main()
                package = run.call_args_list[-1].args[0]
                self.assertEqual(package[package.index("--shape") + 1], shape)
                self.assertEqual(package[package.index("--version") + 1], version)
                self.assertEqual(package[package.index("--arch") + 1], "gfx1150")
                stage = root / f"stage-{family}"
                self.assertEqual((stage / f"strata-{family}").read_bytes(), b"binary")
                self.assertFalse((stage / "strata-vision").exists())
                self.assertEqual(json.loads((stage / "BUILD.json").read_text())["vision"], "builtin")

    def test_unsupported_hy4_platform_fails_before_build(self) -> None:
        env = {"FAMILY": "hy4", "BACKEND": "metal", "PLATFORM": "macos-arm64"}
        with patch.dict(os.environ, env), patch("build_shape_engine.run") as run:
            with self.assertRaisesRegex(ValueError, "Linux x86_64 HIP and SYCL"):
                build.main()
        run.assert_not_called()

    def test_hy4_hip_uses_requested_archs_and_upstream_dispatch_defaults(self) -> None:
        with patch("build_shape_engine.build_hy4_objects", return_value=([], ["host.o"])), \
                patch("build_shape_engine.run") as run:
            build.build_hy4_hip(Path("source"), Path("build"), Path("sdk"), ["gfx1150"])
        command = run.call_args.args[0]
        self.assertEqual([arg for arg in command if arg.startswith("--offload-arch=")], ["--offload-arch=gfx1150"])
        self.assertNotIn("-DHY4_MMA=1", command)
        self.assertIn(str(Path("source/engine/src/hy4flash/run/mla_attn.hip.cpp")), command)

    def test_hy4_sycl_has_release_version_and_battlemage_fix(self) -> None:
        with patch.dict(os.environ, {"MKLROOT": "mkl"}), \
                patch("build_shape_engine.build_hy4_objects", return_value=([], ["host.o"])), \
                patch("build_shape_engine.run") as run:
            build.build_hy4_sycl(Path("source"), Path("build"), "0.1.65")
        command = run.call_args.args[0]
        self.assertIn('-DHY4_VERSION="0.1.65"', command)
        self.assertIn("-DHY4S_DISABLE_SG8", command)
        self.assertIn("-DHY4S_ENABLE_SG16_XMX", command)


if __name__ == "__main__":
    unittest.main()
