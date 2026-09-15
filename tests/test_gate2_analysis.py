import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from experiments.gate2.analyze import audit_timeline, verify_summary


class TimelineAudit(unittest.TestCase):
    def test_float_sum_compatibility_does_not_relax_tail_metrics(self):
        verify_summary({"mean_service_ms": .04866665800000466, "p99_response_ms": 1.},
                       {"mean_service_ms": .04866665800000487, "p99_response_ms": 1.})
        with self.assertRaisesRegex(ValueError, "p99_response_ms"):
            verify_summary({"mean_service_ms": 1., "p99_response_ms": 1.},
                           {"mean_service_ms": 1., "p99_response_ms": 1.00000000000001})
        with self.assertRaisesRegex(ValueError, "mean_service_ms"):
            verify_summary({"mean_service_ms": 1.}, {"mean_service_ms": 1.0000001})

    def fixture(self, root, mode="growth", owner=7999, exemption=0, seen=None):
        records = {
            "arena": [{"event": "alloc", "bytes": 256}],
            "maintenance": [{"shared_bytes": 0, "current_only_bytes": 256,
                             "reader_only_at_publish_bytes": 0, "other_held_at_publish_bytes": 0,
                             "live_at_publish_bytes": 512, "retired_only_bytes": 0,
                             "exclusive_actual_reclaim_ms": 0, "last_reader_device_done_ms": 0}],
            "requests": [{"epoch": 1}],
            "arrivals": [{"returned_ms": 8000}],
            "coverage": [{"epoch": 1, "retained_base_exemption": exemption,
                          "owner_released_ms": owner, "published_ms": 7900,
                          "exclusive_reclaimed_ms": 7999, "within_window": 1}],
        }
        for kind, rows in records.items():
            with (root/f"case.{kind}.csv").open("w") as f:
                w = csv.DictWriter(f, fieldnames=rows[0].keys())
                w.writeheader()
                w.writerows(rows)
        return {"mode": mode, "start_ms": 0, "window_ms": 8000,
                "seen_epochs": seen if seen is not None else [0, 1, 0, 0, 0, 0, 0]}

    def test_exact_completion_boundary_counted(self):
        with TemporaryDirectory() as path:
            root = Path(path)
            audit_timeline(root, "case", self.fixture(root))

    def test_claimed_reclaim_with_zero_timestamp_rejected(self):
        with TemporaryDirectory() as path:
            root = Path(path)
            with self.assertRaisesRegex(ValueError, "lifecycle coverage"):
                audit_timeline(root, "case", self.fixture(root, owner=0))

    def test_only_deliberate_shadow_base_can_remain_owned(self):
        with TemporaryDirectory() as path:
            root = Path(path)
            audit_timeline(root, "case", self.fixture(root, mode="shadow", owner=0, exemption=1))
            with self.assertRaisesRegex(ValueError, "exemption"):
                audit_timeline(root, "case", self.fixture(root, owner=0, exemption=1))

    def test_epoch_coverage_must_come_from_request_records(self):
        with TemporaryDirectory() as path:
            root = Path(path)
            with self.assertRaisesRegex(ValueError, "epoch coverage"):
                audit_timeline(root, "case", self.fixture(root, seen=[1]*7))


if __name__ == "__main__":
    unittest.main()
