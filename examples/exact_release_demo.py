"""Synthetic bitset demonstration; not a real chemistry application experiment."""
from fractions import Fraction
from reference.exact_runs import ExactRunIndex, Record
from reference.interval_visibility import stale_ancestor_counterexample


def main() -> None:
    index = ExactRunIndex(8, [Record(10, 0b00001111), Record(20, 0b11110000)])
    old_epoch = index.acquire()
    new_epoch = index.publish([Record(30, 0b00000111)])
    query, threshold = 0b00000111, Fraction(1)
    print('old epoch:', old_epoch.version, old_epoch.search(query, threshold))
    print('new epoch:', new_epoch.version, new_epoch.search(query, threshold))
    compacted = index.compact()
    print('compacted:', compacted.version, compacted.search(query, threshold))
    print('stale-ancestor mathematical fixture:', stale_ancestor_counterexample())


if __name__ == '__main__':
    main()
