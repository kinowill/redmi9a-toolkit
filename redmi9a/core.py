"""Read-only probes and bounded image operations. No phone writes in this module."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import zlib
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Any


class ToolkitError(Exception):
    """An expected failure, safe to show without raw device output."""


Runner = Callable[[list[str], int], str]
SHA256_PATTERN = re.compile(r"[a-f0-9]{64}")
PROPERTIES = (
    "ro.product.vendor.model",
    "ro.product.vendor.device",
    "ro.vendor.build.version.incremental",
    "ro.vendor.product.cpu.abilist",
    "ro.board.platform",
    "ro.hardware",
    "ro.treble.enabled",
    "ro.boot.flash.locked",
    "ro.build.version.release",
    "ro.build.version.security_patch",
    "ro.vendor.build.security_patch",
    "ro.lineage.version",
    "ro.adb.secure",
    "sys.boot_completed",
)


def run_command(args: list[str], timeout: int = 30) -> str:
    """Never invoke a shell or echo device identifiers/host paths on failure."""
    executable = shutil.which(args[0])
    if executable is None:
        raise ToolkitError(f"Missing executable: {Path(args[0]).name}")
    try:
        result = subprocess.run(
            [executable, *args[1:]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolkitError("Tool timed out; inspect the device before trying again.") from exc
    if result.returncode:
        raise ToolkitError(
            f"{Path(executable).name} failed (exit {result.returncode}); "
            "no automatic retry. Check the device and the upstream tool directly."
        )
    return result.stdout + result.stderr


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ToolkitError("Expected a JSON object.")
    return value


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".report-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def load_profile(name: str) -> dict[str, Any]:
    # Profiles are shipped with reviewed code, never imported from a bundle path.
    if name != "dandelion-eea":
        raise ToolkitError("Unsupported profile. Add a reviewed profile and its tests first.")
    profile = files("redmi9a").joinpath("profiles").joinpath(name + ".json")
    value: dict[str, Any] = json.loads(profile.read_text(encoding="utf-8"))
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_image(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        header = stream.read(4096)
    kind = "unknown"
    expanded = size
    if header.startswith(b"ANDROID!") and size >= 4096:
        kind = "android_boot"
    elif header.startswith(b"AVB0") and size >= 256:
        kind = "avb"
    elif len(header) >= 2048 and header[1080:1082] == b"\x53\xef":
        kind = "ext4"
        log_size = struct.unpack_from("<I", header, 1048)[0]
        if log_size > 6:
            raise ToolkitError("Invalid ext4 block size.")
        blocks = struct.unpack_from("<I", header, 1028)[0]
        incompat = struct.unpack_from("<I", header, 1120)[0]
        if incompat & 0x80:
            blocks |= struct.unpack_from("<I", header, 1360)[0] << 32
        expanded = blocks * (1024 << log_size)
        if not blocks or expanded > size:
            raise ToolkitError("Truncated ext4 image.")
        # shared_blocks is a read-only-compatibility flag; never simply clear it.
        if struct.unpack_from("<I", header, 1124)[0] & 0x4000:
            raise ToolkitError("ext4 shared_blocks still present; use e2fsck unshare_blocks.")
    elif header.startswith(b"\x3a\xff\x26\xed"):
        kind = "android_sparse"
    return {"format": kind, "bytes": size, "expanded_bytes": expanded, "sha256": sha256(path)}


def extract_gzip(source: Path, destination: Path, expected: str, limit: int) -> dict[str, Any]:
    if not SHA256_PATTERN.fullmatch(expected) or sha256(source) != expected:
        raise ToolkitError("Archive SHA256 mismatch or invalid expected digest.")
    if limit <= 0:
        raise ToolkitError("Extraction size limit must be positive.")
    if source.resolve() == destination.resolve() or destination.exists():
        raise ToolkitError("Extraction destination must be a new file.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    # Exclusive creation also protects against an existing destination appearing later.
    try:
        with destination.open("xb") as output, gzip.open(source, "rb") as archive:
            for chunk in iter(lambda: archive.read(1024 * 1024), b""):
                count += len(chunk)
                if count > limit:
                    raise ToolkitError("Decompressed image exceeds the size limit.")
                output.write(chunk)
    except FileExistsError:
        raise ToolkitError("Extraction destination appeared; refusing overwrite.") from None
    except (OSError, EOFError, zlib.error, ToolkitError):
        destination.unlink(missing_ok=True)
        raise ToolkitError(
            "Extraction failed (CRC, truncated archive, disk error or size limit)."
        ) from None
    return inspect_image(destination)


class Device:
    def __init__(
        self,
        adb: str = "adb",
        fastboot: str = "fastboot",
        serial: str | None = None,
        runner: Runner = run_command,
    ) -> None:
        self.adb_executable = adb
        self.fastboot_executable = fastboot
        self.serial = serial
        self.runner = runner

    def adb(self, *args: str, timeout: int = 30) -> str:
        selector = ["-s", self.serial] if self.serial else []
        return self.runner([self.adb_executable, *selector, *args], timeout)

    def fastboot(self, *args: str, timeout: int = 30) -> str:
        if not self.serial:
            raise ToolkitError("A specific device must be selected before fastboot commands.")
        return self.runner([self.fastboot_executable, "-s", self.serial, *args], timeout)

    def select_adb(self) -> None:
        response = self.runner([self.adb_executable, "devices"], 15)
        entries = [
            line.split()
            for line in response.splitlines()
            if line.strip() and not line.startswith(("List of", "*"))
        ]
        devices = {row[0]: row[1] for row in entries if len(row) == 2}
        if self.serial:
            if devices.get(self.serial) != "device":
                raise ToolkitError("Selected phone is absent or USB authorization is pending.")
        elif len(devices) == 1 and next(iter(devices.values())) == "device":
            self.serial = next(iter(devices))
        else:
            raise ToolkitError("Connect and authorize exactly one phone, or use --serial.")

    def getvar(self, name: str) -> str:
        response = self.fastboot("getvar", name)
        matches = re.findall(
            r"^(?:\(bootloader\)\s*)?" + re.escape(name) + r":\s*(\S+)\s*$", response, re.MULTILINE
        )
        if len(matches) != 1:
            raise ToolkitError(f"Missing or ambiguous fastboot variable: {name}")
        return matches[0]

    def inventory(self) -> dict[str, Any]:
        self.select_adb()
        properties = {key: self.adb("shell", "getprop", key).strip() for key in PROPERTIES}
        battery_text = self.adb("shell", "dumpsys", "battery")
        match = re.search(r"^\s*level:\s*(\d+)\s*$", battery_text, re.MULTILINE)
        battery = int(match[1]) if match else None
        config_text = self.adb("shell", "zcat", "/proc/config.gz")
        config = {}
        for name in ("CONFIG_ARM64", "CONFIG_64BIT", "CONFIG_ANDROID_BINDER_IPC_32BIT"):
            if re.search(r"^" + name + r"=y$", config_text, re.MULTILINE):
                config[name] = "y"
            elif re.search(r"^# " + name + r" is not set$", config_text, re.MULTILINE):
                config[name] = "n"
            else:
                config[name] = "unknown"
        return {
            "properties": properties,
            "battery_percent": battery,
            "uname_machine": self.adb("shell", "uname", "-m").strip(),
            "kernel_config": config,
            "kernel_architecture": "aarch64"
            if config.get("CONFIG_ARM64") == "y" and config.get("CONFIG_64BIT") == "y"
            else "unknown",
            "selinux": self.adb("shell", "getenforce").strip(),
        }


def compatibility_issues(inventory: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    issues = []
    for key, expected in profile["properties"].items():
        if inventory["properties"].get(key) != expected:
            issues.append(f"Property mismatch: {key}")
    if inventory.get("kernel_architecture") != profile["kernel_architecture"]:
        issues.append("Kernel architecture mismatch.")
    if inventory.get("kernel_config") != profile["kernel_config"]:
        issues.append("Kernel ARM64/binder64 configuration mismatch or unavailable.")
    if inventory["properties"].get("ro.boot.flash.locked") != "0":
        issues.append("Bootloader must already be unlocked.")
    battery = inventory.get("battery_percent")
    if not isinstance(battery, int) or not 100 >= battery >= profile["minimum_battery_percent"]:
        issues.append("Battery below threshold or unreadable.")
    if inventory["properties"].get("ro.adb.secure") != "1":
        issues.append("Normal ADB authentication must be enabled.")
    if inventory.get("selinux") != "Enforcing":
        issues.append("SELinux must be Enforcing.")
    return issues
