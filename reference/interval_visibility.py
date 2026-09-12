"""Minimal mathematical regression fixtures, not a reproduction of CUDA code."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class Interval:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lower) and math.isfinite(self.upper)
                and 0 <= self.lower <= self.upper):
            raise ValueError("interval endpoints must be finite, ordered, and nonnegative")

    def lower_bound(self, query_pivot_distance: float) -> float:
        if not math.isfinite(query_pivot_distance) or query_pivot_distance < 0:
            raise ValueError("pivot distance must be finite and nonnegative")
        return max(0.0, self.lower - query_pivot_distance, query_pivot_distance - self.upper)


def path_certifies(distances: tuple[float, ...], intervals: tuple[Interval, ...],
                   margin: float = 0.0) -> bool:
    """Check EVERY existing ancestor interval; uncertain boundary goes to delta.

    Margin is a conservative toy guard, not a proof for floating-point kernels.
    """
    if len(distances) != len(intervals) or not intervals:
        raise ValueError("a nonempty path with one interval per distance is required")
    if not math.isfinite(margin) or margin < 0:
        raise ValueError("margin must be finite and nonnegative")
    return all(math.isfinite(d) and i.lower + margin < d < i.upper - margin
               for d, i in zip(distances, intervals))


def stale_ancestor_counterexample() -> dict[str, float | bool]:
    # Real line, d(x,y)=|x-y|. Native subtree is [0,1] about pivot 0.
    # A leaf-local insertion of x=2 cannot make the stale ancestor safe.
    old_ancestor = Interval(0.0, 1.0)
    x = query = 2.0
    radius = 0.1
    lb = old_ancestor.lower_bound(abs(query))
    return {"ancestor_lower_bound": lb, "query_radius": radius,
            "true_distance_to_insert": abs(query - x),
            "stale_ancestor_prunes": lb > radius,
            "new_object_is_a_hit": abs(query - x) <= radius}
