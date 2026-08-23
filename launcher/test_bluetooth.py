import json
import pathlib
import unittest
from unittest import mock

import moonlightos_bluetooth as bluetooth


ADAPTER_ON = {
    "ok": True,
    "adapter": {"path": "/org/bluez/hci0", "powered": True, "discovering": False},
    "devices": [],
    "operations": [],
    "prompt": None,
}
DEVICE = {
    "path": "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
    "address": "AA:BB:CC:DD:EE:FF",
    "alias": "Wireless Controller",
    "paired": True,
    "trusted": True,
    "connected": False,
    "rssi": -40,
    "audio": False,
}


class FakeScreen:
    def __init__(self, keys=()):
        self.keys = list(keys)
        self.drawn = []
        self.timeouts = []

    def getmaxyx(self):
        return 30, 100

    def erase(self):
        pass

    def border(self):
        pass

    def addstr(self, _row, _column, value):
        self.drawn.append(value)

    def addnstr(self, _row, _column, value, _length):
        self.drawn.append(value)

    def refresh(self):
        pass

    def timeout(self, value):
        self.timeouts.append(value)

    def getch(self):
        return self.keys.pop(0) if self.keys else 27


class FakeClient:
    def __init__(self, snapshots=()):
        self.snapshots = list(snapshots)
        self.requests = []

    def snapshot(self):
        if not self.snapshots:
            return dict(ADAPTER_ON)
        value = self.snapshots.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def request(self, command, **fields):
        self.requests.append((command, fields))
        if command in {"pair", "connect", "disconnect", "forget", "use_audio"}:
            return {"ok": True, "operation_id": "op-1"}
        return {"ok": True, "accepted": True}


class BluetoothHelpersTest(unittest.TestCase):
    def test_duplicate_aliases_receive_address_suffixes(self):
        devices = [dict(DEVICE), dict(DEVICE, path=DEVICE["path"][:-2] + "11", address="AA:BB:CC:DD:EE:11")]
        self.assertEqual(
            bluetooth.device_labels(devices),
            ["Wireless Controller · EE:FF", "Wireless Controller · EE:11"],
        )

    def test_unnamed_device_never_has_empty_label(self):
        self.assertEqual(
            bluetooth.device_labels([dict(DEVICE, alias="")]),
            ["UNKNOWN DEVICE · EE:FF"],
        )

    def test_socket_client_rejects_malformed_response(self):
        connection = mock.Mock()
        connection.recv.side_effect = [b"not json\n"]
        with mock.patch.object(bluetooth.socket, "socket", return_value=connection):
            with self.assertRaisesRegex(bluetooth.BluetoothError, "INVALID RESPONSE"):
                bluetooth.BluetoothClient(pathlib.Path("/tmp/control.sock")).snapshot()
        connection.close.assert_called_once_with()

    def test_socket_client_accepts_snapshot(self):
        connection = mock.Mock()
        connection.recv.side_effect = [(json.dumps(ADAPTER_ON) + "\n").encode()]
        with mock.patch.object(bluetooth.socket, "socket", return_value=connection):
            snapshot = bluetooth.BluetoothClient(pathlib.Path("/tmp/control.sock")).snapshot()
        self.assertTrue(snapshot["adapter"]["powered"])


class BluetoothMenuTest(unittest.TestCase):
    def test_no_adapter_screen_returns_with_escape(self):
        screen = FakeScreen([27])
        client = FakeClient([dict(ADAPTER_ON, adapter=None)])
        bluetooth.BluetoothMenu(screen, client).run()
        self.assertIn("NO BLUETOOTH ADAPTER FOUND", screen.drawn)

    def test_powered_off_screen_can_turn_adapter_on(self):
        off = dict(ADAPTER_ON, adapter={"path": "/org/bluez/hci0", "powered": False})
        screen = FakeScreen([10, 27])
        client = FakeClient([off, ADAPTER_ON])
        bluetooth.BluetoothMenu(screen, client).run()
        self.assertIn(("set_power", {"powered": True}), client.requests)

    def test_powered_on_screen_lists_connected_state(self):
        screen = FakeScreen([27])
        client = FakeClient([dict(ADAPTER_ON, devices=[dict(DEVICE, connected=True)])])
        bluetooth.BluetoothMenu(screen, client).run()
        self.assertTrue(any("Wireless Controller" in value and "CONNECTED" in value for value in screen.drawn))

    def test_scan_countdown_and_escape_stop_discovery(self):
        screen = FakeScreen([27])
        client = FakeClient([ADAPTER_ON])
        bluetooth.BluetoothMenu(screen, client)._scan()
        self.assertEqual(client.requests[0][0], "start_scan")
        self.assertEqual(client.requests[-1][0], "stop_scan")
        self.assertTrue(any("SCANNING" in value for value in screen.drawn))

    def test_pair_success_finishes_without_external_screen(self):
        completed = dict(
            ADAPTER_ON,
            operations=[{"id": "op-1", "type": "pair", "state": "completed", "device": DEVICE["path"]}],
        )
        screen = FakeScreen([10])
        client = FakeClient([completed])
        bluetooth.BluetoothMenu(screen, client)._pair(dict(DEVICE, paired=False))
        self.assertIn(("pair", {"device": DEVICE["path"]}), client.requests)

    def test_pair_confirmation_can_be_rejected(self):
        prompt = {
            "id": "prompt-1",
            "kind": "confirmation",
            "passkey": "123456",
            "operation_id": "op-1",
        }
        working = dict(
            ADAPTER_ON,
            operations=[{"id": "op-1", "type": "pair", "state": "working", "device": DEVICE["path"]}],
            prompt=prompt,
        )
        screen = FakeScreen([27])
        client = FakeClient([working])
        success, _operation = bluetooth.BluetoothMenu(screen, client)._wait_operation(
            "op-1", "PAIRING", cancellable_pairing=True
        )
        self.assertFalse(success)
        self.assertIn(
            ("agent_reply", {"prompt_id": "prompt-1", "accepted": False}), client.requests
        )

    def test_pair_timeout_is_reported(self):
        failed = dict(
            ADAPTER_ON,
            operations=[{
                "id": "op-1",
                "type": "pair",
                "state": "failed",
                "device": DEVICE["path"],
                "error": "PAIRING TIMED OUT",
            }],
        )
        screen = FakeScreen([27])
        client = FakeClient([failed])
        success, _operation = bluetooth.BluetoothMenu(screen, client)._wait_operation(
            "op-1", "PAIRING", cancellable_pairing=True
        )
        self.assertFalse(success)
        self.assertTrue(any("PAIRING TIMED OUT" in value for value in screen.drawn))

    def test_adapter_removal_during_operation_is_recoverable(self):
        screen = FakeScreen([27])
        client = FakeClient([dict(ADAPTER_ON, adapter=None)])
        success, _operation = bluetooth.BluetoothMenu(screen, client)._wait_operation("op-1", "CONNECTING")
        self.assertFalse(success)
        self.assertIn("BLUETOOTH ADAPTER REMOVED", screen.drawn)

    def test_service_unavailable_always_offers_back(self):
        screen = FakeScreen([bluetooth.curses.KEY_DOWN, 10])
        client = FakeClient([bluetooth.BluetoothError("unavailable")])
        bluetooth.BluetoothMenu(screen, client).run()
        self.assertIn("BLUETOOTH SERVICE UNAVAILABLE", screen.drawn)
        self.assertTrue(any("BACK" in value for value in screen.drawn))

    def test_device_screen_changes_action_for_connection_state(self):
        disconnected = dict(ADAPTER_ON, devices=[DEVICE])
        screen = FakeScreen([27])
        bluetooth.BluetoothMenu(screen, FakeClient([disconnected]))._device_screen(DEVICE["path"])
        self.assertTrue(any("CONNECT" in value for value in screen.drawn))


if __name__ == "__main__":
    unittest.main()
