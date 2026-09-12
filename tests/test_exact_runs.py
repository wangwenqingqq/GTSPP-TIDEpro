from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import random
import unittest

from reference.exact_runs import (ExactRunIndex, Record, Run, OutputOverflow,
                                  brute_force, fragmentation_blocks)


class ExactRunTests(unittest.TestCase):
    def test_exhaustive_small_fingerprints(self):
        rows = [Record(i, i) for i in range(64)]
        index = ExactRunIndex(6, rows)
        for q in range(1, 64):
            for t in (Fraction(1, 3), Fraction(7, 10), Fraction(4, 5), Fraction(1)):
                self.assertEqual(index.acquire().search(q, t), brute_force(rows, q, t))

    def test_rational_boundary_inclusive(self):
        index = ExactRunIndex(10, [Record(1, (1 << 7) - 1)])
        self.assertEqual(len(index.acquire().search((1 << 10) - 1, Fraction(7, 10))), 1)
        self.assertFalse(index.acquire().search((1 << 10) - 1, Fraction(7001, 10000)))

    def test_distinct_ids_with_identical_bits_are_preserved(self):
        i = ExactRunIndex(8, [Record(4, 3), Record(5, 3)])
        self.assertEqual([x.source_id for x in i.acquire().search(3, Fraction(1))], [4, 5])

    def test_old_epoch_stays_unchanged(self):
        index = ExactRunIndex(8, [Record(1, 1)])
        old = index.acquire()
        new = index.publish([Record(2, 3)])
        self.assertFalse(old.search(3, Fraction(1)))
        self.assertEqual(new.search(3, Fraction(1))[0].source_id, 2)
        self.assertEqual(old.version, 0)
        self.assertEqual(new.version, 1)

    def test_invalid_release_leaves_visible_epoch_unchanged(self):
        index = ExactRunIndex(8, [Record(1, 1)])
        old = index.acquire()
        with self.assertRaises(ValueError):
            index.publish([Record(2, 1 << 8)])
        self.assertIs(index.acquire(), old)

    def test_duplicate_release_id_is_rejected_atomically(self):
        index = ExactRunIndex(8, [Record(1, 1)])
        old = index.acquire()
        with self.assertRaises(ValueError):
            index.publish([Record(2, 3), Record(1, 3)])
        self.assertIs(index.acquire(), old)

    def test_duplicate_in_one_run_is_rejected(self):
        with self.assertRaises(ValueError):
            Run.build([Record(1, 1), Record(1, 2)], 8)

    def test_compaction_preserves_complete_results_and_old_owners(self):
        i = ExactRunIndex(8, [Record(1, 1)])
        old = i.publish([Record(2, 3), Record(3, 7)])
        before = old.search(7, Fraction(1, 3))
        new = i.compact()
        self.assertEqual(new.search(7, Fraction(1, 3)), before)
        self.assertEqual(old.search(7, Fraction(1, 3)), before)
        self.assertEqual(len(new.runs), 1)
        self.assertEqual(len(old.runs), 2)

    def test_complete_output_overflow_is_explicit(self):
        i = ExactRunIndex(8, [Record(1, 1), Record(2, 1)])
        with self.assertRaises(OutputOverflow):
            i.acquire().search(1, Fraction(1), max_hits=1)
        self.assertEqual(len(i.acquire().search(1, Fraction(1), max_hits=2)), 2)

    def test_empty_query_is_outside_contract(self):
        with self.assertRaises(ValueError):
            ExactRunIndex(8).acquire().search(0, Fraction(7, 10))

    def test_bad_threshold_is_rejected(self):
        for threshold in (0.7, Fraction(0), Fraction(2)):
            with self.assertRaises(ValueError):
                ExactRunIndex(8).acquire().search(1, threshold)

    def test_empty_base_and_release(self):
        i = ExactRunIndex(8)
        self.assertEqual(i.acquire().search(1, Fraction(1)), ())
        with self.assertRaises(ValueError):
            i.publish([])

    def test_bad_ids_and_width(self):
        for source_id in (-1, 2**64):
            with self.assertRaises(ValueError):
                Run.build([Record(source_id, 1)], 8)
        with self.assertRaises(ValueError):
            ExactRunIndex(0)

    def test_random_arrival_history_matches_independent_oracle(self):
        rng = random.Random(912)
        rows = [Record(i, rng.getrandbits(16)) for i in range(180)]
        i = ExactRunIndex(16, rows[:30])
        for stop in range(45, 181, 15):
            i.publish(rows[stop-15:stop])
            if stop % 45 == 0:
                i.compact()
            for _ in range(6):
                q = rng.randrange(1, 2**16)
                self.assertEqual(i.acquire().search(q, Fraction(2, 3)),
                                 brute_force(rows[:stop], q, Fraction(2, 3)))

    def test_locked_reference_concurrent_publishers_lose_no_rows(self):
        i = ExactRunIndex(8)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda j: i.publish([Record(j, 1)]), range(1, 17)))
        self.assertEqual(len(i.acquire().search(1, Fraction(1))), 16)
        self.assertEqual(i.acquire().version, 16)

    def test_fragmentation_preserves_candidate_set(self):
        rows = [Record(i, i) for i in range(256)]
        compact = Run.build(rows, 8)
        shards = [Run.build(rows[start::7], 8) for start in range(7)]
        for q in (1, 3, 15, 127, 255):
            for t in (Fraction(1, 2), Fraction(7, 10), Fraction(4, 5)):
                a = {r.source_id for r in compact.candidate_rows(q, t)}
                b = {r.source_id for s in shards for r in s.candidate_rows(q, t)}
                self.assertEqual(a, b)

    def test_fragmentation_block_arithmetic(self):
        rng = random.Random(1)
        for _ in range(100):
            counts = [rng.randrange(0, 1000) for _ in range(20)]
            fragmented, compacted = fragmentation_blocks(counts, 256)
            nonempty = sum(c > 0 for c in counts)
            self.assertGreaterEqual(fragmented, compacted)
            self.assertLessEqual(fragmented - compacted, max(nonempty - 1, 0))
        self.assertEqual(fragmentation_blocks([0, 0], 256), (0, 0))

    def test_invalid_fragmentation_input(self):
        with self.assertRaises(ValueError):
            fragmentation_blocks([1, -1], 256)
        with self.assertRaises(ValueError):
            fragmentation_blocks([1], 0)
