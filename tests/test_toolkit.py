"""Safety and failure tests: no USB access, external tools or phone writes."""

from __future__ import annotations

import contextlib
import gzip
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from redmi9a.cli import main
from redmi9a.core import (
    Device,
    ToolkitError,
    compatibility_issues,
    extract_gzip,
    inspect_image,
    load_profile,
    sha256,
)
from redmi9a.unlock import require_fresh_brom, unlock_phone, validate_gpt, validate_write
from redmi9a.workflow import Installer, load_bundle, plan_bundle, verify_phone


class FakeTransport:
    def __init__(self) -> None:
        self.profile = load_profile("dandelion-eea")
        self.properties = {
            **self.profile["properties"],
            "ro.boot.flash.locked": "0",
            "ro.adb.secure": "1",
            "sys.boot_completed": "1",
            "ro.build.version.release": "13",
            "sys.oem_unlock_allowed": "1",
        }
        self.calls: list[list[str]] = []
        self.mode = "android"
        self.product = "dandelion"
        self.unlocked = "yes"
        self.capacity = 16384
        self.fail_flash = ""
        self.multiple = False
        self.root = True

    def __call__(self, args: list[str], timeout: int) -> str:
        self.calls.append(args)
        tool = Path(args[0]).stem
        command = args[3:] if len(args) > 2 and args[1] == "-s" else args[1:]
        if command == ["devices"]:
            if tool == "adb":
                return "List of devices attached\nTEST-PRIVATE-ID\tdevice\n" + (
                    "OTHER-PRIVATE-ID\tdevice\n" if self.multiple else ""
                )
            return "TEST-PRIVATE-ID\tfastboot\n"
        if tool == "adb":
            if command[:2] == ["shell", "getprop"]:
                return self.properties.get(command[2], "") + "\n"
            if command == ["shell", "dumpsys", "battery"]:
                return "Current Battery Service state:\n  level: 90\n"
            if command == ["shell", "uname", "-m"]:
                return "armv8l\n"
            if command == ["shell", "zcat", "/proc/config.gz"]:
                return (
                    "CONFIG_ARM64=y\nCONFIG_64BIT=y\n# CONFIG_ANDROID_BINDER_IPC_32BIT is not set\n"
                )
            if command == ["shell", "getenforce"]:
                return "Enforcing\n"
            if command == ["shell", "su", "-c", "id"]:
                return "uid=0(root) gid=0(root)" if self.root else "uid=2000(shell)"
            if command == ["reboot", "bootloader"]:
                self.mode = "bootloader"
                return ""
        if tool == "fastboot":
            if command[0] == "getvar":
                values = {
                    "product": self.product,
                    "unlocked": self.unlocked,
                    "is-userspace": "yes" if self.mode == "fastbootd" else "no",
                    "is-logical:system": "yes",
                    "partition-size:boot": "0x1000",
                    "partition-size:vbmeta": "0x1000",
                    "partition-size:system": hex(self.capacity),
                }
                return f"{command[1]}: {values[command[1]]}\nFinished. Total time: 0.001s\n"
            if command[0] == "reboot":
                self.mode = "fastbootd" if command[1:] == ["fastboot"] else "bootloader"
                return "OKAY\n"
            if "flash" in command:
                partition = command[command.index("flash") + 1]
                if partition == self.fail_flash:
                    raise ToolkitError("Simulated flash error.")
                return "OKAY\n"
            if command == ["-w"]:
                return "OKAY\n"
        raise AssertionError(f"Unexpected simulated command: {command}")

    def writes(self) -> list[list[str]]:
        return [cmd for cmd in self.calls if "flash" in cmd or "-w" in cmd]


class ToolkitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fake = FakeTransport()
        self.device = Device(runner=self.fake)
        self.profile = {
            **load_profile("dandelion-eea"),
            "boot_bytes": 4096,
            "vbmeta_bytes": 4096,
            "maximum_system_bytes": 16384,
        }
        for name, magic in (("boot", b"ANDROID!"), ("vbmeta", b"AVB0"), ("system", b"")):
            header = bytearray(4096)
            header[: len(magic)] = magic
            if name == "system":
                header[1080:1082] = b"\x53\xef"
                struct.pack_into("<I", header, 1028, 1)
                struct.pack_into("<I", header, 1048, 2)
            (self.root / (name + ".img")).write_bytes(header)
        self.bundle: dict[str, Any] = {
            "schema_version": 1,
            "profile": "dandelion-eea",
            "os": "android-gsi",
            "architecture": "a64",
            "layout": "sar",
            "audits": {
                "stock_kernel_preserved": True,
                "product_mount_removed": True,
                "adb_authentication_enabled": True,
                "filesystem_checked": True,
            },
            "expected_properties": {"ro.build.version.release": "13"},
            "images": {
                name: {"path": name + ".img", "sha256": sha256(self.root / (name + ".img"))}
                for name in ("boot", "vbmeta", "system")
            },
        }
        self.manifest = self.root / "bundle.json"
        self.write_bundle()
        self.profile_patch = patch("redmi9a.workflow.load_profile", return_value=self.profile)
        self.profile_patch.start()
        self.addCleanup(self.profile_patch.stop)

    def write_bundle(self) -> None:
        self.manifest.write_text(json.dumps(self.bundle), encoding="utf-8")

    def installer(self) -> Installer:
        return Installer(
            self.device, self.manifest, self.root / "journal.json", emit=lambda _: None
        )

    def install(self) -> dict[str, Any]:
        return self.installer().execute(erase_userdata=True, confirmation="WIPE-DANDELION")

    def test_doctor_is_read_only_and_does_not_export_serial(self) -> None:
        inventory = self.device.inventory()
        self.assertEqual([], compatibility_issues(inventory, load_profile("dandelion-eea")))
        self.assertNotIn("TEST-PRIVATE-ID", json.dumps(inventory))
        self.assertFalse(self.fake.writes())
        self.assertFalse(any("reboot" in call for call in self.fake.calls))

    def test_multiple_phones_refused(self) -> None:
        self.fake.multiple = True
        with self.assertRaises(ToolkitError):
            self.device.inventory()

    def test_explicit_device_selection(self) -> None:
        self.fake.multiple = True
        self.device.serial = "TEST-PRIVATE-ID"
        self.assertEqual("Enforcing", self.device.inventory()["selinux"])

    def test_no_confirmation_means_no_device_commands(self) -> None:
        with self.assertRaises(ToolkitError):
            self.installer().execute(erase_userdata=False, confirmation="")
        self.assertFalse(self.fake.calls)

    def test_offline_plan_never_connects(self) -> None:
        result = plan_bundle(self.manifest)
        self.assertTrue(result["destructive"])
        self.assertFalse(self.fake.calls)

    def test_unknown_profile_is_rejected(self) -> None:
        with self.assertRaises(ToolkitError):
            load_profile("../outside")

    def test_architecture_rejected(self) -> None:
        self.bundle["architecture"] = "arm64"
        self.write_bundle()
        with self.assertRaises(ToolkitError):
            plan_bundle(self.manifest)

    def test_native_linux_is_not_misrepresented_as_gsi(self) -> None:
        self.bundle["os"] = "linux"
        self.write_bundle()
        with self.assertRaises(ToolkitError):
            plan_bundle(self.manifest)

    def test_missing_audit_rejected(self) -> None:
        self.bundle["audits"]["filesystem_checked"] = False
        self.write_bundle()
        with self.assertRaises(ToolkitError):
            plan_bundle(self.manifest)

    def test_arbitrary_shell_property_is_rejected(self) -> None:
        self.bundle["expected_properties"] = {"x; touch /sdcard/unwanted": "13"}
        self.write_bundle()
        with self.assertRaises(ToolkitError):
            load_bundle(self.manifest)

    def test_extra_partition_rejected(self) -> None:
        self.bundle["images"]["preloader"] = self.bundle["images"]["boot"]
        self.write_bundle()
        with self.assertRaises(ToolkitError):
            plan_bundle(self.manifest)

    def test_paths_outside_bundle_rejected(self) -> None:
        self.bundle["images"]["boot"]["path"] = "../outside.img"
        self.write_bundle()
        with self.assertRaises(ToolkitError):
            load_bundle(self.manifest)

    def test_hash_mismatch_before_device_access(self) -> None:
        (self.root / "boot.img").write_bytes(b"changed")
        with self.assertRaises(ToolkitError):
            self.install()
        self.assertFalse(self.fake.calls)

    def test_bad_image_format_before_device_access(self) -> None:
        path = self.root / "boot.img"
        path.write_bytes(b"wrong" * 1000)
        self.bundle["images"]["boot"]["sha256"] = sha256(path)
        self.write_bundle()
        with self.assertRaises(ToolkitError):
            self.install()
        self.assertFalse(self.fake.calls)

    def test_locked_phone_stops_before_reboot(self) -> None:
        self.fake.properties["ro.boot.flash.locked"] = "1"
        with self.assertRaises(ToolkitError):
            self.install()
        self.assertFalse(self.fake.writes())
        self.assertFalse(any("reboot" in call for call in self.fake.calls))

    def test_wrong_vendor_stops_before_writes(self) -> None:
        self.fake.properties["ro.vendor.build.version.incremental"] = "different"
        with self.assertRaises(ToolkitError):
            self.install()
        self.assertFalse(self.fake.writes())

    def test_bootloader_must_independently_confirm_unlocked(self) -> None:
        self.fake.unlocked = "no"
        with self.assertRaises(ToolkitError):
            self.install()
        self.assertFalse(self.fake.writes())

    def test_fastboot_product_mismatch_stops_before_writes(self) -> None:
        self.fake.product = "angelica"
        with self.assertRaises(ToolkitError):
            self.install()
        self.assertFalse(self.fake.writes())

    def test_too_small_system_checked_before_any_write(self) -> None:
        self.fake.capacity = 1024
        with self.assertRaises(ToolkitError):
            self.install()
        self.assertFalse(self.fake.writes())

    def test_success_order_and_partition_allowlist(self) -> None:
        result = self.install()
        writes = self.fake.writes()
        self.assertEqual(
            ["boot", "vbmeta", "system"],
            [call[call.index("flash") + 1] for call in writes if "flash" in call],
        )
        self.assertEqual(1, sum("-w" in call for call in writes))
        self.assertIn("--disable-verification", writes[1])
        self.assertTrue(result["images_written"])
        self.assertFalse(result["phone_verified"])
        self.assertNotIn("TEST-PRIVATE-ID", json.dumps(result))

    def test_failed_flash_is_not_retried_or_followed_by_wipe(self) -> None:
        self.fake.fail_flash = "vbmeta"
        with self.assertRaises(ToolkitError):
            self.install()
        writes = self.fake.writes()
        self.assertEqual(2, len(writes))
        self.assertFalse(any("-w" in cmd for cmd in writes))
        journal = json.loads((self.root / "journal.json").read_text(encoding="utf-8"))
        self.assertTrue(journal["failed"])
        self.assertEqual("Flash vbmeta", journal["current_step"])

    def test_existing_journal_prevents_automatic_replay(self) -> None:
        (self.root / "journal.json").write_text("{}")
        with self.assertRaises(ToolkitError):
            self.install()
        self.assertFalse(self.fake.calls)

    def test_direct_flash_refuses_preloader(self) -> None:
        with self.assertRaises(ToolkitError):
            self.installer().flash("preloader", self.root / "boot.img", "a" * 64)
        self.assertFalse(self.fake.calls)

    def test_changed_image_before_write_refused(self) -> None:
        self.device.serial = "TEST-PRIVATE-ID"
        expected = sha256(self.root / "boot.img")
        (self.root / "boot.img").write_bytes(b"changed after plan")
        with self.assertRaises(ToolkitError):
            self.installer().flash("boot", self.root / "boot.img", expected)
        self.assertFalse(self.fake.writes())

    def test_bootloader_mode_never_used_for_logical_system(self) -> None:
        self.device.serial = "TEST-PRIVATE-ID"
        with self.assertRaises(ToolkitError):
            self.installer().check_fastbootd(self.profile, 4096)

    def test_readonly_verification_does_not_assume_root(self) -> None:
        self.fake.root = False
        report = verify_phone(self.device, root_check=True)
        self.assertFalse(report["software_checks_passed"])
        self.assertFalse(report["root_verified"])
        self.assertFalse(self.fake.writes())

    def test_cli_install_requires_confirmation(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            result = main(["install", str(self.manifest), "--journal", str(self.root / "out.json")])
        self.assertEqual(2, result)

    def test_gzip_valid_and_existing_output_preserved(self) -> None:
        source = self.root / "source.gz"
        source.write_bytes(gzip.compress(b"test-image"))
        output = self.root / "extracted.img"
        report = extract_gzip(source, output, sha256(source), 100)
        self.assertEqual(10, report["bytes"])
        with self.assertRaises(ToolkitError):
            extract_gzip(source, output, sha256(source), 100)
        self.assertEqual(b"test-image", output.read_bytes())

    def test_gzip_crc_failure_removes_partial_output(self) -> None:
        source = self.root / "corrupt.gz"
        data = bytearray(gzip.compress(b"test-image"))
        data[-8] ^= 1
        source.write_bytes(data)
        output = self.root / "extracted.img"
        with self.assertRaises(ToolkitError):
            extract_gzip(source, output, sha256(source), 100)
        self.assertFalse(output.exists())

    def test_gzip_size_cap_removes_partial_output(self) -> None:
        source = self.root / "large.gz"
        source.write_bytes(gzip.compress(b"x" * 1000))
        output = self.root / "extracted.img"
        with self.assertRaises(ToolkitError):
            extract_gzip(source, output, sha256(source), 10)
        self.assertFalse(output.exists())

    def test_invalid_deflate_removes_partial_output(self) -> None:
        source = self.root / "deflate.gz"
        source.write_bytes(b"\x1f\x8b\x08\x00" + b"\x00" * 6 + b"\xff" * 32)
        output = self.root / "extracted.img"
        with self.assertRaises(ToolkitError):
            extract_gzip(source, output, sha256(source), 1000)
        self.assertFalse(output.exists())

    def test_wrong_unlocked_model_is_still_refused(self) -> None:
        self.fake.properties["ro.product.vendor.model"] = "different"
        with self.assertRaises(ToolkitError):
            unlock_phone(
                self.device,
                self.root,
                self.root / "missing.bin",
                self.root / "session",
                True,
                "UNLOCK-DANDELION",
            )
        self.assertFalse(self.fake.writes())

    def test_shared_blocks_cannot_be_hidden_by_audit_flag(self) -> None:
        path = self.root / "system.img"
        header = bytearray(path.read_bytes())
        struct.pack_into("<I", header, 1124, 0x4000)
        path.write_bytes(header)
        with self.assertRaises(ToolkitError):
            inspect_image(path)

    def test_truncated_ext4_rejected(self) -> None:
        path = self.root / "system.img"
        header = bytearray(path.read_bytes())
        struct.pack_into("<I", header, 1028, 10000)
        path.write_bytes(header)
        with self.assertRaises(ToolkitError):
            inspect_image(path)

    def test_unknown_fastboot_variable_is_not_guessed(self) -> None:
        device = Device(serial="TEST-PRIVATE-ID", runner=lambda _args, _timeout: "unknown variable")
        with self.assertRaises(ToolkitError):
            device.getvar("unlocked")

    def test_seccfg_guard_rejects_wrong_region_length_and_second_write(self) -> None:
        data = b"MMMM" + b"\x00" * 508
        validate_write(4096, 512, "", data, "user", 4096, 8192, False)
        cases = [
            (0, 512, "", data, "user", False),
            (4096, 1024, "", data, "user", False),
            (4096, 512, "disk.bin", data, "user", False),
            (4096, 512, "", data, "rpmb", False),
            (4096, 512, "", data, "user", True),
            (4096, 512, "", b"bad!" + data[4:], "user", False),
        ]
        for addr, length, filename, payload, parttype, attempted in cases:
            with self.subTest(addr=addr, length=length, parttype=parttype, attempted=attempted):
                with self.assertRaises(ToolkitError):
                    validate_write(addr, length, filename, payload, parttype, 4096, 8192, attempted)

    def test_gpt_guard_rejects_changed_partition_map(self) -> None:
        expected = [{"name": "seccfg", "sector": 10, "sectors": 16}]
        self.assertEqual("seccfg", validate_gpt(expected, expected)["name"])
        with self.assertRaises(ToolkitError):
            validate_gpt([{**expected[0], "sector": 11}], expected)

    def test_brom_guard_rejects_cached_or_wrong_chip_session(self) -> None:
        good = SimpleNamespace(reinited=False, config=SimpleNamespace(is_brom=True, hwcode=0x766))
        require_fresh_brom(good)
        for session in (
            None,
            SimpleNamespace(reinited=True),
            SimpleNamespace(reinited=False, config=SimpleNamespace(is_brom=False)),
            SimpleNamespace(reinited=False, config=SimpleNamespace(is_brom=True, hwcode=0x999)),
        ):
            with self.assertRaises(ToolkitError):
                require_fresh_brom(session)

    def test_unlock_without_confirmation_does_nothing(self) -> None:
        with self.assertRaises(ToolkitError):
            unlock_phone(
                self.device, self.root, self.root / "missing.bin", self.root / "session", False, ""
            )
        self.assertFalse(self.fake.calls)

    def test_already_unlocked_phone_has_no_mtk_operation(self) -> None:
        result = unlock_phone(
            self.device,
            self.root,
            self.root / "missing.bin",
            self.root / "session",
            True,
            "UNLOCK-DANDELION",
        )
        self.assertTrue(result["already_unlocked"])
        self.assertFalse((self.root / "session").exists())
        self.assertFalse(self.fake.writes())


if __name__ == "__main__":
    unittest.main()
