"""Read-only local-link and published provenance checks; never runs experiments."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

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
gate1 = ROOT / "results/gate1_20260913/evidence_receipt.json"
if gate1.exists():
    evidence = json.loads(gate1.read_text())
    expected = dict(evidence["source_hashes"])
    expected["experiments/gate1/run_guarded.py"] = evidence["runner_sha256"]
    expected["experiments/gate1/analyze.py"] = evidence["analysis_sha256"]
    for relative, sha in expected.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != sha:
            raise SystemExit("Gate1 measured identity mismatch: " + relative)
    print(f"PASS: Gate1 {len(expected)} measured source/runner/analysis identities")
previous = ROOT / "results/gate1_20260913_v3_per_run_pin/evidence_receipt.json"
if previous.exists():
    evidence = json.loads(previous.read_text())
    for relative, sha in evidence["source_hashes"].items():
        content = subprocess.check_output(["git", "show", "1ecf8c0:" + relative], cwd=ROOT)
        if hashlib.sha256(content).hexdigest() != sha:
            raise SystemExit("Gate1 v3 archived source mismatch: " + relative)
    print("PASS: archived Gate1 v3 source identities at 1ecf8c0")
ablation = ROOT / "results/gate1_staging_ablation_20260913.json"
if ablation.exists():
    evidence = json.loads(ablation.read_text())
    for relative, key in (("experiments/gate1/compare_staging.py", "analysis_sha256"),
                          ("results/gate1_20260913/summary.json", "after_summary_sha256"),
                          ("results/gate1_20260913_v3_per_run_pin/summary.json", "before_summary_sha256")):
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != evidence[key]:
            raise SystemExit("Staging ablation identity mismatch: " + relative)
    print("PASS: staging ablation script and both input summaries")
