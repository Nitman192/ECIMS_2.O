from __future__ import annotations

import unittest
from unittest.mock import patch

from ecims_agent.device_adapter import USBDevice, WindowsDeviceAdapter


class TestWindowsAdapter(unittest.TestCase):
    @patch("subprocess.run")
    def test_block_unblock_reversible(self, run_mock):
        run_mock.return_value.returncode = 0
        run_mock.return_value.stdout = "Start    REG_DWORD    0x3"
        adapter = WindowsDeviceAdapter()
        self.assertTrue(adapter.block_device(USBDevice(device_id="d", vid="a", pid="b")))
        self.assertTrue(adapter.unblock_device(USBDevice(device_id="d", vid="a", pid="b")))

    @patch("subprocess.run")
    def test_reconcile_calls(self, run_mock):
        run_mock.return_value.returncode = 0
        run_mock.return_value.stdout = "Start    REG_DWORD    0x3"
        adapter = WindowsDeviceAdapter()
        adapter.reconcile_state("observe")
        adapter.reconcile_state("enforce")


if __name__ == "__main__":
    unittest.main()
