"""Guarded MTKClient integration. Never used for account/activation bypass."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .core import Device, ToolkitError, compatibility_issues, load_profile, run_command, save_json
from .workflow import Installer

MTK_REVISION = "118a000a83ea31c4f427fe5225abfe964546e05e"
PRELOADER_SHA256 = "c0dfa5d13d88f03aeee4a2a4af943175cdc755cdadf5a96c20f16f83e1035cc4"
UNLOCK_PHRASE = "UNLOCK-DANDELION"


def validate_write(
    addr: int,
    length: int,
    filename: str,
    data: bytes,
    parttype: str,
    start: int,
    capacity: int,
    attempted: bool,
) -> None:
    if (
        attempted
        or parttype != "user"
        or filename
        or addr != start
        or length != 512
        or len(data) != 512
        or capacity < 512
        or data[:4] != b"MMMM"
    ):
        raise ToolkitError("Refused write outside the single expected 512-byte seccfg block.")


def validate_gpt(actual: list[dict[str, Any]], expected: list[dict[str, Any]]) -> dict[str, Any]:
    if actual != expected:
        raise ToolkitError("Live GPT differs from the validated 32GB dandelion reference.")
    matches = [part for part in actual if part.get("name") == "seccfg"]
    if len(matches) != 1 or not matches[0]["sector"] > 0 or matches[0]["sectors"] < 1:
        raise ToolkitError("Missing or ambiguous seccfg partition.")
    return matches[0]


def require_fresh_brom(mtk: Any) -> None:
    if mtk is None or mtk.reinited or not mtk.config.is_brom or mtk.config.hwcode != 0x766:
        raise ToolkitError("A fresh BROM session identifying hardware 0x766 is required.")


def unlock_phone(
    device: Device,
    repository: Path,
    preloader: Path,
    work: Path,
    accept_data_loss: bool,
    confirmation: str,
) -> dict[str, Any]:
    if not accept_data_loss or confirmation != UNLOCK_PHRASE:
        raise ToolkitError("Unlock requires --accept-data-loss --confirm UNLOCK-DANDELION.")
    inventory = device.inventory()
    # This gate accepts a locked bootloader, while retaining every other identity check.
    if inventory["properties"].get("ro.boot.flash.locked") not in {"0", "1"}:
        raise ToolkitError("Bootloader state is unknown.")
    comparison = {
        **inventory,
        "properties": {**inventory["properties"], "ro.boot.flash.locked": "0"},
    }
    issues = compatibility_issues(comparison, load_profile("dandelion-eea"))
    if issues:
        raise ToolkitError("Unlock preflight refused: " + "; ".join(issues))
    if inventory["properties"].get("ro.boot.flash.locked") == "0":
        return {
            "already_unlocked": True,
            "phone_changed": False,
            "note": "No MediaTek command or write was performed.",
        }
    # OEM toggle is a user setting, never silently enabled or bypassed here.
    if device.adb("shell", "getprop", "sys.oem_unlock_allowed").strip() != "1":
        raise ToolkitError("Enable OEM unlocking normally in Developer options first.")
    if run_command(["git", "-C", str(repository), "rev-parse", "HEAD"], 15).strip() != MTK_REVISION:
        raise ToolkitError("Unsupported MTKClient revision; use the pinned upstream commit.")
    if run_command(
        ["git", "-C", str(repository), "status", "--porcelain", "--untracked-files=no"], 15
    ).strip():
        raise ToolkitError("MTKClient tracked files must be clean.")
    from .core import sha256

    if sha256(preloader) != PRELOADER_SHA256:
        raise ToolkitError("Preloader RAM-initialization reference does not match this firmware.")
    if work.exists():
        raise ToolkitError("Unlock work directory must be new; never reuse a DA session.")
    # Fail before asking for cable manipulation if the optional libraries are missing.
    for module in ("usb.core", "Crypto", "Cryptodome", "serial", "colorama"):
        try:
            importlib.import_module(module)
        except ImportError as exc:
            raise ToolkitError(
                "Install the optional mtk dependencies in this Python environment."
            ) from exc
    work.mkdir(parents=True)
    request = {
        "repository": str(repository.resolve()),
        "preloader": str(preloader.resolve()),
        "result": str((work / "result.json").resolve()),
        "confirmation": UNLOCK_PHRASE,
    }
    save_json(work / "preflight.json", inventory)
    save_json(work / "request.json", request)
    print(
        "Disconnect and power off the same phone. Hold both volume buttons while reconnecting USB."
        " Release when BROM is detected. Waiting up to 180 seconds."
        " Do not force Power indefinitely.",
        file=sys.stderr,
    )
    bridge = Path(__file__).with_name("mtk_bridge.py")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    environment["PYTHONIOENCODING"] = "utf-8"
    try:
        with (work / "mtk-private.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                [sys.executable, str(bridge), str((work / "request.json").resolve())],
                cwd=work,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise ToolkitError(
            "BROM operation timed out. Keep private logs and inspect before retrying."
        ) from exc
    from .core import load_json

    if completed.returncode or not (work / "result.json").is_file():
        raise ToolkitError(
            "MTK operation did not complete. Inspect the private log; no blind retry."
        )
    result = load_json(work / "result.json")
    if not (
        result.get("readback_matches") is True
        and result.get("bytes_written") == 512
        and result.get("fastboot_reboot_sent") is True
    ):
        raise ToolkitError("Unlock write/readback/reboot was not verified.")
    # The original phone selection stays pinned across USB mode changes.
    checker = Installer(device, Path(), work / "unused.json")
    checker.wait_fastboot(False)
    if device.getvar("product") != "dandelion" or device.getvar("unlocked") != "yes":
        raise ToolkitError("Bootloader did not independently confirm dandelion/unlocked=yes.")
    result["bootloader_verified_after_reboot"] = True
    save_json(work / "result.json", result)
    return result
