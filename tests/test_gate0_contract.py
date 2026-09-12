"""Fast CPU checks for the new pilot, separate from the original 24 tests."""
import hashlib
import importlib.util
from pathlib import Path
import random
import unittest

ROOT = Path(__file__).resolve().parents[1]
HAS_NUMPY = importlib.util.find_spec("numpy") is not None
if HAS_NUMPY:
    import numpy as np
    from experiments.gate0.prepare_history import selection, verify_rows, choose_queries, SEED


class FrozenRuntimeTests(unittest.TestCase):
    def test_frozen_donor_runtime_hash(self):
        actual = hashlib.sha256((ROOT / "vendor/tide/frozen_query_runtime.cuh").read_bytes()).hexdigest()
        self.assertEqual(actual, "7ccf4416f08ec653f8d74c32562a4ee75b9ede251f953e3ec8619e8b63523302")

    def test_budget_accounts_for_maximum_pilot_coexistence(self):
        # Old full snapshot + newly inserted delta + new compacted snapshot,
        # with conservative 2 MiB allowance for the persistent query workspace.
        self.assertLess((1082990 * 2 + 80753) * 42 + (2 << 20), 256 << 20)


@unittest.skipUnless(HAS_NUMPY, "optional NumPy needed for input-preparation tests")
class PreparationTests(unittest.TestCase):
    def test_vectorized_sampling_matches_scalar_modular_arithmetic(self):
        mask = (1 << 64) - 1
        rng = random.Random(913)
        ids = [0, 1, (1 << 63) - 1, 1 << 63, mask] + [rng.getrandbits(64) for _ in range(1000)]
        expected = []
        for source_id in ids:
            value = ((source_id ^ SEED) + 0x9e3779b97f4a7c15) & mask
            value = ((value ^ (value >> 30)) * 0xbf58476d1ce4e5b9) & mask
            value = ((value ^ (value >> 27)) * 0x94d049bb133111eb) & mask
            value ^= value >> 31
            expected.append(value % 38 == 0)
        self.assertEqual(selection(np.array(ids, dtype=np.uint64), 38).tolist(), expected)

    def test_sampling_is_stable_across_release_boundaries(self):
        ids = np.arange(10000, dtype=np.uint64)
        whole = selection(ids, 38)
        chunks = np.concatenate([selection(chunk, 38) for chunk in np.array_split(ids, 7)])
        np.testing.assert_array_equal(whole, chunks)

    def test_invalid_popcount_and_duplicate_ids_rejected(self):
        rows = np.array([[1, 1, 0, 0, 0, 1], [2, 3, 0, 0, 0, 2]], dtype=np.uint64)
        verify_rows(rows)
        bad = rows.copy(); bad[1, 5] = 3
        with self.assertRaises(ValueError): verify_rows(bad)
        bad = rows.copy(); bad[1, 0] = 1
        with self.assertRaises(ValueError): verify_rows(bad)

    def test_unsorted_popcounts_rejected(self):
        rows = np.array([[1, 3, 0, 0, 0, 2], [2, 1, 0, 0, 0, 1]], dtype=np.uint64)
        with self.assertRaises(ValueError): verify_rows(rows)

    def test_queries_have_fixed_cohorts_and_exclude_empty(self):
        runs = []
        for epoch in range(7):
            rows = np.zeros((32, 6), dtype=np.uint64)
            rows[:, 0] = np.arange(32) + epoch * 100
            rows[1:, 1] = 1; rows[1:, 5] = 1
            runs.append(rows)
        queries, labels = choose_queries(runs)
        self.assertEqual(len(queries), 32)
        self.assertTrue(np.all(queries[:, 5] > 0))
        self.assertEqual([sum(x["arrival_epoch"] == i for x in labels) for i in range(7)], [16, 2, 2, 2, 2, 2, 6])


if __name__ == "__main__":
    unittest.main()
