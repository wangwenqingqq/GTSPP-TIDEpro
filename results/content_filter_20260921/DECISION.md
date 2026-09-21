# Content-filter CPU reference checkpoint — 2026-09-21

Protocol: tide_content_filter_v1_20260921.
Reference repository commit: e21f13167cbe8c6abc4e9dc35a0e864ed7085a1c.
Status: **STAGE_A_IN_PROGRESS**, not A_GO.

## Completed measured scope

- Canonical source SHA-256 checks passed for SureChEMBL 2026-08-25 (41,126,808
  rows, 256 bits) and official ChEMBL37 FPS (2,897,819 rows, 2048 bits), including
  the accepted FPS-derived ID/fingerprint artifacts. No HDF5 substitution.
- Each condition now has frozen nested 100K/1M databases and 128 dev / 256
  A-screen / 512 sealed B-final queries. Database IDs and query IDs are disjoint;
  query bitstrings do not cross splits. No result cardinality was used to sample.
- Located old-query exclusions contain 4,431 IDs / 4,419 bitstrings for
  SureChEMBL and 544 IDs / 544 bitstrings for ChEMBL. Historical exposure is
  still **PRIOR_EXPOSURE_UNKNOWN**, not a strict fresh-query guarantee.
- New CPU reference tests passed: 261,120 exhaustive D=8 query/object/threshold
  combinations; 10,602 method/query/threshold comparisons including directed
  256/2048-bit boundaries, duplicate fingerprints, tail masks, and B/P equality.
- An additional 184 checks passed with deliberately poisoned invalid bitmap tail
  bits and truncated h=8 prefixes. Native GPU capacities remain untested.
- Streaming sample selection matched a full-sort independent fixture.
- The independent raw AND/OR/popcount C++ oracle produced eight complete result
  artifacts: 2 conditions x 2 splits (dev/A-screen) x 2 thresholds, totaling
  1,536 query-threshold requests over 100K rows. Synthetic and small real-data
  cross-checks against the pinned Python Fraction oracle passed.
- Input preparation took 167.23 seconds with peak RSS 1,930,014,720 bytes.
  Oracle runner/child peak RSS was 55,017,472 / 124,248,064 bytes. These are CPU
  preparation diagnostics, **not query-performance results**.

## Real-dev reference correctness completed

The full real-dev CPU reference correctness grid completed at 2026-09-21
12:10:10 UTC: R0, two R1 orders, R2 g=4/8, B h=1/8, P h=1/8; 128 dev queries,
two thresholds, both datasets. All **4,608** method/query/threshold rows match
the independent complete-tuple oracle, with zero false negatives, false
positives, tuple mismatches or duplicate IDs. B/P survivor hashes agree in all
1,024 paired comparisons. The retained CSV has SHA-256
`4d5417c7ee48eb458afa74ab7123b59260808b17063bd2d8817f934edd66afa7`.
Peak RSS was 287,199,232 bytes. No process from this checkpoint remains running.

This is **REFERENCE_DEV_PASS_NOT_A_GO**. Fullscan verification was used for this
semantic checkpoint. V/config selection has not been performed. Access metrics
in the CSV remain NA, not zero. CPU times are diagnostics, not GPU comparators.
No A-screen method evaluation or GPU initialization occurred. The complete
results, raw process logs, and original host-local receipts are preserved;
only curated source, manifests and derived correctness measurements are in Git.

## Remaining mandatory gates

| Dimension | Current state | Required next evidence |
|---|---|---|
| correctness | partial | Real-dev grid passed; native filter/capacity checks remain |
| resource | partial | Actual index/workspace reserved accounting; exact 1M forecast |
| mechanism | unknown | Freeze and test complete logical/sector access model; dev selection; A-screen |
| native_system | NOT_STARTED | A_GO then separately frozen GPU campaign |
| novelty_coverage | NOT_ESTABLISHED | Mature same-contract content index; ordinary mechanisms are prior art |

No native filter sanitizer/capacity pass, access saving, GPU speedup, A_GO or
novel contribution is claimed. A-screen oracle preparation is not A-screen
method evaluation. B-final has not been used. Source fingerprints and widths
remain unchanged; differing corpus and width prevent width-only attribution.

## Decision and publication

Continue the registered Stage A diagnostic, not a new data structure. Stop or
record a versioned repair on correctness/resource failure. Do not select a
configuration using screen results or promote a byte proxy to GPU speed.

The corresponding GitHub repository was live-verified **public**, contrary to
its historical private label. Upload was authorized on 2026-09-21 after that
public status was disclosed. Publish only the independent
`research/content-filter-20260921` branch; do not merge the default branch or
change visibility. The actual pushed SHA must be independently verified.
Original fingerprints, oracle tuple binaries, private source-location maps,
credentials, and machine configuration are excluded.
