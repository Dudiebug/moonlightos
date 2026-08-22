import importlib.machinery
import importlib.util
import io
import json
import pathlib
import re
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "launcher"))
import moonlightos_support as support

loader = importlib.machinery.SourceFileLoader(
    "support_exporter", str(ROOT / "scripts" / "moonlightos-support-export")
)
spec = importlib.util.spec_from_loader(loader.name, loader)
exporter = importlib.util.module_from_spec(spec)
loader.exec_module(exporter)


class DestinationTest(unittest.TestCase):
    def test_selects_mounted_and_ordinary_unmounted_removable_partitions(self):
        data = {
            "blockdevices": [
                {
                    "path": "/dev/sdb",
                    "type": "disk",
                    "tran": "usb",
                    "rm": True,
                    "ro": False,
                    "children": [
                        {
                            "path": "/dev/sdb1",
                            "type": "part",
                            "rm": False,
                            "ro": False,
                            "fstype": "vfat",
                            "label": "FILES",
                            "mountpoints": ["/media/files"],
                        },
                        {
                            "path": "/dev/sdb2",
                            "type": "part",
                            "rm": False,
                            "ro": False,
                            "fstype": "ext4",
                            "label": "ARCHIVE",
                            "mountpoints": [None],
                        },
                    ],
                }
            ]
        }
        found = support.destinations_from_lsblk(data, lambda path: path == "/media/files")
        self.assertEqual({item.device for item in found}, {"/dev/sdb1", "/dev/sdb2"})
        self.assertTrue(found[0].mounted)
        unmounted = next(item for item in found if item.device == "/dev/sdb2")
        self.assertFalse(unmounted.mounted)
        self.assertEqual(unmounted.label, support.SUPPORT_MOUNT_LABEL)
        self.assertEqual(unmounted.display_label, "ARCHIVE")
        self.assertIn("WILL MOUNT TEMPORARILY", unmounted.display_name)

    def test_rejects_internal_nvme_and_sata(self):
        data = {
            "blockdevices": [
                {
                    "path": "/dev/nvme0n1",
                    "type": "disk",
                    "tran": "nvme",
                    "rm": False,
                    "children": [
                        {
                            "path": "/dev/nvme0n1p1",
                            "type": "part",
                            "ro": False,
                            "fstype": "ext4",
                            "label": "MOONLIGHTOS_SUPPORT",
                            "mountpoints": ["/mnt/internal"],
                        }
                    ],
                },
                {
                    "path": "/dev/sda",
                    "type": "disk",
                    "tran": "sata",
                    "rm": False,
                    "children": [
                        {
                            "path": "/dev/sda1",
                            "type": "part",
                            "ro": False,
                            "fstype": "ext4",
                            "mountpoints": ["/mnt/sata"],
                        }
                    ],
                },
            ]
        }
        self.assertEqual(support.destinations_from_lsblk(data, lambda _path: True), [])

    def test_rejects_read_only_and_iso9660(self):
        data = {
            "blockdevices": [
                {
                    "path": "/dev/sdc",
                    "type": "disk",
                    "tran": "usb",
                    "rm": True,
                    "children": [
                        {
                            "path": "/dev/sdc1",
                            "type": "part",
                            "ro": False,
                            "fstype": "iso9660",
                            "mountpoints": ["/run/live/medium"],
                        },
                        {
                            "path": "/dev/sdc2",
                            "type": "part",
                            "ro": True,
                            "fstype": "ext4",
                            "mountpoints": ["/media/readonly"],
                        },
                    ],
                }
            ]
        }
        self.assertEqual(support.destinations_from_lsblk(data, lambda _path: True), [])

    def test_live_boot_usb_entire_tree_is_rejected(self):
        data = {
            "blockdevices": [
                {
                    "path": "/dev/sdd",
                    "type": "disk",
                    "tran": "usb",
                    "rm": True,
                    "children": [
                        {
                            "path": "/dev/sdd1",
                            "type": "part",
                            "ro": False,
                            "fstype": "iso9660",
                            "label": "MOONLIGHTOS",
                            "mountpoints": ["/run/live/medium"],
                        },
                        {
                            "path": "/dev/sdd2",
                            "type": "part",
                            "ro": False,
                            "fstype": "ext4",
                            "label": "persistence",
                            "mountpoints": ["/run/live/persistence/sdd2"],
                        },
                    ],
                }
            ]
        }
        self.assertEqual(support.destinations_from_lsblk(data, lambda _path: True), [])

    def test_whole_disk_usb_filesystem_is_allowed(self):
        data = {
            "blockdevices": [
                {
                    "path": "/dev/sde",
                    "type": "disk",
                    "tran": "usb",
                    "rm": True,
                    "ro": False,
                    "fstype": "exfat",
                    "label": "SUPPORT",
                    "mountpoints": ["/media/support"],
                }
            ]
        }
        found = support.destinations_from_lsblk(data, lambda _path: True)
        self.assertEqual([item.device for item in found], ["/dev/sde"])

    def test_unmounted_whole_disk_usb_filesystem_is_allowed(self):
        data = {
            "blockdevices": [
                {
                    "path": "/dev/sdf",
                    "type": "disk",
                    "tran": "usb",
                    "rm": True,
                    "ro": False,
                    "fstype": "vfat",
                    "label": "DIAGS",
                    "mountpoints": [None],
                }
            ]
        }
        found = support.destinations_from_lsblk(data, lambda _path: False)
        self.assertEqual([item.device for item in found], ["/dev/sdf"])
        self.assertFalse(found[0].mounted)
        self.assertEqual(found[0].display_label, "DIAGS")

    def test_unsafe_label_is_terminal_safe(self):
        self.assertEqual(support.safe_terminal_text("USB\x1b[2J\nBAD"), "USB??2J?BAD")


class ExporterTest(unittest.TestCase):
    def make_archive(self, directory: pathlib.Path, secret: str = "FAKESECRET-123") -> pathlib.Path:
        bundle = directory / "moonlightos-support"
        bundle.mkdir()
        exporter.write_text(bundle / "status.txt", f"password={secret}\nBearer {secret}\n")
        exporter.create_manifest(bundle)
        archive = directory / "fixture.tar.gz"
        with tarfile.open(archive, "w:gz", dereference=False) as container:
            container.add(bundle, arcname="moonlightos-support")
        exporter.verify_archive(archive)
        return archive

    def test_filename_syntax(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            exporter.os.environ,
            {"MOONLIGHTOS_SUPPORT_MACHINE_ID": str(pathlib.Path(directory) / "machine-id")},
        ):
            pathlib.Path(directory, "machine-id").write_text("abcdef1234567890\n")
            self.assertRegex(
                exporter.archive_filename(),
                r"^moonlightos-support-\d{8}-\d{6}Z-abcdef12\.tar\.gz$",
            )

    def test_destination_identity_is_revalidated(self):
        selected = support.Destination(
            "/dev/sdb1", "/media/usb", "FILES", "ext4", True, "8:17", "uuid-one"
        )
        swapped = support.Destination(
            "/dev/sdb1", "/media/usb", "FILES", "ext4", True, "8:17", "uuid-two"
        )
        request = {
            "device": selected.device,
            "mountpoint": selected.mountpoint,
            "label": selected.label,
            "fstype": selected.fstype,
            "mounted": True,
            "majmin": selected.majmin,
            "uuid": selected.uuid,
        }
        with mock.patch.object(exporter, "discover_destinations", return_value=[selected]):
            self.assertEqual(exporter.validate_destination(request), selected)
        with mock.patch.object(exporter, "discover_destinations", return_value=[swapped]):
            with self.assertRaises(RuntimeError):
                exporter.validate_destination(request)

    def test_plain_and_structured_secrets_are_redacted(self):
        fake = "FAKESECRET-123456789"
        text = exporter.redact_text(
            f"password={fake}\nAuthorization: Bearer {fake}\n"
            f"url=https://login.tailscale.com/a/{fake}\ntskey-auth-{fake}\n"
            f'{{"api_key": "{fake}"}}\n--auth-key {fake}\n'
        )
        self.assertNotIn(fake, text)
        structured = exporter.redact_json({"AuthKey": fake, "Peer": {"DNSName": "host.ts.net"}})
        self.assertEqual(structured["AuthKey"], "[REDACTED]")
        self.assertEqual(structured["Peer"]["DNSName"], "host.ts.net")

    def test_fixture_archive_manifest_and_no_secret_leak(self):
        secret = "FAKESECRET-UNIQUE-999"
        with tempfile.TemporaryDirectory() as directory:
            archive = self.make_archive(pathlib.Path(directory), secret)
            with tarfile.open(archive, "r:gz") as container:
                combined = b"\n".join(
                    container.extractfile(member).read()
                    for member in container.getmembers()
                    if member.isfile()
                )
            self.assertNotIn(secret.encode(), combined)
            self.assertIn(b"[REDACTED]", combined)
            self.assertIn(b"MANIFEST", b"MANIFEST")

    def test_symlink_and_binary_files_are_not_embedded(self):
        secret = b"FAKESECRET-LINKED"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "secret"
            source.write_bytes(secret)
            link = root / "link"
            link.symlink_to(source)
            binary = root / "binary"
            binary.write_bytes(b"prefix\0" + secret)
            bundle = root / "bundle"
            exporter.add_file(bundle, "linked.txt", link)
            exporter.add_file(bundle, "binary.txt", binary)
            self.assertNotIn(secret, (bundle / "linked.txt").read_bytes())
            self.assertNotIn(secret, (bundle / "binary.txt").read_bytes())

    def test_atomic_copy_creates_archive_and_sidecar_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source_dir = root / "source"
            target = root / "target"
            source_dir.mkdir()
            target.mkdir()
            archive = self.make_archive(source_dir)
            final = exporter.atomic_export(archive, target, "support.tar.gz")
            self.assertEqual(
                sorted(item.name for item in target.iterdir()),
                ["support.tar.gz", "support.tar.gz.sha256"],
            )
            digest, name = (target / "support.tar.gz.sha256").read_text().split()
            self.assertEqual(name, final.name)
            self.assertEqual(digest, exporter.file_sha256(final))

    def test_failed_copy_cleans_partial_and_final_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source_dir = root / "source"
            target = root / "target"
            source_dir.mkdir()
            target.mkdir()
            archive = self.make_archive(source_dir)

            def fail_copy(incoming, outgoing, _size):
                outgoing.write(incoming.read(32))
                raise OSError("fixture failure")

            with mock.patch.object(exporter.shutil, "copyfileobj", side_effect=fail_copy):
                with self.assertRaises(OSError):
                    exporter.atomic_export(archive, target, "support.tar.gz")
            self.assertEqual(list(target.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
