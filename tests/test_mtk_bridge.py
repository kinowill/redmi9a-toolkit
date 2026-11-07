"""Exercise the actual MTK hook with a simulated DA, including failed readback."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from redmi9a import mtk_bridge
from redmi9a.core import ToolkitError
from redmi9a.unlock import PRELOADER_SHA256, UNLOCK_PHRASE


class BridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.original_cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self.original_cwd)
        self.memory = b"MMMM" + b"\x00" * 508
        self.writes = 0
        self.corrupt_readback = False
        self.second_write = False
        self.bad_gpt = False
        self.reinited = False
        self.shutdown_called = False
        reference = files("redmi9a").joinpath("profiles").joinpath("dandelion-gpt.json")
        partitions = json.loads(reference.read_text(encoding="utf-8"))["partitions"]
        self.partitions = [SimpleNamespace(**part) for part in partitions]
        self.flash = SimpleNamespace(writeflash=self.write, readflash=self.read)
        self.mtk = SimpleNamespace(
            reinited=False,
            config=SimpleNamespace(is_brom=True, hwcode=0x766),
            daloader=SimpleNamespace(
                daconfig=SimpleNamespace(pagesize=512),
                xft=SimpleNamespace(xflash=self.flash),
                get_gpt=self.gpt,
                seccfg=self.seccfg,
                shutdown=self.shutdown,
            ),
        )
        self.request = self.root / "request.json"
        self.request.write_text(
            json.dumps(
                {
                    "repository": str(self.root),
                    "preloader": str(self.root / "preloader.bin"),
                    "result": str(self.root / "result.json"),
                    "confirmation": UNLOCK_PHRASE,
                }
            ),
            encoding="utf-8",
        )

    def read(self, **kwargs: Any) -> bytes:
        if self.writes and self.corrupt_readback:
            return b"corrupted"
        return self.memory

    def write(self, **kwargs: Any) -> bool:
        self.writes += 1
        self.memory = kwargs["wdata"]
        return True

    def gpt(self) -> tuple[bytes, Any]:
        if self.bad_gpt:
            self.partitions[-1].sector += 1
        return b"table", SimpleNamespace(partentries=self.partitions)

    def seccfg(self, flag: str, critical: bool) -> tuple[bool, str]:
        self.assertEqual("unlock", flag)
        self.assertFalse(critical)
        part = next(part for part in self.partitions if part.name == "seccfg")
        options = {
            "addr": part.sector * 512,
            "length": 512,
            "filename": "",
            "wdata": b"MMMM" + b"\x02" * 508,
            "parttype": "user",
            "display": False,
        }
        success = self.flash.writeflash(**options)
        if self.second_write:
            self.flash.writeflash(**options)
        return success, "simulated"

    def shutdown(self, bootmode: int) -> bool:
        self.assertEqual(2, bootmode)
        self.shutdown_called = True
        return True

    def run_bridge(self) -> None:
        class Handler:
            def configure_da(self, mtk: Any) -> Any:
                return mtk

        original_import = importlib.import_module

        def invoke() -> None:
            handler = Handler()
            self.mtk.reinited = self.reinited
            handler.configure_da(self.mtk)
            handler.handle_da_cmds(  # type: ignore[attr-defined]
                self.mtk, "da", SimpleNamespace(subcmd="seccfg", flag="unlock", critical=False)
            )

        def modules(name: str, package: str | None = None) -> Any:
            if name == "mtkclient.Library.DA.mtk_da_handler":
                return SimpleNamespace(DaHandler=Handler)
            if name == "mtk":
                return SimpleNamespace(main=invoke)
            return original_import(name, package)

        # The adapter's optional Windows DLL setup is outside these hardware-free tests.
        with (
            patch.object(sys, "platform", "linux"),
            patch.object(sys, "argv", []),
            patch.object(sys, "path", list(sys.path)),
            patch("redmi9a.mtk_bridge.sha256", return_value=PRELOADER_SHA256),
            patch("redmi9a.mtk_bridge.importlib.import_module", side_effect=modules),
        ):
            mtk_bridge.main(self.request)

    def test_one_write_then_identical_readback_and_fastboot_request(self) -> None:
        self.run_bridge()
        result = json.loads((self.root / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(1, self.writes)
        self.assertTrue(result["readback_matches"])
        self.assertFalse(result["bootloader_verified_after_reboot"])
        self.assertTrue(self.shutdown_called)
        self.assertTrue((self.root / "seccfg.before.bin").is_file())

    def test_readback_mismatch_never_claims_success_or_reboots(self) -> None:
        self.corrupt_readback = True
        with self.assertRaises(ToolkitError):
            self.run_bridge()
        self.assertEqual(1, self.writes)
        self.assertFalse(self.shutdown_called)
        self.assertFalse((self.root / "result.json").exists())

    def test_second_write_is_refused_at_actual_hook(self) -> None:
        self.second_write = True
        with self.assertRaises(ToolkitError):
            self.run_bridge()
        self.assertEqual(1, self.writes)
        self.assertFalse(self.shutdown_called)

    def test_changed_gpt_stops_before_backup_or_write(self) -> None:
        self.bad_gpt = True
        with self.assertRaises(ToolkitError):
            self.run_bridge()
        self.assertEqual(0, self.writes)
        self.assertFalse((self.root / "seccfg.before.bin").exists())

    def test_cached_da_session_is_rejected_before_gpt_or_write(self) -> None:
        self.reinited = True
        with self.assertRaises(ToolkitError):
            self.run_bridge()
        self.assertEqual(0, self.writes)


if __name__ == "__main__":
    unittest.main()
