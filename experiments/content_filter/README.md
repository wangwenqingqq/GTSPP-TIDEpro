# Content-filter Stage A intake

Start from PROTOCOL_zh.md and EXECUTION_ADDENDUM.md. This initial checkpoint
implements input preparation, new CPU reference semantics, an independent
complete-tuple CPU oracle, and the real-dev correctness grid. It does not
implement the complete access model, dev selection, A-screen or any GPU run.
Do not interpret its completion as A_GO.

Requirements: Linux, Python >=3.10, NumPy, and g++ with C++17 support;
read-only canonical data; <=8 CPU threads,
8 GiB process cap. Use a fresh output directory. From the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/content_filter/prepare_inputs.py --sources private/sources.json --output raw_data/content_filter_v1
```

The host-local source JSON records exact canonical paths/hashes, widths, row
counts and old query files. It is deliberately outside Git. The launcher
reuses the repository's read-only digest/source-stability helper, verifies all
canonical identities, runs new reference tests, freezes nested 100K/1M samples
and three query splits, then exits. Failures remain in attempts.jsonl. It never
runs Stage A-screen or B, and never overwrites historical data.

Synthetic semantic test alone (not native capacity/sanitizer coverage):

```sh
python3 experiments/content_filter/reference_semantics.py --self-test
python3 experiments/content_filter/test_boundaries.py
```

Next gate: native uint64/buffer boundary tests, independent real-data oracle,
complete logical/sector access-accounting implementation and tests, then dev
selection freeze before opening A-screen. Keep B-final sealed until GPU freeze.

After successful intake, prepare independent A oracles, then check all registered
reference configurations on dev (no A-screen selection or GPU timing):

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/content_filter/run_oracle.py --input raw_data/content_filter_v1 --output raw_data/oracle_v1
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/content_filter/check_dev.py --input raw_data/content_filter_v1 --oracle raw_data/oracle_v1 --output raw_data/reference_dev_v1
```

Oracle tests cross-check raw C++ AND/OR/popcount with the existing pinned
Python Fraction oracle on synthetic boundaries and real-data subsets. Streaming
sampling is compared against full sorting on a 3,000-record fixture. The dev
checker compares complete tuples and B/P survivor IDs. Its CSV records missing
access metrics as NA; CPU diagnostic time must not select a GPU configuration.

Audit the retained public correctness evidence without downloading fingerprints
or launching any experiment:

```sh
python3 experiments/content_filter/audit_checkpoint.py
```

Data provenance: SureChEMBL data are provided by the EMBL-EBI ChEMBL team
([official downloads](https://chembl.gitbook.io/surechembl/downloads/bulk-data));
ChEMBL37 uses the official `chembl_37.fps.gz` artifact, not the separate HDF5
representation. See `results/content_filter_20260921/SOURCE_IDENTITY.json` for
accepted input hashes and `INPUT_FROZEN.json` for deterministic sample identity.
Original fingerprints and complete oracle tuple binaries are not redistributed.
The published CSV contains derived correctness diagnostics and query identifiers;
it contains no fingerprint bitstrings or molecular structures. Existing data
provider terms continue to apply; this checkpoint does not relicense datasets.

This is not a self-contained data distribution. Full reproduction also requires
the exact canonical artifacts and old query inventory identified in the frozen
manifests, plus a host-local sources JSON mapping those identities to files.
The resource guard uses Linux RLIMIT_AS and Linux ru_maxrss units. The published
INPUT_FROZEN manifest replaces private path prefixes with relative source
labels; INPUT_EXPORT_RECEIPT.json links its checksum to the unchanged executed
freeze checksum. This privacy export does not modify input selection or data.
