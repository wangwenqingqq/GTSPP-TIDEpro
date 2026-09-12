import unittest
from reference.interval_visibility import Interval, path_certifies, stale_ancestor_counterexample


class VisibilityTests(unittest.TestCase):
    def test_stale_ancestor_loses_a_true_range_hit(self):
        result = stale_ancestor_counterexample()
        self.assertTrue(result['stale_ancestor_prunes'])
        self.assertTrue(result['new_object_is_a_hit'])
        self.assertEqual(result['true_distance_to_insert'], 0.0)

    def test_every_ancestor_must_certify(self):
        self.assertFalse(path_certifies((2.0, 0.5), (Interval(0, 1), Interval(0, 1))))
        self.assertTrue(path_certifies((0.5, 0.5), (Interval(0, 1), Interval(0, 1))))

    def test_boundary_is_reserved_for_fallback(self):
        self.assertFalse(path_certifies((1.0,), (Interval(0, 1),)))
        self.assertFalse(path_certifies((0.99,), (Interval(0, 1),), margin=0.02))

    def test_invalid_interval_or_path(self):
        with self.assertRaises(ValueError):
            Interval(2, 1)
        with self.assertRaises(ValueError):
            path_certifies((), ())
        self.assertFalse(path_certifies((float('nan'),), (Interval(0, 1),)))

    def test_valid_interval_bound_is_not_greater_than_true_distance(self):
        interval = Interval(1, 3)
        for x in (1.0, 1.5, 2.0, 2.5, 3.0):
            for q in (-4.0, -2.0, 0.0, 2.0, 4.0):
                self.assertLessEqual(interval.lower_bound(abs(q)), abs(q - x))

    def test_multiplying_a_valid_bound_can_create_a_false_prune(self):
        # x=1, pivot=0, q=0: exact LB=1 and true distance=1.
        lb = Interval(1, 1).lower_bound(0)
        radius = 1.1
        self.assertLessEqual(lb, radius)
        self.assertGreater(1.3 * lb, radius)
