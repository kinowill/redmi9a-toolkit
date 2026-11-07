"""Bundle validation and explicit, non-resumable fastboot installation."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from .core import (
    SHA256_PATTERN,
    Device,
    ToolkitError,
    compatibility_issues,
    inspect_image,
    load_json,
    load_profile,
    save_json,
    sha256,
)

AUDITS = {
    "stock_kernel_preserved",
    "product_mount_removed",
    "adb_authentication_enabled",
    "filesystem_checked",
}
EXPECTED_PROPERTIES = {"ro.build.version.release", "ro.lineage.version"}
PHRASE = "WIPE-DANDELION"


def load_bundle(manifest: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Path]]:
    bundle = load_json(manifest)
    if type(bundle.get("schema_version")) is not int or bundle["schema_version"] != 1:
        raise ToolkitError("Unsupported bundle schema.")
    profile = load_profile(bundle.get("profile", ""))
    if (
        bundle.get("os") != "android-gsi"
        or bundle.get("architecture") != profile["architecture"]
        or bundle.get("layout") != profile["layout"]
    ):
        raise ToolkitError("Unsupported OS, architecture or partition layout.")
    audits = bundle.get("audits")
    if not isinstance(audits, dict) or any(audits.get(key) is not True for key in AUDITS):
        raise ToolkitError("Required operator image audits are missing; read the runbook.")
    expected = bundle.get("expected_properties")
    if (
        not isinstance(expected, dict)
        or not expected
        or not set(expected).issubset(EXPECTED_PROPERTIES)
        or any(not isinstance(value, str) or not value for value in expected.values())
    ):
        raise ToolkitError("Expected Android version properties are missing or unsupported.")
    images = bundle.get("images")
    if not isinstance(images, dict) or set(images) != {"boot", "vbmeta", "system"}:
        raise ToolkitError("Bundle must contain exactly boot, vbmeta and system.")
    paths = {}
    for partition, image in images.items():
        if not isinstance(image, dict) or not isinstance(image.get("path"), str):
            raise ToolkitError("Malformed image entry.")
        digest = image.get("sha256", "")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ToolkitError("Every image requires a lowercase SHA256 digest.")
        path = (manifest.parent / image["path"]).resolve()
        if not path.is_relative_to(manifest.parent.resolve()) or not path.is_file():
            raise ToolkitError("Image must be a local file inside the bundle directory.")
        paths[partition] = path
    return bundle, profile, paths


def plan_bundle(manifest: Path) -> dict[str, Any]:
    bundle, profile, paths = load_bundle(manifest)
    return audit_images(bundle, profile, paths)


def audit_images(
    bundle: dict[str, Any], profile: dict[str, Any], paths: dict[str, Path]
) -> dict[str, Any]:
    details = {}
    for partition, path in paths.items():
        info = inspect_image(path)
        if info["sha256"] != bundle["images"][partition]["sha256"]:
            raise ToolkitError(f"SHA256 mismatch for {partition}.")
        if info["format"] != profile["allowed_image_formats"][partition]:
            raise ToolkitError(f"Unsupported image format for {partition}.")
        if partition != "system" and info["bytes"] != profile[partition + "_bytes"]:
            raise ToolkitError(f"Unexpected {partition} size for this profile.")
        if partition == "system" and info["bytes"] > profile["maximum_system_bytes"]:
            raise ToolkitError("System image exceeds the profile capacity; no partition resizing.")
        details[partition] = info
    return {
        "profile": profile["id"],
        "os": bundle["os"],
        "images": details,
        "expected_properties": bundle["expected_properties"],
        "operator_audits_are_attestations": True,
        "steps": [
            "Read Android identity, vendor, ABI, battery, ADB authentication and SELinux",
            "Enter bootloader; verify product, unlocked state, boot and vbmeta sizes",
            "Enter fastbootd; verify product, logical system and current system capacity",
            "Return to bootloader; recheck identity; flash boot and vbmeta",
            "Return to fastbootd; recheck identity and capacity; flash system",
            "Erase Android userdata/cache/metadata using fastboot -w; reboot",
            "Authorize normal ADB on the phone, then run verify separately",
        ],
        "destructive": True,
        "preserved": ["preloader", "RPMB", "radio/calibration", "vendor", "product"],
        "note": "Plan only. No phone command was executed. Hashes are not a safety audit.",
    }


class Installer:
    def __init__(
        self,
        device: Device,
        manifest: Path,
        journal: Path,
        emit: Callable[[str], None] = print,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.device = device
        self.manifest = manifest
        self.journal = journal
        self.emit = emit
        self.sleep = sleep
        self.clock = clock
        self.state: dict[str, Any] = {"completed_steps": [], "phone_verified": False}

    def step(self, label: str, operation: Callable[[], Any]) -> None:
        self.state["current_step"] = label
        save_json(self.journal, self.state)
        self.emit(label)
        operation()
        self.state["completed_steps"].append(label)
        save_json(self.journal, self.state)

    def wait_fastboot(self, userspace: bool) -> None:
        deadline = self.clock() + 90
        while self.clock() < deadline:
            response = self.device.runner([self.device.fastboot_executable, "devices"], 10)
            present = [line.split()[0] for line in response.splitlines() if line.strip()]
            if self.device.serial in present:
                actual = self.device.getvar("is-userspace")
                if actual == ("yes" if userspace else "no"):
                    return
                if actual not in {"yes", "no"}:
                    raise ToolkitError("Unknown fastboot mode; refusing to guess.")
            self.sleep(1)
        raise ToolkitError("Expected fastboot mode did not appear; inspect phone before retrying.")

    def check_bootloader(self, profile: dict[str, Any]) -> None:
        if self.device.getvar("is-userspace") != "no":
            raise ToolkitError("Boot writes require bootloader fastboot.")
        if self.device.getvar("product") != profile["product"]:
            raise ToolkitError("Fastboot product mismatch.")
        if self.device.getvar("unlocked") != "yes":
            raise ToolkitError("Fastboot must independently confirm unlocked=yes.")
        for partition in ("boot", "vbmeta"):
            size = self.partition_size(partition)
            if size != profile[partition + "_bytes"]:
                raise ToolkitError(f"Unexpected device {partition} partition size.")

    def partition_size(self, partition: str) -> int:
        value = self.device.getvar("partition-size:" + partition)
        if not re.fullmatch(r"0x[0-9a-fA-F]+|[0-9]+", value):
            raise ToolkitError("Invalid partition size response.")
        return int(value, 16 if value.startswith("0x") else 10)

    def check_fastbootd(self, profile: dict[str, Any], system_bytes: int) -> None:
        if self.device.getvar("is-userspace") != "yes":
            raise ToolkitError("Logical system writes require userspace fastbootd.")
        if self.device.getvar("product") != profile["product"]:
            raise ToolkitError("Fastbootd product mismatch.")
        if self.device.getvar("is-logical:system") != "yes":
            raise ToolkitError("System must be a logical partition.")
        size = self.partition_size("system")
        if not system_bytes <= size <= profile["maximum_system_bytes"]:
            raise ToolkitError(
                "System does not fit the current partition; resizing is not supported."
            )

    def flash(self, partition: str, path: Path, expected: str) -> None:
        if partition not in {"boot", "vbmeta", "system"}:
            raise ToolkitError("Partition is outside the fixed write allowlist.")
        if sha256(path) != expected:
            raise ToolkitError("Image changed after planning; stopping.")
        flags = ["--disable-verity", "--disable-verification"] if partition == "vbmeta" else []
        self.device.fastboot(*flags, "flash", partition, str(path), timeout=600)

    def execute(self, *, erase_userdata: bool, confirmation: str) -> dict[str, Any]:
        if not erase_userdata or confirmation != PHRASE:
            raise ToolkitError(f"Install requires --erase-userdata --confirm {PHRASE}.")
        if self.journal.exists():
            raise ToolkitError("Journal already exists; inspect it and choose a new path.")
        # Fully validate immutable planning inputs before any reboot or partition write.
        bundle, profile, paths = load_bundle(self.manifest)
        plan = audit_images(bundle, profile, paths)
        self.state["plan"] = plan
        try:
            inventory = self.device.inventory()
            issues = compatibility_issues(inventory, profile)
            if issues:
                raise ToolkitError("Preflight refused: " + "; ".join(issues))
            self.state["preflight"] = inventory
            self.step("Enter bootloader", lambda: self.device.adb("reboot", "bootloader"))
            self.wait_fastboot(False)
            self.check_bootloader(profile)
            self.step(
                "Inspect fastbootd before writes",
                lambda: self.device.fastboot("reboot", "fastboot"),
            )
            self.wait_fastboot(True)
            system_bytes = plan["images"]["system"]["bytes"]
            self.check_fastbootd(profile, system_bytes)
            self.step("Return to bootloader", lambda: self.device.fastboot("reboot", "bootloader"))
            self.wait_fastboot(False)
            self.check_bootloader(profile)
            for partition in ("boot", "vbmeta"):
                self.step(
                    "Flash " + partition,
                    partial(
                        self.flash,
                        partition,
                        paths[partition],
                        bundle["images"][partition]["sha256"],
                    ),
                )
            self.step(
                "Enter fastbootd for system", lambda: self.device.fastboot("reboot", "fastboot")
            )
            self.wait_fastboot(True)
            self.check_fastbootd(profile, system_bytes)
            self.step(
                "Flash system",
                lambda: self.flash("system", paths["system"], bundle["images"]["system"]["sha256"]),
            )
            self.step("Erase Android user data", lambda: self.device.fastboot("-w", timeout=180))
            self.step("Reboot Android", lambda: self.device.fastboot("reboot"))
            self.state["images_written"] = True
            self.state["next"] = (
                "Authorize normal USB access and run verify; boot/root not yet verified."
            )
            save_json(self.journal, self.state)
            return self.state
        except (ToolkitError, OSError, ValueError, KeyboardInterrupt) as exc:
            self.state["failed"] = True
            self.state["failure"] = (
                str(exc)
                if isinstance(exc, ToolkitError)
                else ("Local I/O error or interruption; inspect the device and journal.")
            )
            self.state["next"] = "Stop. Inspect the last completed step before manual recovery."
            save_json(self.journal, self.state)
            raise


def verify_phone(
    device: Device, manifest: Path | None = None, root_check: bool = False
) -> dict[str, Any]:
    inventory = device.inventory()
    profile = load_profile("dandelion-eea")
    issues = compatibility_issues(inventory, profile)
    props = inventory["properties"]
    if props.get("sys.boot_completed") != "1":
        issues.append("Android boot is incomplete.")
    if manifest:
        bundle, _, _ = load_bundle(manifest)
        for key, expected in bundle["expected_properties"].items():
            if props.get(key) != expected:
                issues.append(f"Installed OS mismatch: {key}")
    if root_check:
        result = device.adb("shell", "su", "-c", "id", timeout=30)
        inventory["root_verified"] = bool(re.search(r"(?:^|\s)uid=0\(root\)(?:\s|$)", result))
        if not inventory["root_verified"]:
            issues.append("Shell root was not granted; use the normal Magisk UI.")
    inventory["issues"] = issues
    inventory["software_checks_passed"] = not issues
    inventory["hardware_tests"] = (
        "Not performed by this command. Test cameras, audio, radios and sleep."
    )
    return inventory
