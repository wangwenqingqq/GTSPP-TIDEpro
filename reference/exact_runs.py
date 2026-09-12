"""Exact insert-only binary-fingerprint reference with immutable snapshots.

This CPU reference illustrates established bounded-run search and version ownership.
It is NOT a new indexing algorithm, a GPU implementation, or a performance baseline.
An epoch is acquired once per request and stays reachable for the entire request.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from fractions import Fraction
from threading import RLock
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Record:
    source_id: int
    fingerprint: int


@dataclass(frozen=True, slots=True, order=True)
class Hit:
    source_id: int
    intersection: int
    union: int


class OutputOverflow(RuntimeError):
    """The complete result does not fit; no truncated result is returned."""


def _check_width(width: int) -> None:
    if isinstance(width, bool) or not isinstance(width, int) or width <= 0:
        raise ValueError("width must be a positive integer")


def _check_fingerprint(fp: int, width: int, *, nonzero: bool = False) -> None:
    if isinstance(fp, bool) or not isinstance(fp, int) or fp < 0 or fp.bit_length() > width:
        raise ValueError("fingerprint must be a nonnegative integer fitting the width")
    if nonzero and fp == 0:
        raise ValueError("this reference explicitly excludes the empty query")


@dataclass(frozen=True, slots=True)
class Run:
    width: int
    rows: tuple[Record, ...]
    counts: tuple[int, ...]

    @classmethod
    def build(cls, records: Iterable[Record], width: int) -> Run:
        _check_width(width)
        rows = tuple(records)
        ids: set[int] = set()
        for row in rows:
            if not isinstance(row, Record):
                raise TypeError("all inputs must be Record instances")
            if (isinstance(row.source_id, bool) or not isinstance(row.source_id, int)
                    or not 0 <= row.source_id < 2**64):
                raise ValueError("source_id must be a uint64 integer")
            _check_fingerprint(row.fingerprint, width)
            if row.source_id in ids:
                raise ValueError("duplicate source_id within the release")
            ids.add(row.source_id)
        ordered = tuple(sorted(rows, key=lambda r: (r.fingerprint.bit_count(), r.source_id)))
        return cls(width, ordered, tuple(r.fingerprint.bit_count() for r in ordered))

    def candidate_rows(self, query: int, threshold: Fraction) -> tuple[Record, ...]:
        _check_fingerprint(query, self.width, nonzero=True)
        if not isinstance(threshold, Fraction) or not 0 < threshold <= 1:
            raise ValueError("threshold must be Fraction in (0, 1]")
        a = query.bit_count()
        m, n = threshold.numerator, threshold.denominator
        lower = (m * a + n - 1) // n
        upper = min(self.width, (n * a) // m)
        return self.rows[bisect_left(self.counts, lower):bisect_right(self.counts, upper)]


@dataclass(frozen=True, slots=True)
class Epoch:
    version: int
    width: int
    runs: tuple[Run, ...]

    def search(self, query: int, threshold: Fraction, *, max_hits: int | None = None) -> tuple[Hit, ...]:
        _check_fingerprint(query, self.width, nonzero=True)
        if not isinstance(threshold, Fraction) or not 0 < threshold <= 1:
            raise ValueError("threshold must be Fraction in (0, 1]")
        if max_hits is not None and (isinstance(max_hits, bool)
                                    or not isinstance(max_hits, int) or max_hits < 0):
            raise ValueError("max_hits must be a nonnegative integer or None")
        m, n = threshold.numerator, threshold.denominator
        hits: list[Hit] = []
        for run in self.runs:
            for row in run.candidate_rows(query, threshold):
                intersection = (query & row.fingerprint).bit_count()
                union = (query | row.fingerprint).bit_count()
                if n * intersection >= m * union:
                    hits.append(Hit(row.source_id, intersection, union))
                    if max_hits is not None and len(hits) > max_hits:
                        raise OutputOverflow("complete result exceeds max_hits")
        return tuple(sorted(hits))


class ExactRunIndex:
    """Small lock-based CPU reference. No deletion, durability, or lock-free claims."""

    def __init__(self, width: int, base: Iterable[Record] = ()) -> None:
        self._lock = RLock()
        initial = Run.build(base, width)
        self._epoch = Epoch(0, width, (initial,))
        self._ids = {row.source_id for row in initial.rows}

    def acquire(self) -> Epoch:
        with self._lock:
            return self._epoch

    def publish(self, records: Iterable[Record]) -> Epoch:
        # Construction/validation happens before publication. A failed build leaves
        # the visible state untouched. This models no host-to-device transfer.
        candidate = Run.build(records, self._epoch.width)
        new_ids = {row.source_id for row in candidate.rows}
        if not new_ids:
            raise ValueError("empty releases are rejected by this reference")
        with self._lock:
            if self._ids.intersection(new_ids):
                raise ValueError("source_id already exists in the visible collection")
            new_epoch = Epoch(self._epoch.version + 1, self._epoch.width,
                              self._epoch.runs + (candidate,))
            # Allocate the new ID set before changing either published field.
            merged_ids = self._ids.union(new_ids)
            self._ids = merged_ids
            self._epoch = new_epoch
            return new_epoch

    def compact(self) -> Epoch:
        with self._lock:
            current = self._epoch
            merged = Run.build((row for run in current.runs for row in run.rows), current.width)
            self._epoch = Epoch(current.version + 1, current.width, (merged,))
            return self._epoch


def brute_force(records: Iterable[Record], query: int, threshold: Fraction) -> tuple[Hit, ...]:
    """Independent verifier: no population-count bound, rational score comparison."""
    if query <= 0 or not isinstance(threshold, Fraction) or not 0 < threshold <= 1:
        raise ValueError("nonempty query and Fraction threshold in (0, 1] required")
    result: list[Hit] = []
    for row in records:
        intersection = (row.fingerprint & query).bit_count()
        union = (row.fingerprint | query).bit_count()
        if Fraction(intersection, union) >= threshold:
            result.append(Hit(row.source_id, intersection, union))
    return tuple(sorted(result))


def fragmentation_blocks(candidate_counts: Iterable[int], block_size: int) -> tuple[int, int]:
    """Return fragmented/compacted block counts; established layout arithmetic.

    This is NOT a timing model. It excludes descriptor routing, bandwidth,
    synchronization, result transfer, occupancy, and concurrent maintenance.
    """
    counts = tuple(candidate_counts)
    if isinstance(block_size, bool) or not isinstance(block_size, int) or block_size <= 0:
        raise ValueError("block_size must be positive")
    if any(isinstance(c, bool) or not isinstance(c, int) or c < 0 for c in counts):
        raise ValueError("candidate counts must be nonnegative integers")
    fragmented = sum((c + block_size - 1) // block_size for c in counts)
    compacted = (sum(counts) + block_size - 1) // block_size
    return fragmented, compacted
