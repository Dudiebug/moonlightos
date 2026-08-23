import importlib.machinery
import importlib.util
import json
import pathlib
import socket
import tempfile
import unittest
from unittest import mock


PATH = pathlib.Path(__file__).parents[1] / "scripts" / "moonlightos-bluetoothd"
LOADER = importlib.machinery.SourceFileLoader("moonlightos_bluetooth_service", str(PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
bluetoothd = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(bluetoothd)


ADAPTER_PATH = "/org/bluez/hci0"
DEVICE_PATH = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"


class FakeGLib:
    IO_IN = 1
    IO_HUP = 2
    IO_ERR = 4

    def __init__(self):
        self.next_source = 1
        self.removed = []
        self.timers = []

    def io_add_watch(self, *_arguments):
        self.next_source += 1
        return self.next_source

    def timeout_add_seconds(self, seconds, callback):
        self.timers.append((seconds, callback))
        self.next_source += 1
        return self.next_source

    def idle_add(self, callback):
        callback()
        self.next_source += 1
        return self.next_source

    def source_remove(self, source):
        self.removed.append(source)


class FakeDBusException(Exception):
    def get_dbus_name(self):
        return getattr(self, "_dbus_error_name", "org.bluez.Error.Failed")


class FakeServiceObject:
    def __init__(self, _bus, _path):
        pass


class FakeService:
    Object = FakeServiceObject

    @staticmethod
    def method(*_arguments, **_keywords):
        return lambda function: function


class FakeDBus:
    service = FakeService
    DBusException = FakeDBusException
    Boolean = staticmethod(bool)
    ObjectPath = staticmethod(str)
    UInt32 = staticmethod(int)

    @staticmethod
    def Interface(proxy, _interface):
        return proxy


def managed_objects(*, powered=True, connected=False, paired=True, trusted=True, audio=True):
    uuids = ["0000110b-0000-1000-8000-00805f9b34fb"] if audio else []
    return {
        ADAPTER_PATH: {
            bluetoothd.ADAPTER: {
                "Powered": powered,
                "Discovering": False,
                "Address": "11:22:33:44:55:66",
            }
        },
        DEVICE_PATH: {
            bluetoothd.DEVICE: {
                "Address": "AA:BB:CC:DD:EE:FF",
                "Alias": "Headphones",
                "Paired": paired,
                "Trusted": trusted,
                "Connected": connected,
                "RSSI": -44,
                "UUIDs": uuids,
            }
        },
    }


class ControllerTest(unittest.TestCase):
    def controller(self, directory=None):
        preference = pathlib.Path(directory or "/tmp") / "bluetooth-enabled-test"
        controller = bluetoothd.BluetoothController(
            mock.Mock(), FakeDBus, FakeGLib(), preference_path=preference
        )
        controller.objects = managed_objects()
        controller.bluez_available = True
        return controller

    def test_object_manager_snapshot_parses_adapter_and_device(self):
        controller = self.controller()
        snapshot = controller.snapshot()
        self.assertTrue(snapshot["adapter"]["powered"])
        self.assertEqual(snapshot["devices"][0]["alias"], "Headphones")
        self.assertTrue(snapshot["devices"][0]["audio"])

    def test_interface_signals_update_and_remove_objects(self):
        controller = self.controller()
        controller.properties_changed(
            bluetoothd.DEVICE, {"Connected": True}, [], path=DEVICE_PATH
        )
        self.assertTrue(controller.snapshot()["devices"][0]["connected"])
        controller.interfaces_removed(DEVICE_PATH, [bluetoothd.DEVICE])
        self.assertEqual(controller.snapshot()["devices"], [])

    def test_power_change_is_persisted_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)

            def set_property(_path, _interface, _name, value, success, _failure):
                self.assertTrue(value)
                success()

            controller._set_property = set_property
            controller.set_power(True)
            path = pathlib.Path(directory) / "bluetooth-enabled-test"
            self.assertEqual(path.read_text(), "1\n")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_start_and_stop_discovery_use_bluez_adapter(self):
        controller = self.controller()
        controller._begin_discovery = mock.Mock()
        controller.start_scan()
        controller._begin_discovery.assert_called_once_with(ADAPTER_PATH)
        controller.objects[ADAPTER_PATH][bluetoothd.ADAPTER]["Discovering"] = True
        controller._call = mock.Mock()
        controller.stop_scan()
        self.assertEqual(controller._call.call_args.args[2], "StopDiscovery")

    def test_discovery_filter_precedes_start(self):
        controller = self.controller()
        methods = []

        def call(_path, _interface, method, _arguments, success, _failure, _timeout):
            methods.append(method)
            success()

        controller._call = call
        controller._begin_discovery(ADAPTER_PATH)
        self.assertEqual(methods, ["SetDiscoveryFilter", "StartDiscovery"])
        self.assertEqual(controller.glib.timers[0][0], 15)

    def test_pair_trusts_then_connects(self):
        controller = self.controller()
        controller.objects = managed_objects(paired=False, trusted=False, connected=False)
        calls = []

        def call(_path, _interface, method, _arguments, success, _failure, timeout):
            calls.append((method, timeout))
            success()

        def set_property(_path, _interface, name, _value, success, _failure):
            calls.append((name, 0))
            success()

        controller._call = call
        controller._set_property = set_property
        response = controller.pair(DEVICE_PATH)
        operation = controller.operations[response["operation_id"]]
        self.assertEqual(operation["state"], "completed")
        self.assertEqual(calls, [("Pair", 60), ("Trusted", 0), ("Connect", 15)])

    def test_pair_rejection_is_reported(self):
        controller = self.controller()
        controller.objects = managed_objects(paired=False)

        def call(_path, _interface, method, _arguments, _success, failure, _timeout):
            self.assertEqual(method, "Pair")
            failure(FakeDBusException("rejected"))

        controller._call = call
        response = controller.pair(DEVICE_PATH)
        operation = controller.operations[response["operation_id"]]
        self.assertEqual(operation["state"], "failed")
        self.assertIn("PAIRING FAILED", operation["error"])

    def test_pair_request_has_sixty_second_bound(self):
        controller = self.controller()
        controller.objects = managed_objects(paired=False)
        timeouts = []
        controller._call = lambda *_args: timeouts.append(_args[-1])
        controller.pair(DEVICE_PATH)
        self.assertEqual(timeouts, [60])

    def test_cancel_pairing_uses_bluez_cancellation(self):
        controller = self.controller()
        operation = controller._new_operation("pair", DEVICE_PATH)
        controller._call = mock.Mock()
        controller.cancel_pairing(operation["id"])
        self.assertEqual(controller._call.call_args.args[2], "CancelPairing")
        self.assertEqual(operation["state"], "cancelled")

    def test_connect_failure_is_bounded_and_reported(self):
        controller = self.controller()

        def call(_path, _interface, method, _arguments, _success, failure, timeout):
            self.assertEqual((method, timeout), ("Connect", 15))
            failure(FakeDBusException("not available"))

        controller._call = call
        response = controller._device_action("connect", DEVICE_PATH)
        self.assertEqual(controller.operations[response["operation_id"]]["state"], "failed")

    def test_disconnect_and_remove_device_map_to_bluez(self):
        controller = self.controller()
        methods = []

        def call(_path, _interface, method, _arguments, success, _failure, _timeout):
            methods.append(method)
            success()

        controller._call = call
        controller.objects[DEVICE_PATH][bluetoothd.DEVICE]["Connected"] = True
        controller._device_action("disconnect", DEVICE_PATH)
        controller.forget(DEVICE_PATH)
        self.assertEqual(methods, ["Disconnect", "RemoveDevice"])

    def test_bad_device_identifier_is_rejected(self):
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, "INVALID"):
            controller.handle({"command": "connect", "device": "/tmp/not-a-device"})

    def test_unknown_command_and_invalid_power_are_rejected(self):
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED"):
            controller.handle({"command": "execute", "value": "anything"})
        with self.assertRaisesRegex(ValueError, "TRUE OR FALSE"):
            controller.handle({"command": "set_power", "powered": "yes"})

    def test_simultaneous_device_actions_are_rejected(self):
        controller = self.controller()
        controller._new_operation("pair", DEVICE_PATH)
        with self.assertRaisesRegex(ValueError, "ALREADY RUNNING"):
            controller._new_operation("connect", DEVICE_PATH)

    def test_adapter_removal_fails_active_operation(self):
        controller = self.controller()
        operation = controller._new_operation("connect", DEVICE_PATH)
        controller.interfaces_removed(ADAPTER_PATH, [bluetoothd.ADAPTER])
        self.assertEqual(operation["state"], "failed")
        self.assertIn("ADAPTER REMOVED", operation["error"])

    def test_bluez_restart_rebuilds_state_and_agent(self):
        controller = self.controller()
        controller.refresh_objects = mock.Mock()
        controller.register_agent = mock.Mock()
        operation = controller._new_operation("connect", DEVICE_PATH)
        controller.owner_changed("")
        self.assertEqual(operation["state"], "failed")
        controller.owner_changed(":1.42")
        controller.refresh_objects.assert_called_once_with()
        controller.register_agent.assert_called_once_with()

    def test_pairing_agent_registers_with_keyboard_display(self):
        controller = self.controller()
        controller.agent = object()
        manager = mock.Mock()
        manager.RegisterAgent.side_effect = lambda *_args, **kwargs: kwargs["reply_handler"]()
        controller._interface = mock.Mock(return_value=manager)
        controller.register_agent()
        self.assertTrue(controller.agent_registered)
        self.assertEqual(manager.RegisterAgent.call_args.args[1], "KeyboardDisplay")

    def test_audio_sink_selection_is_explicit(self):
        runner = mock.Mock(
            side_effect=[
                mock.Mock(returncode=0, stdout="Audio\n Sinks:\n  45. bluez_output.AA_BB_CC_DD_EE_FF [vol]\n Sources:\n"),
                mock.Mock(returncode=0, stdout=""),
            ]
        )
        controller = bluetoothd.BluetoothController(
            mock.Mock(), FakeDBus, FakeGLib(), process_runner=runner
        )
        self.assertEqual(controller._select_audio_sink("Headphones", "AA:BB:CC:DD:EE:FF"), "")
        self.assertEqual(runner.call_args_list[-1].args[0], ["wpctl", "set-default", "45"])

    def test_missing_audio_sink_leaves_device_connected(self):
        runner = mock.Mock(return_value=mock.Mock(returncode=0, stdout="Audio\n Sinks:\n"))
        controller = bluetoothd.BluetoothController(
            mock.Mock(), FakeDBus, FakeGLib(), process_runner=runner
        )
        self.assertIn("NO AUDIO OUTPUT", controller._select_audio_sink("Headphones", "AA:BB:CC:DD:EE:FF"))


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.controller = bluetoothd.BluetoothController(mock.Mock(), FakeDBus, FakeGLib())
        self.controller.objects = managed_objects(paired=False)
        agent_class = bluetoothd.build_agent_class(FakeDBus)
        self.agent = agent_class(mock.Mock(), bluetoothd.AGENT_PATH, self.controller)

    def test_numeric_confirmation_and_reply(self):
        accepted = mock.Mock()
        rejected = mock.Mock()
        self.agent.RequestConfirmation(DEVICE_PATH, 123456, accepted, rejected)
        prompt = self.controller.snapshot()["prompt"]
        self.assertEqual(prompt["kind"], "confirmation")
        self.assertEqual(prompt["passkey"], "123456")
        self.controller.agent_reply({"prompt_id": prompt["id"], "accepted": True})
        accepted.assert_called_once_with()

    def test_pin_and_passkey_input_are_validated(self):
        pin_reply = mock.Mock()
        reject = mock.Mock()
        self.agent.RequestPinCode(DEVICE_PATH, pin_reply, reject)
        prompt = self.controller.prompt
        self.controller.agent_reply({"prompt_id": prompt["id"], "accepted": True, "value": "A0420"})
        pin_reply.assert_called_once_with("A0420")

        passkey_reply = mock.Mock()
        self.agent.RequestPasskey(DEVICE_PATH, passkey_reply, reject)
        prompt = self.controller.prompt
        self.controller.agent_reply({"prompt_id": prompt["id"], "accepted": True, "value": 123456})
        passkey_reply.assert_called_once_with(123456)

    def test_authorization_can_be_rejected(self):
        accepted = mock.Mock()
        rejected = mock.Mock()
        self.agent.AuthorizeService(DEVICE_PATH, "service-id", accepted, rejected)
        prompt = self.controller.prompt
        self.controller.agent_reply({"prompt_id": prompt["id"], "accepted": False})
        rejected.assert_called_once()

    def test_displayed_passkey_does_not_block_agent(self):
        self.agent.DisplayPasskey(DEVICE_PATH, 42, 0)
        self.assertEqual(self.controller.prompt["kind"], "display_passkey")
        self.assertEqual(self.controller.prompt["passkey"], "000042")


class SocketServerTest(unittest.TestCase):
    def server_with_pair(self, incoming):
        glib = FakeGLib()
        controller = mock.Mock()
        controller.handle.return_value = {"ok": True, "adapter": None, "devices": []}
        server = bluetoothd.JsonSocketServer(pathlib.Path("/tmp/unused.sock"), controller, glib)
        service_socket, peer = socket.socketpair()
        fd = service_socket.fileno()
        server.clients[fd] = (service_socket, bytearray(), 1)
        peer.sendall(incoming)
        while fd in server.clients:
            server._read_client(fd, glib.IO_IN)
        response = json.loads(peer.recv(65536).split(b"\n", 1)[0])
        peer.close()
        return response, controller

    def test_invalid_json_is_rejected(self):
        response, controller = self.server_with_pair(b"not-json\n")
        self.assertFalse(response["ok"])
        controller.handle.assert_not_called()

    def test_oversized_message_is_rejected(self):
        response, controller = self.server_with_pair(b"x" * (bluetoothd.MAX_MESSAGE + 1))
        self.assertFalse(response["ok"])
        self.assertIn("TOO LARGE", response["error"])
        controller.handle.assert_not_called()

    def test_valid_json_is_dispatched(self):
        response, controller = self.server_with_pair(b'{"command":"snapshot"}\n')
        self.assertTrue(response["ok"])
        controller.handle.assert_called_once_with({"command": "snapshot"})

    def test_socket_permissions_are_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "control.sock"
            server = bluetoothd.JsonSocketServer(path, mock.Mock(), FakeGLib())
            listener = mock.Mock()
            listener.fileno.return_value = 7
            with mock.patch.object(bluetoothd.socket, "socket", return_value=listener), mock.patch.object(
                bluetoothd.os, "chmod"
            ) as chmod:
                server.start()
                chmod.assert_called_once_with(path, 0o600)
                server.close()


if __name__ == "__main__":
    unittest.main()
