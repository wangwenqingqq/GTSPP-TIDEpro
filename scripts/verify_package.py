"""Verify the distributed starter, without reading secrets or accessing a network."""
from pathlib import Path
import hashlib
import argparse
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--revision', help='Verify the original starter blobs at a local Git commit, without changing the worktree')
args = parser.parse_args()
revision = None
if args.revision:
    revision = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options',
                                        args.revision + '^{commit}'], cwd=root, text=True).strip()

def read(relative):
    if revision:
        return subprocess.check_output(['git', 'show', f'{revision}:{relative}'], cwd=root)
    return (root / relative).read_bytes()

expected = set(read('RELEASE_FILES.txt').decode().splitlines())
if not expected or any(not x or x.startswith('/') or '..' in Path(x).parts for x in expected):
    raise SystemExit('Invalid package allowlist')
if not revision:
    for relative in expected:
        path = root / relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise SystemExit(f'Unsafe or missing package file: {relative}')
checked = set()
for line in read('MANIFEST.sha256').decode().splitlines():
    digest, relative = line.split('  ', 1)
    if relative not in expected or relative in checked:
        raise SystemExit('Unexpected or duplicate manifest entry')
    actual = hashlib.sha256(read(relative)).hexdigest()
    if actual != digest:
        raise SystemExit(f'File differs from distributed starter: {relative}')
    checked.add(relative)
if checked != expected - {'MANIFEST.sha256'}:
    raise SystemExit('Incomplete manifest')
print(f'PASS: {len(checked)} package file hashes at {revision or "working tree"}; no remote operation performed.')
