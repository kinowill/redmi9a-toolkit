"""Portable command line. Commands print sanitized JSON, progress goes to stderr."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .core import (
    Device,
    ToolkitError,
    compatibility_issues,
    extract_gzip,
    inspect_image,
    load_profile,
    save_json,
)
from .unlock import unlock_phone
from .workflow import Installer, plan_bundle, verify_phone


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Redmi 9A community toolkit. Read docs before installing a ROM."
    )
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--adb", default="adb", help="Android platform-tools adb executable")
    root.add_argument(
        "--fastboot", default="fastboot", help="Android platform-tools fastboot executable"
    )
    root.add_argument("--serial", help="Select one phone; never written to reports")
    root.add_argument("--output", type=Path, help="Save sanitized JSON report (keep outside Git)")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Read-only device identity and installation prerequisites")
    unlock = commands.add_parser("unlock", help="DESTRUCTIVE: guarded MediaTek bootloader unlock")
    unlock.add_argument("--mtkclient", type=Path, required=True)
    unlock.add_argument(
        "--preloader", type=Path, required=True, help="Stock reference loaded into RAM"
    )
    unlock.add_argument("--work-dir", type=Path, required=True)
    unlock.add_argument("--accept-data-loss", action="store_true")
    unlock.add_argument("--confirm", default="")
    image = commands.add_parser(
        "inspect", help="Hash image and detect its format; not a content audit"
    )
    image.add_argument("image", type=Path)
    extract = commands.add_parser(
        "extract", help="Verify SHA256/CRC and extract gzip with a size cap"
    )
    extract.add_argument("archive", type=Path)
    extract.add_argument("destination", type=Path)
    extract.add_argument("--sha256", required=True)
    extract.add_argument("--max-bytes", type=int, default=4 * 1024**3)
    for name in ("plan", "install"):
        command = commands.add_parser(
            name,
            help="Audit an offline plan"
            if name == "plan"
            else "DESTRUCTIVE: install an audited local bundle",
        )
        command.add_argument("bundle", type=Path)
        if name == "install":
            command.add_argument("--erase-userdata", action="store_true")
            command.add_argument("--confirm", default="")
            command.add_argument("--journal", type=Path, required=True)
    verify = commands.add_parser(
        "verify", help="Read-only Android checks after boot/USB authorization"
    )
    verify.add_argument("--bundle", type=Path)
    verify.add_argument("--root-check", action="store_true", help="Request Shell root using Magisk")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    device = Device(args.adb, args.fastboot, args.serial)
    try:
        result: dict[str, Any]
        status = 0
        if args.command == "doctor":
            result = device.inventory()
            result["profile"] = "dandelion-eea"
            result["installation_issues"] = compatibility_issues(
                result, load_profile("dandelion-eea")
            )
            result["note"] = "Device match does not certify an OS image. No phone settings changed."
            status = 2 if result["installation_issues"] else 0
        elif args.command == "unlock":
            result = unlock_phone(
                device,
                args.mtkclient,
                args.preloader,
                args.work_dir,
                args.accept_data_loss,
                args.confirm,
            )
        elif args.command == "inspect":
            result = inspect_image(args.image)
        elif args.command == "extract":
            result = extract_gzip(args.archive, args.destination, args.sha256, args.max_bytes)
        elif args.command == "plan":
            result = plan_bundle(args.bundle)
        elif args.command == "install":
            result = Installer(
                device, args.bundle, args.journal, emit=lambda text: print(text, file=sys.stderr)
            ).execute(erase_userdata=args.erase_userdata, confirmation=args.confirm)
        else:
            result = verify_phone(device, args.bundle, args.root_check)
            status = 0 if result["software_checks_passed"] else 2
        if args.output:
            save_json(args.output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return status
    except (ToolkitError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Raw OS exceptions may contain personal paths; keep stdout suitable for sharing.
        message = (
            str(exc)
            if isinstance(exc, ToolkitError)
            else ("Invalid input or local I/O error; check the manifest and readable file paths.")
        )
        print(json.dumps({"error": message, "phone_success_claimed": False}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted. Inspect phone and journal before continuing.", file=sys.stderr)
        return 130
