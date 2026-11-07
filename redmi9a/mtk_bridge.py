"""Isolated optional MTK backend. Raw upstream logs remain in a private work folder.

No upstream source is bundled. This adapter is deliberately limited to one known
hardware/GPT and a single seccfg write, not a general flash or account-unlock tool.
"""

from __future__ import annotations

import ctypes
import importlib
import os
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

from redmi9a.core import ToolkitError, load_json, save_json, sha256
from redmi9a.unlock import (
    PRELOADER_SHA256,
    UNLOCK_PHRASE,
    require_fresh_brom,
    validate_gpt,
    validate_write,
)


def main(request_file: Path) -> None:
    request = load_json(request_file)
    if request.get("confirmation") != UNLOCK_PHRASE:
        raise ToolkitError("Explicit unlock intent absent.")
    repository = Path(request["repository"])
    preloader = Path(request["preloader"])
    if sha256(preloader) != PRELOADER_SHA256:
        raise ToolkitError("Preloader reference changed before BROM connection.")
    # Verified upstream repository, dynamically imported only in this child process.
    sys.path.insert(0, str(repository))
    dll_handle = None
    if sys.platform == "win32":
        dll_handle = os.add_dll_directory(
            str(Path(os.environ["ProgramFiles"]) / "UsbDk Runtime Library")
        )
        backend_module = importlib.import_module("usb.backend.libusb1")
        library = repository / "mtkclient" / "Windows" / "libusb-1.0.dll"
        backend = backend_module.get_backend(find_library=lambda _: str(library))
        if backend is None:
            raise ToolkitError("Official MTKClient libusb backend unavailable.")
        backend.lib.libusb_set_option.argtypes = [ctypes.c_void_p, ctypes.c_int]
        if backend.lib.libusb_set_option(backend.ctx, 1) != 0:
            raise ToolkitError("UsbDk backend unavailable. Use the official signed driver.")
    handler_module = importlib.import_module("mtkclient.Library.DA.mtk_da_handler")
    handler = handler_module.DaHandler
    original_configure = handler.configure_da
    reference_path = files("redmi9a").joinpath("profiles").joinpath("dandelion-gpt.json")
    import json

    expected = json.loads(reference_path.read_text(encoding="utf-8"))["partitions"]

    def configure(self: Any, mtk: Any) -> Any:
        require_fresh_brom(mtk)
        return original_configure(self, mtk)

    def unlock(self: Any, mtk: Any, cmd: str, args: Any) -> None:
        if cmd != "da" or args.subcmd != "seccfg" or args.flag != "unlock" or args.critical:
            raise ToolkitError("Only non-critical seccfg unlock is supported.")
        data, table = mtk.daloader.get_gpt()
        if not data or table is None:
            raise ToolkitError("Live GPT could not be read.")
        actual = [
            {"name": part.name, "sector": part.sector, "sectors": part.sectors}
            for part in table.partentries
        ]
        part = validate_gpt(actual, expected)
        if mtk.daloader.daconfig.pagesize != 512 or mtk.daloader.xft is None:
            raise ToolkitError("Unexpected sector size or non-XFlash DA.")
        start, capacity = part["sector"] * 512, part["sectors"] * 512
        flash = mtk.daloader.xft.xflash
        original_write = flash.writeflash
        original = flash.readflash(
            addr=start, length=512, filename="", parttype="user", display=False
        )
        if not original or len(original) != 512 or original[:4] != b"MMMM":
            raise ToolkitError("Only the known seccfg V4 header is supported.")
        # Technical recovery reference, local/private only; never included in public reports.
        Path("seccfg.before.bin").write_bytes(original)
        attempted = False
        verified = False

        def checked_write(
            addr: int, length: int, filename: str, wdata: bytes, parttype: str, display: bool = True
        ) -> bool:
            nonlocal attempted, verified
            validate_write(addr, length, filename, wdata, parttype, start, capacity, attempted)
            attempted = True  # A failed write must never be automatically retried.
            save_json(Path("write-intent.json"), {"partition": "seccfg", "bytes": length})
            if not original_write(
                addr=addr,
                length=length,
                filename=filename,
                wdata=wdata,
                parttype=parttype,
                display=False,
            ):
                return False
            readback = flash.readflash(
                addr=addr, length=length, filename="", parttype="user", display=False
            )
            if readback != wdata:
                raise ToolkitError("seccfg readback differs after writing. Stop and inspect.")
            verified = True
            return True

        flash.writeflash = checked_write
        try:
            success, _ = mtk.daloader.seccfg("unlock", critical=False)
        finally:
            flash.writeflash = original_write
        if not success or not verified:
            raise ToolkitError("No verified unlock write was completed.")
        result = {
            "seccfg_written": True,
            "bytes_written": 512,
            "readback_matches": True,
            "bootloader_verified_after_reboot": False,
            "fastboot_reboot_sent": bool(mtk.daloader.shutdown(bootmode=2)),
        }
        save_json(Path(request["result"]), result)

    handler.configure_da = configure
    handler.handle_da_cmds = unlock
    # Use upstream's default USB ID map. Explicit --vid/--pid in this revision has
    # a dict/list bug; no local patch or modified third-party files are required.
    sys.argv = ["mtk.py", "da", "seccfg", "unlock", "--preloader", str(preloader)]
    try:
        importlib.import_module("mtk").main()
    finally:
        if dll_handle is not None:
            dll_handle.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
