"""Read-only local-link and published provenance checks; never runs experiments."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
links = 0
for path in [ROOT / "README.md", *(ROOT / "docs").glob("*.md"), *(ROOT / "vendor").rglob("*.md")]:
    for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        local = (path.parent / target.split("#", 1)[0]).resolve()
        if not local.is_file() or not local.is_relative_to(ROOT):
            raise SystemExit(f"Bad local link in {path.relative_to(ROOT)}: {target}")
        links += 1
receipt = json.loads((ROOT / "results/gate0_20260913/evidence_receipt.json").read_text())
for relative, expected in receipt["source_hashes"].items():
    actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Source differs from measured artifact: {relative}")
for key, relative in (("runner_sha256", "experiments/gate0/run_guarded.py"),
                      ("analysis_sha256", "experiments/gate0/analyze.py")):
    if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != receipt[key]:
        raise SystemExit(f"Provenance hash mismatch: {relative}")
print(f"PASS: {links} internal links, 4 measured source hashes, runner and analysis identity")
