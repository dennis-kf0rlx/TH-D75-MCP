"""Serial selection and service-control tests with no radio or systemd."""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from serial.tools import list_ports


SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"
USB = "/dev/cu.usbmodem123"
BLUETOOTH = "/dev/cu.TH-D75"
KENWOOD = SimpleNamespace(device=USB, vid=0x2166, pid=0x9023)
OTHER_USB = SimpleNamespace(device="/dev/cu.usbmodem001", vid=0x1234, pid=0x5678)
DIALIN = SimpleNamespace(device="/dev/tty.usbmodem123", vid=0x2166, pid=0x9023)


def load_server(platform, ports=(), present=(), env=None):
    spec = importlib.util.spec_from_file_location("d75settings", SERVER_PATH)
    server = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "platform", platform), \
         mock.patch.object(list_ports, "comports", return_value=ports), \
         mock.patch.object(os.path, "exists", side_effect=present.__contains__), \
         mock.patch.dict(os.environ, env or {}, clear=True):
        spec.loader.exec_module(server)
    return server


class SerialSelectionTests(unittest.TestCase):
    def test_macos_prefers_matching_usb_callout_to_bluetooth(self):
        server = load_server("darwin", (OTHER_USB, DIALIN, KENWOOD),
                             (OTHER_USB.device, DIALIN.device, USB, BLUETOOTH))
        self.assertEqual((server.SERIAL, server.TRANSPORT), (USB, "usb"))

    def test_macos_falls_back_to_bluetooth_without_matching_usb(self):
        server = load_server("darwin", (OTHER_USB, DIALIN),
                             (OTHER_USB.device, DIALIN.device, BLUETOOTH))
        self.assertEqual((server.SERIAL, server.TRANSPORT), (BLUETOOTH, "bluetooth"))

    def test_macos_honors_explicit_serial_or_bluetooth_selection(self):
        custom_usb = "/dev/cu.usbmodem456"
        cases = [
            ({"D75_SERIAL": custom_usb}, (custom_usb, "usb")),
            ({"D75_TRANSPORT": "bluetooth"}, (BLUETOOTH, "bluetooth")),
        ]
        for env, expected in cases:
            with self.subTest(env=env):
                server = load_server("darwin", (KENWOOD,), (USB, BLUETOOTH, custom_usb), env)
                self.assertEqual((server.SERIAL, server.TRANSPORT), expected)

    def test_linux_keeps_udev_path_and_rfcomm_fallback(self):
        for present, expected in [
            (("/dev/thd75", "/dev/rfcomm0"), ("/dev/thd75", "usb")),
            (("/dev/rfcomm0",), ("/dev/rfcomm0", "bluetooth")),
        ]:
            with self.subTest(present=present):
                server = load_server("linux", present=present)
                self.assertEqual((server.SERIAL, server.TRANSPORT), expected)


class MonitorControlTests(unittest.TestCase):
    def test_stop_monitor_returns_without_systemctl(self):
        server = load_server("darwin")
        with mock.patch.object(server.shutil, "which", return_value=None) as which, \
             mock.patch.object(server, "monitor_active") as monitor_active, \
             mock.patch.object(server, "run") as run, \
             mock.patch.object(server, "wait_monitor") as wait_monitor:
            server.stop_monitor()
        which.assert_called_once_with("systemctl")
        monitor_active.assert_not_called()
        run.assert_not_called()
        wait_monitor.assert_not_called()
