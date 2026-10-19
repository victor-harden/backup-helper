import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backup


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.source = base / "data"
        self.dest = base / "backups"
        (self.source / "sub").mkdir(parents=True)
        (self.source / "a.txt").write_text("alpha")
        (self.source / "sub" / "b.txt").write_text("beta")
        self.base = base

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_writes_archive_and_manifest(self):
        archive = backup.create_backup(self.source, self.dest, "data")
        self.assertTrue(archive.exists())
        manifest = archive.with_name(archive.name.replace(".tar.gz", ".manifest.json"))
        self.assertTrue(manifest.exists())
        data = json.loads(manifest.read_text())
        self.assertEqual(len(data), 2)

    def test_verify_ok(self):
        archive = backup.create_backup(self.source, self.dest, "data")
        result = backup.verify_backup(archive)
        self.assertTrue(result["ok"])
        self.assertEqual(result["files"], 2)

    def test_verify_detects_change(self):
        archive = backup.create_backup(self.source, self.dest, "data")
        # tamper with the manifest to simulate a mismatch
        manifest = archive.with_name(archive.name.replace(".tar.gz", ".manifest.json"))
        data = json.loads(manifest.read_text())
        key = next(iter(data))
        data[key] = "0" * 64
        manifest.write_text(json.dumps(data))
        result = backup.verify_backup(archive)
        self.assertFalse(result["ok"])
        self.assertTrue(result["changed"])

    def test_rotate_keeps_newest(self):
        for _ in range(3):
            backup.create_backup(self.source, self.dest, "data")
            for p in list(self.dest.glob("*.tar.gz")) + list(self.dest.glob("*.manifest.json")):
                p.touch()
        removed = backup.rotate(self.dest, keep=1)
        self.assertGreaterEqual(len(removed), 1)
        self.assertEqual(len(list(self.dest.glob("*.tar.gz"))), 1)

    def test_rotate_rejects_zero(self):
        with self.assertRaises(ValueError):
            backup.rotate(self.dest, keep=0)

    def test_create_rejects_missing_source(self):
        with self.assertRaises(ValueError):
            backup.create_backup(self.base / "nope", self.dest, "x")

    def test_list_backups(self):
        backup.create_backup(self.source, self.dest, "data")
        rows = backup.list_backups(self.dest)
        self.assertEqual(len(rows), 1)
        self.assertIn("bytes", rows[0])


if __name__ == "__main__":
    unittest.main()
