"""CPU-only immutable input intake and split preparation; never executes a query.

Source locations are explicit host-local JSON, not repository constants.
Outputs refuse replacement. Peak RSS and attempts are retained.
"""
import argparse
import hashlib
import heapq
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from experiments.gate0.prepare_history import digest, source_record


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def event(out, state, **extra):
    obj = dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), state=state, **extra)
    with (out / 'attempts.jsonl').open('a') as f:
        f.write(json.dumps(obj) + '\n')
    print(json.dumps(obj), flush=True)


def known_queries(config, D):
    ids, bits, records = set(), set(), []
    for pstr in config['old_queries']:
        p = Path(pstr)
        width = D // 64 + 2
        if p.stat().st_size % (8 * width):
            raise ValueError('invalid old query shape: ' + pstr)
        rows = np.fromfile(p, dtype='<u8').reshape(-1, width)
        for row in rows:
            ids.add(int(row[0]))
            bits.add(row[1:-1].tobytes())
        records.append({'path': pstr, 'rows': len(rows), 'sha256': digest(p)})
    return ids, bits, records


def pick_database(ids, ns, out):
    prefix = ('20260921|' + ns + '|').encode('ascii')
    heap = []
    for row, raw_id in enumerate(ids):
        rid = int(raw_id)
        key = int.from_bytes(hashlib.sha256(prefix + str(rid).encode('ascii')).digest(), 'big')
        item = (-key, -rid, row)
        if len(heap) < 1_000_000:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)
        if row and row % 5_000_000 == 0:
            event(out, 'DATABASE_SAMPLING', namespace=ns, rows=row)
    return np.array([v[2] for v in sorted(heap, reverse=True)], dtype=np.int64)


def pick_queries(ids, fp, db_ids, old_ids, old_bits, ns, out):
    prefix = ('20260922|' + ns + '|').encode('ascii')
    heap, active = [], {}
    for start in range(0, len(ids), 500_000):
        end = min(start + 500_000, len(ids))
        outside = ~np.isin(ids[start:end], db_ids, assume_unique=True)
        for offset in np.flatnonzero(outside):
            row = start + int(offset)
            rid = int(ids[row])
            if rid in old_ids:
                continue
            key = int.from_bytes(hashlib.sha256(prefix + str(rid).encode('ascii')).digest(), 'big')
            while heap and active.get(heap[0][2]) != heap[0]:
                heapq.heappop(heap)
            if len(active) == 896 and (-key, -rid) <= heap[0][:2]:
                continue
            bits = fp[row].tobytes()
            if not any(bits) or bits in old_bits:
                continue
            item = (-key, -rid, bits, row)
            prev = active.get(bits)
            if prev is not None and item[:2] <= prev[:2]:
                continue
            active[bits] = item
            heapq.heappush(heap, item)
            if len(active) > 896:
                while active.get(heap[0][2]) != heap[0]:
                    heapq.heappop(heap)
                removed = heapq.heappop(heap)
                del active[removed[2]]
            if len(heap) > 4096:
                heap = list(active.values())
                heapq.heapify(heap)
        event(out, 'QUERY_SAMPLING', namespace=ns, rows=end)
    if len(active) != 896:
        raise ValueError('not enough eligible distinct query bitstrings')
    return np.array([v[3] for v in sorted(active.values(), reverse=True)], dtype=np.int64)


def write_rows(out, name, ids, fp, order):
    # Original selection order is preserved. Later execution layout is separate.
    dest = out / name
    dest.mkdir()
    for filename, values in (('ids.u64', ids[order]), ('fp.u64', fp[order])):
        with (dest / filename).open('xb') as f:
            values.astype('<u8', copy=False).tofile(f)
    return {'rows': len(order), 'ids_sha256': digest(dest / 'ids.u64'),
            'fp_sha256': digest(dest / 'fp.u64'), 'relative_path': name}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sources', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    out, started = a.output, time.perf_counter()
    resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
    config = json.loads(a.sources.read_text())
    save(out / 'EXECUTION_FROZEN.json', {
        'source_sha256': digest(Path(__file__)),
        'addendum_sha256': digest(HERE / 'EXECUTION_ADDENDUM.md'),
        'protocol_sha256': digest(HERE / 'PROTOCOL_zh.md'),
        'source_config_sha256': digest(a.sources), 'python': sys.version,
        'numpy': np.__version__, 'host': platform.node(), 'pid': os.getpid(),
        'threads': 1, 'cpu_as_cap_bytes': 8 << 30, 'gpu': 'NOT_USED',
        'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    try:
        identity = []
        for lane in config['lanes']:
            records = []
            for item in lane['sources']:
                path = Path(item['path'])
                record = source_record(path, path.parent)
                if record['sha256'] != item['sha256']:
                    raise ValueError('canonical hash mismatch: ' + str(path))
                record['role'] = item['role']
                records.append(record)
                event(out, 'SOURCE_HASH_PASS', lane=lane['name'], role=item['role'])
            identity.append({'lane': lane['name'], 'D': lane['D'], 'rows': lane['rows'], 'files': records})
        save(out / 'SOURCE_IDENTITY.json', identity)
        event(out, 'CANONICAL_IDENTITIES_VERIFIED')
        from reference_semantics import self_test
        test = self_test()
        save(out / 'REFERENCE_A0.json', test)
        event(out, 'REFERENCE_A0_PASS', comparisons=test['method_query_comparisons'])
        manifest = {'protocol_id': 'tide_content_filter_v1_20260921',
                    'exposure': 'PRIOR_EXPOSURE_UNKNOWN', 'lanes': []}
        for lane in config['lanes']:
            N, D, ns = lane['rows'], lane['D'], lane['name']
            idir, fdir = Path(lane['ids']), Path(lane['fp'])
            if idir.stat().st_size != N * 8 or fdir.stat().st_size != N * D // 8:
                raise ValueError('canonical shape mismatch')
            signed = np.memmap(idir, mode='r', dtype='<i8')
            if np.any(signed < 0) or len(np.unique(signed)) != N:
                raise ValueError('nonunique or negative ID')
            del signed
            ids = np.memmap(idir, mode='r', dtype='<u8')
            fp = np.memmap(fdir, mode='r', dtype='<u8', shape=(N, D // 64))
            db = pick_database(ids, ns, out)
            old_ids, old_bits, old_records = known_queries(lane, D)
            q = pick_queries(ids, fp, ids[db], old_ids, old_bits, ns, out)
            assert not np.intersect1d(ids[db], ids[q]).size
            assert len({fp[i].tobytes() for i in q}) == 896
            artifacts = {}
            for name, order in [('database_1m', db), ('database_100k', db[:100_000]),
                                ('dev', q[:128]), ('a_screen', q[128:384]), ('sealed_b_final', q[384:])]:
                artifacts[name] = write_rows(out, ns + '_' + name, ids, fp, order)
            manifest['lanes'].append({'name': ns, 'N_canonical': N, 'D': D,
                'old_query_files': old_records, 'old_unique_ids': len(old_ids),
                'old_unique_bitstrings': len(old_bits), 'artifacts': artifacts})
            event(out, 'LANE_INPUT_FROZEN', lane=ns)
            del ids, fp, db, q
        manifest['elapsed_s'] = time.perf_counter() - started
        manifest['max_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        if manifest['max_rss_bytes'] > 8 << 30:
            raise ValueError('CPU RSS cap exceeded')
        save(out / 'INPUT_FROZEN.json', manifest)
        event(out, 'INPUT_PREPARATION_COMPLETE', elapsed_s=manifest['elapsed_s'], max_rss_bytes=manifest['max_rss_bytes'])
    except BaseException as exc:
        event(out, 'FAILED_PRESERVED', error=repr(exc))
        raise


if __name__ == '__main__':
    main()
