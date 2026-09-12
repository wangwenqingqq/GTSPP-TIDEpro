"""Verify the distributed starter, without reading secrets or accessing a network."""
from pathlib import Path
import hashlib

root = Path(__file__).resolve().parents[1]
expected = set((root / 'RELEASE_FILES.txt').read_text().splitlines())
if not expected or any(not x or x.startswith('/') or '..' in Path(x).parts for x in expected):
    raise SystemExit('Invalid package allowlist')
for relative in expected:
    path = root / relative
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
        raise SystemExit(f'Unsafe or missing package file: {relative}')
checked = set()
for line in (root / 'MANIFEST.sha256').read_text().splitlines():
    digest, relative = line.split('  ', 1)
    if relative not in expected or relative in checked:
        raise SystemExit('Unexpected or duplicate manifest entry')
    actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f'File differs from distributed starter: {relative}')
    checked.add(relative)
if checked != expected - {'MANIFEST.sha256'}:
    raise SystemExit('Incomplete manifest')
print(f'PASS: {len(checked)} package file hashes; no remote operation performed.')
