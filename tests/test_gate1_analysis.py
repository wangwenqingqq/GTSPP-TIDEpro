import tempfile
import unittest
from pathlib import Path

from experiments.gate1.analyze import audit_arena, gm, interval, quantile, write_gzip_csv


class Gate1AnalysisTests(unittest.TestCase):
    def test_process_unit_and_identity(self):
        self.assertEqual(interval([1, 1, 1, 1])["process_log_t95"], [1, 1])
        with self.assertRaisesRegex(ValueError, "four"):
            interval([1, 1, 1])

    def test_geomean_and_quantile(self):
        self.assertAlmostEqual(gm([.5, 2]), 1)
        self.assertEqual(quantile([1, 2, 3, 4], .5), 2.5)
        with self.assertRaises(ValueError):
            gm([0])

    def test_ledger_coexistence_and_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "arena.csv"
            path.write_text("time_ms,event,offset,bytes,live_bytes\n"
                            "0,alloc,0,256,256\n1,alloc,256,512,768\n"
                            "2,refuse,128,256,768\n3,release,0,256,512\n"
                            "4,alloc,0,256,768\n5,release,256,512,256\n6,release,0,256,0\n")
            self.assertEqual(audit_arena(path), 768)

    def test_ledger_overlap_and_leak_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "arena.csv"
            path.write_text("time_ms,event,offset,bytes,live_bytes\n0,alloc,0,512,512\n1,alloc,256,256,768\n")
            with self.assertRaisesRegex(ValueError, "overlapping"):
                audit_arena(path)
            path.write_text("time_ms,event,offset,bytes,live_bytes\n0,alloc,0,512,512\n")
            with self.assertRaisesRegex(ValueError, "leak"):
                audit_arena(path)

    def test_compressed_csv_is_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "one.gz", Path(tmp) / "two.gz"
            rows = [{"first": 1, "second": "test"}]
            write_gzip_csv(a, rows)
            write_gzip_csv(b, rows)
            self.assertEqual(a.read_bytes(), b.read_bytes())


if __name__ == "__main__":
    unittest.main()
