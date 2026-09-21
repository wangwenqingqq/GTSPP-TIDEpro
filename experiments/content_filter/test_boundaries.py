"""Adversarial CPU bitmap padding, prefix truncation, and parameter boundaries."""
import json
import random
from reference_semantics import Index, oracle


def main():
    rng = random.Random(20260921)
    checks = 0
    for D in (256, 2048):
        for count in (1, 63, 64, 65, 129):
            rows = [(i, sum(1 << j for j in rng.sample(range(D), 80))) for i in range(count)]
            index = Index(rows, D)
            remainder = count % 64
            if remainder:
                invalid = ((1 << 64) - 1) ^ ((1 << remainder) - 1)
                # Poison every invalid padding bit. Correct masks must hide them.
                for column in index.tiles[80]:
                    column[-1] |= invalid
            for q in (rows[0][1], (1 << 80) - 1, 1):
                for m,n in ((7,10),(4,5),(1,1)):
                    expected = oracle(rows,q,D,m,n)
                    for h in (1,8):
                        bp,bs = index.search(q,m,n,'B',h)
                        pp,ps = index.search(q,m,n,'P',h)
                        assert bp == pp == expected
                        assert bs == ps and all(0 <= i < count for i in bs)
                        checks += 1
        # a=1, h=8 forces L to a and t=1, not 8.
        index = Index([(10,1),(11,1),(12,2),(13,0)], D)
        for method in ('B','P'):
            assert index.search(1,1,1,method,8)[0] == [(10,1,1),(11,1,1)]
            checks += 1
    print(json.dumps({'status':'PASS_CPU_REFERENCE_BOUNDARIES','checks':checks,
                      'poisoned_invalid_tail_bits':True,'native_GPU_capacity':'NOT_COVERED'}))


if __name__ == '__main__':
    main()
