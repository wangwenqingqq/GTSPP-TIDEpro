"""New CPU semantic reference; not the unavailable historical reference package.

No performance or GPU-capacity claims. Run with Python >=3.10 --self-test.
"""
import argparse
import collections
import hashlib
import json
import random
import time

MASK64 = (1 << 64) - 1


def ceil_div(num, den):
    if num < 0 or den <= 0 or num + den - 1 > MASK64:
        raise ValueError('invalid or overflowing integer division')
    return (num + den - 1) // den


def threshold(m, n):
    if not (isinstance(m, int) and isinstance(n, int) and 0 < m <= n <= (1 << 31) - 1):
        raise ValueError('invalid rational threshold')


def checked_size(count, stride, cap=MASK64):
    if count < 0 or stride < 0 or count * stride > cap:
        raise ValueError('capacity overflow')
    return count * stride


def oracle(rows, q, D, m, n):
    threshold(m, n)
    if not 0 < q < (1 << D):
        raise ValueError('query must be nonzero and fit width')
    result = []
    for rid, x in rows:
        c, u = (q & x).bit_count(), (q | x).bit_count()
        if n * c >= m * u:
            result.append((rid, c, u))
    return sorted(result)


class Index:
    def __init__(self, rows, D):
        if D not in (8, 256, 2048):
            raise ValueError('unsupported width')
        if len({rid for rid, _ in rows}) != len(rows):
            raise ValueError('duplicate stable ID')
        if any(not 0 <= rid <= MASK64 or not 0 <= x < (1 << D) for rid, x in rows):
            raise ValueError('record outside contract')
        self.D, self.buckets = D, {}
        for rid, x in sorted(rows, key=lambda r: (r[1].bit_count(), r[0])):
            self.buckets.setdefault(x.bit_count(), []).append((rid, x))
        self.postings, self.tiles = {}, {}
        for b, bucket in self.buckets.items():
            checked_size(len(bucket), 1, (1 << 32) - 1)
            posts = [[] for _ in range(D)]
            for i, (_, x) in enumerate(bucket):
                while x:
                    j = (x & -x).bit_length() - 1
                    posts[j].append(i)
                    x &= x - 1
            self.postings[b] = posts
            tiles = [[0] * ((len(bucket) + 63) // 64) for _ in range(D)]
            for j, post in enumerate(posts):
                for i in post:
                    tiles[j][i // 64] |= 1 << (i % 64)
            self.tiles[b] = tiles

    def prefix_survivors(self, b, q, e, h, method):
        bucket, posts = self.buckets[b], self.postings[b]
        order = sorted((j for j in range(self.D) if (q >> j) & 1), key=lambda j: (len(posts[j]), j))
        L = min(len(order), e + h)
        t = L - e
        assert 1 <= t <= L
        prefix = order[:L]
        if method == 'P':
            # CPU diagnostic merge/RLE of uint32 row-ID postings.
            merged = sorted(i for j in prefix for i in posts[j])
            counts = collections.Counter(merged)
            return {i for i, count in counts.items() if count >= t}
        survivors = set()
        for tile in range((len(bucket) + 63) // 64):
            valid = (1 << min(64, len(bucket) - tile * 64)) - 1
            if t == 1:
                keep = 0
                for j in prefix:
                    keep |= self.tiles[b][j][tile]
            else:
                planes = [0] * L.bit_length()
                for j in prefix:
                    carry = self.tiles[b][j][tile]
                    for k in range(len(planes)):
                        carry, planes[k] = planes[k] & carry, planes[k] ^ carry
                greater, equal = 0, valid
                for k in reversed(range(len(planes))):
                    if (t >> k) & 1:
                        equal &= planes[k]
                    else:
                        greater |= equal & planes[k]
                        equal &= ~planes[k]
                keep = (greater | equal) & valid
            keep &= valid
            while keep:
                j = (keep & -keep).bit_length() - 1
                survivors.add(tile * 64 + j)
                keep &= keep - 1
        return survivors

    def search(self, q, m, n, method, config=None):
        threshold(m, n)
        if not 0 < q < (1 << self.D):
            raise ValueError('query must be nonzero and fit width')
        a, output, survivors = q.bit_count(), [], set()
        lo, hi = ceil_div(m * a, n), min(self.D, n * a // m)
        for b, bucket in self.buckets.items():
            if not lo <= b <= hi:
                continue
            required = ceil_div(m * (a + b), m + n)
            if method in ('B', 'P'):
                indices = self.prefix_survivors(b, q, a - required, config, method)
            else:
                indices = range(len(bucket))
            for i in indices:
                rid, x = bucket[i]
                if method == 'R2':
                    g = config
                    w = self.D // g
                    mask = (1 << w) - 1
                    upper = sum(min(((q >> j) & mask).bit_count(), ((x >> j) & mask).bit_count())
                                for j in range(0, self.D, w))
                    if upper < required:
                        continue
                if method == 'R1':
                    order = list(range(0, self.D, 64))
                    if config == 'descending':
                        order.sort(key=lambda j: (-((q >> j) & MASK64).bit_count(), j))
                    c = sa = sb = 0
                    for j in order:
                        qw, xw = (q >> j) & MASK64, (x >> j) & MASK64
                        c += (qw & xw).bit_count()
                        sa += qw.bit_count()
                        sb += xw.bit_count()
                        if c + min(a - sa, b - sb) < required:
                            break
                    else:
                        if n * c >= m * (a + b - c):
                            output.append((rid, c, a + b - c))
                    continue
                survivors.add(rid)
                c = (q & x).bit_count()
                if n * c >= m * (a + b - c):
                    output.append((rid, c, a + b - c))
        return sorted(output), survivors


CONFIGS = [('R0', None), ('R1', 'natural'), ('R1', 'descending'),
           ('R2', 4), ('R2', 8), ('B', 1), ('B', 8), ('P', 1), ('P', 8)]


def check_case(rows, D, queries, thresholds):
    index, comparisons = Index(rows, D), 0
    for q in queries:
        for m, n in thresholds:
            expected = oracle(rows, q, D, m, n)
            seen = {}
            for method, config in CONFIGS:
                output, survivors = index.search(q, m, n, method, config)
                assert output == expected, (D, q, m, n, method, config)
                assert len({r[0] for r in output}) == len(output)
                if method in ('B', 'P'):
                    seen[method, config] = survivors
                    assert {r[0] for r in expected} <= survivors
                comparisons += 1
            assert seen['B', 1] == seen['P', 1]
            assert seen['B', 8] == seen['P', 8]
    return comparisons


def self_test():
    start = time.perf_counter()
    comparisons = check_case(list(enumerate(range(256))), 8, range(1, 256), [(1, 2), (7, 10), (4, 5), (1, 1)])
    rng = random.Random(20260921)
    for D in (256, 2048):
        for size in (0, 1, 63, 64, 65, 129):
            full = (1 << D) - 1
            xs = [0, full, full, 1] + [rng.getrandbits(D) for _ in range(max(0, size - 4))]
            rows = [(i + 1000, x) for i, x in enumerate(xs[:size])]
            comparisons += check_case(rows, D, [1, full, rng.getrandbits(D)], [(1, 2), (7, 10), (4, 5), (1, 1)])
        # Dense equal-popcount bucket exercises tail masks and t>1 planes.
        rows = [(i, sum(1 << j for j in rng.sample(range(D), 80))) for i in range(129)]
        comparisons += check_case(rows, D, [rows[0][1], rows[64][1], (1 << 80) - 1], [(7, 10), (4, 5)])
    # Exactly 7/10 and one intersection bit less, including duplicate bitstrings.
    comparisons += check_case([(1, 127), (2, 63 | (1 << 10)), (3, 127)], 256, [1023], [(7, 10), (4, 5)])
    for m, n in ((0, 1), (2, 1), (1, 0), (1, 1 << 31)):
        try: threshold(m, n)
        except ValueError: pass
        else: raise AssertionError('threshold accepted')
    for fn in (lambda: Index([(1, 1), (1, 2)], 256),
               lambda: Index([], 256).search(0, 7, 10, 'R0'),
               lambda: checked_size(1 << 32, 1, (1 << 32) - 1),
               lambda: checked_size(1 << 63, 16)):
        try: fn()
        except ValueError: pass
        else: raise AssertionError('invalid contract accepted')
    # Python arbitrary precision is an oracle; native uint64 promotion is a separate gate.
    assert ceil_div(((1 << 31) - 1) * 4096, (1 << 31)) == 4096
    return {'status': 'PASS_REFERENCE_ONLY', 'small_universe_pairs': 255 * 256 * 4,
            'method_query_comparisons': comparisons, 'D': [8, 256, 2048],
            'elapsed_s': time.perf_counter() - start,
            'native_uint64_capacity_sanitizer': 'NOT_COVERED',
            'source_sha256': hashlib.sha256(open(__file__, 'rb').read()).hexdigest()}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--self-test', action='store_true', required=True)
    p.parse_args()
    print(json.dumps(self_test(), indent=2))
