import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from prepare_linux_hip_package import prepare, verify


class HipPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.stage = root / "stage"
        self.sdk = root / "sdk"
        self.stage.mkdir()
        (self.sdk / ".kpack").mkdir(parents=True)
        (self.stage / "librocblas.so.5").write_bytes(
            b"\x7fELF../.kpack/blas_lib_@GFXARCH@.kpack\x00"
        )
        (self.sdk / ".kpack" / "blas_lib_gfx1150.kpack").write_bytes(b"kernel")
        (self.sdk / ".kpack" / "unrelated_gfx1150.kpack").write_bytes(b"unused")
        (self.stage / "BUILD.json").write_text(
            json.dumps({"archs": ["gfx1150"], "hipblaslt_version": 100500}),
            encoding="utf-8",
        )
        for name in ("strata", "strata-vision", "strata-vision-hip"):
            (self.stage / name).write_bytes(b"\x7fELF")
        data = self.stage / "rocblas" / "library" / "gfx1150"
        data.mkdir(parents=True)
        (data / "kernel.hsaco").write_bytes(b"kernel")

    def test_preserves_sdk_relative_lookup_and_library_data(self) -> None:
        with patch("prepare_linux_hip_package.subprocess.run") as run:
            prepare(self.stage, self.sdk)
        library = self.stage / "lib" / "librocblas.so.5"
        payload = library.parent / "../.kpack/blas_lib_gfx1150.kpack"
        self.assertEqual(payload.read_bytes(), b"kernel")
        self.assertTrue((self.stage / "lib/rocblas/library/gfx1150/kernel.hsaco").is_file())
        self.assertFalse((self.stage / "librocblas.so.5").exists())
        self.assertFalse((self.stage / ".kpack/unrelated_gfx1150.kpack").exists())
        metadata = json.loads((self.stage / "BUILD.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["lib_dirs"], ["lib"])
        self.assertEqual(metadata["hipblaslt_version"], 100500)
        self.assertEqual(run.call_count, 3)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][:3], ["patchelf", "--set-rpath", "$ORIGIN/lib:$ORIGIN"])
            self.assertTrue(call.kwargs["check"])
        verify(self.stage)

    def test_missing_sdk_payload_is_rejected_before_relocation(self) -> None:
        (self.sdk / ".kpack/blas_lib_gfx1150.kpack").unlink()
        with self.assertRaisesRegex(RuntimeError, "requires missing kernel payload"):
            prepare(self.stage, self.sdk)
        self.assertTrue((self.stage / "librocblas.so.5").is_file())

    def test_missing_packaged_payload_is_rejected(self) -> None:
        with patch("prepare_linux_hip_package.subprocess.run"):
            prepare(self.stage, self.sdk)
        (self.stage / ".kpack/blas_lib_gfx1150.kpack").unlink()
        with self.assertRaisesRegex(RuntimeError, "requires missing kernel payload"):
            verify(self.stage)

    def test_payload_is_required_for_every_advertised_architecture(self) -> None:
        (self.stage / "BUILD.json").write_text(
            json.dumps({"archs": ["gfx1150", "gfx1151"]}), encoding="utf-8"
        )
        with self.assertRaisesRegex(RuntimeError, "blas_lib_gfx1151.kpack"):
            prepare(self.stage, self.sdk)

    def test_flattened_package_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "No runtime libraries"):
            verify(self.stage)

    def test_incorrect_library_directory_metadata_is_rejected(self) -> None:
        with patch("prepare_linux_hip_package.subprocess.run"):
            prepare(self.stage, self.sdk)
        (self.stage / "BUILD.json").write_text(
            json.dumps({"archs": ["gfx1150"], "lib_dirs": ["."]}), encoding="utf-8"
        )
        with self.assertRaisesRegex(RuntimeError, "must advertise its lib directory"):
            verify(self.stage)

    def test_legacy_libraries_without_kpack_references_remain_supported(self) -> None:
        (self.stage / "librocblas.so.5").write_bytes(b"\x7fELF")
        with patch("prepare_linux_hip_package.subprocess.run"):
            prepare(self.stage, self.sdk)
        self.assertFalse((self.stage / ".kpack").exists())
        verify(self.stage)

    def test_multiple_architectures_and_literal_references_are_bundled(self) -> None:
        (self.stage / "BUILD.json").write_text(
            json.dumps({"archs": ["gfx1150", "gfx1151"]}), encoding="utf-8"
        )
        (self.sdk / ".kpack/blas_lib_gfx1151.kpack").write_bytes(b"other GPU")
        (self.sdk / ".kpack/static_lib.kpack").write_bytes(b"shared")
        (self.stage / "libother.so.1").write_bytes(
            b"\x7fELF../.kpack/static_lib.kpack\x00"
        )
        with patch("prepare_linux_hip_package.subprocess.run"):
            prepare(self.stage, self.sdk)
        self.assertEqual(
            {path.name for path in (self.stage / ".kpack").iterdir()},
            {"blas_lib_gfx1150.kpack", "blas_lib_gfx1151.kpack", "static_lib.kpack"},
        )
        verify(self.stage)

    def test_optional_hipblaslt_data_is_relocated_when_present(self) -> None:
        data = self.stage / "hipblaslt/library"
        data.mkdir(parents=True)
        (data / "kernel.co").write_bytes(b"kernel")
        with patch("prepare_linux_hip_package.subprocess.run"):
            prepare(self.stage, self.sdk)
        self.assertTrue((self.stage / "lib/hipblaslt/library/kernel.co").is_file())

    def test_patchelf_failure_stops_packaging(self) -> None:
        with patch(
            "prepare_linux_hip_package.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "patchelf"),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                prepare(self.stage, self.sdk)


if __name__ == "__main__":
    unittest.main()
