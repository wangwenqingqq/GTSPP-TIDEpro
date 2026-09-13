import unittest

import numpy as np

from experiments.gate1.prepare import queries


class Gate1QueryTests(unittest.TestCase):
    @staticmethod
    def runs():
        runs = []
        for epoch in range(7):
            run = np.zeros((80, 6), dtype="<u8")
            run[:, 0] = np.arange(80) + epoch * 1000
            run[:, 1] = 1
            run[:, 5] = 1
            runs.append(run)
        return runs

    def test_cohorts_and_unique_query_ids(self):
        result, labels = queries(self.runs())
        self.assertEqual(result.shape, (64, 6))
        self.assertEqual(len(np.unique(result[:, 0])), 64)
        counts = [sum(x["arrival_epoch"] == e for x in labels) for e in range(7)]
        self.assertEqual(counts, [32, 4, 4, 4, 4, 4, 12])

    def test_empty_queries_excluded(self):
        runs = self.runs()
        for run in runs:
            run[0, 5] = 0
        result, _ = queries(runs)
        self.assertTrue(np.all(result[:, 5] > 0))

    def test_insufficient_nonempty_cohort_rejected(self):
        runs = self.runs()
        runs[0][:, 5] = 0
        with self.assertRaisesRegex(ValueError, "not enough"):
            queries(runs)

    def test_duplicate_query_ids_rejected(self):
        runs = self.runs()
        for run in runs:
            run[:, 0] = 1
        with self.assertRaisesRegex(ValueError, "uniqueness"):
            queries(runs)


if __name__ == "__main__":
    unittest.main()
