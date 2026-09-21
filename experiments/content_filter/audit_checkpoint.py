"""Read-only audit of the published CPU reference checkpoint; no data/GPU access."""
import collections
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / 'results/content_filter_20260921'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = json.loads((RESULT / 'DEV_CHECK_FROZEN.json').read_text())
    complete = json.loads((RESULT / 'REFERENCE_DEV_COMPLETE.json').read_text())
    assert complete['status'] == 'REFERENCE_DEV_PASS_NOT_A_GO'
    assert digest(Path(__file__).with_name('reference_semantics.py')) == frozen['implementation_sha256']
    assert digest(Path(__file__).with_name('check_dev.py')) == frozen['runner_sha256']
    assert digest(RESULT / 'ORACLE_COMPLETE.json') == frozen['oracle_manifest_sha256']
    export = json.loads((RESULT / 'INPUT_EXPORT_RECEIPT.json').read_text())
    assert digest(RESULT / 'INPUT_FROZEN.json') == export['published_manifest_sha256']
    assert export['original_host_manifest_sha256'] == frozen['input_sha256']
    assert json.loads((RESULT / 'INPUT_FROZEN.json').read_text())['original_host_manifest_sha256'] == frozen['input_sha256']
    source_match = json.loads((RESULT / 'SOURCE_MATCH.json').read_text())
    for name, sha in source_match['sha256'].items():
        assert digest(Path(__file__).with_name(name)) == sha, name
    assert digest(RESULT / 'reference_dev_correctness.csv') == complete['csv_sha256']
    with (RESULT / 'reference_dev_correctness.csv').open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == complete['method_query_threshold_rows'] == 4608
    configs = {('R0', ''), ('R1', 'natural'), ('R1', 'descending'),
               ('R2', '4'), ('R2', '8'), ('B', '1'), ('B', '8'), ('P', '1'), ('P', '8')}
    lanes = collections.defaultdict(list)
    for row in rows:
        lanes[row['lane']].append(row)
        for field in ('false_negative_count', 'false_positive_count', 'tuple_mismatch_count', 'duplicate_id_count'):
            assert int(row[field]) == 0
        assert row['logical_total_bytes'] == row['sector_proxy_bytes'] == 'NA'
        assert 0 <= int(row['H']) <= int(row['C']) <= 100000
        if row['S'] != 'NA':
            assert int(row['H']) <= int(row['S']) <= int(row['C'])
        assert math.isfinite(float(row['cpu_diagnostic_s'])) and float(row['cpu_diagnostic_s']) >= 0
    assert set(lanes) == {'surechembl-2026-08-25-256', 'chembl-37-fps-2048'}
    pairs = 0
    for name, lane in lanes.items():
        assert len(lane) == 2304 and len({r['query_id'] for r in lane}) == 128
        grouped = collections.defaultdict(list)
        for row in lane:
            grouped[row['query_id'], row['m'], row['n']].append(row)
            assert (row['m'], row['n']) in {('7', '10'), ('4', '5')}
        assert len(grouped) == 256
        for group in grouped.values():
            assert len(group) == 9 and {(r['method'], r['config']) for r in group} == configs
            assert len({r['C'] for r in group}) == len({r['H'] for r in group}) == 1
            for h in ('1', '8'):
                b = next(r for r in group if (r['method'], r['config']) == ('B', h))
                p = next(r for r in group if (r['method'], r['config']) == ('P', h))
                assert (b['S'], b['survivor_sha256']) == (p['S'], p['survivor_sha256'])
                pairs += 1
    print(json.dumps({'status': 'PASS', 'rows': len(rows), 'B_P_pairs': pairs,
                      'scope': 'retained CPU reference evidence only; not A_GO'}))


if __name__ == '__main__':
    main()
