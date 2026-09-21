# Content-filter execution addendum v1

Registered 2026-09-21 before new source sampling or query outcomes.
Reference source: e21f13167cbe8c6abc4e9dc35a0e864ed7085a1c.
The supplied structured protocol remains unchanged in PROTOCOL_zh.md.
The five-file historical content-filter package was not found in the scoped
local intake. New reference code is explicitly a new implementation, not a
claim to have rerun its historical six tests.

## Current authorized step

CPU-only input provenance, fresh splits and reference semantic tests. Maximum
8 threads and 8 GiB peak RSS. No GPU context, launch or existing launcher is
used. This checkpoint does not authorize automatic Stage B/C execution.
The existing read-only corpus is never modified. All outputs use a fresh run
directory. Stage A has a four-day cap from 2026-09-21; total campaign two weeks.

## Input identity and encoding

- SureChEMBL: accepted 2026-08-25 full canonical snapshot, 41,126,808 rows,
  256 bits, numeric fp_id, little-endian uint64 in original word order.
  The snapshot is chosen before sampling, not by filtering results.
- ChEMBL: official ChEMBL37 FPS (2,897,819 rows, 2048 bits). Numeric decimal
  suffix of CHEMBL ID; exactly 256 decoded FPS bytes interpreted as 32
  little-endian uint64 words. Reuse the existing all-row FPS-derived union
  only after its hashes match the accepted conversion manifest. Do not use
  the HDF5 artifact. Retain official FPS SHA-256 and conversion provenance.
- Stable IDs are validated unique, nonnegative and representable in uint64.
  Neither corpus removes duplicate bitstrings from the database.
- Bit j means bit (j%64) of word floor(j/64), with no bit permutation.
- Corpus namespaces are ASCII `surechembl-2026-08-25-256` and
  `chembl-37-fps-2048`.
- Database hash input is ASCII `20260921|<namespace>|<canonical_decimal_id>`
  with no newline or leading zeros. Compare all 32 SHA-256 bytes in unsigned
  lexicographic order, then numeric ID. Select the first 1,000,000; the first
  100,000 are the nested A database. Execution may reorder each set by
  (popcount, stable ID), retaining the original selection ranks.
- Independent query seed is ASCII `20260922`. Same encoding. Exclude IDs in
  the entire 1M database, zero bitstrings, all located old query IDs and all
  identical old query bitstrings. Among each equal-bitstring query group use
  the minimum (query SHA-256 bytes, stable ID) as its representative. Sort
  representatives by the same key; first 128 dev, next 256 A-screen, next
  512 B-final. No result counts are used anywhere in this process.
- A bounded streaming top-896 distinct-bitstring heap is equivalent to this
  ranking: discarded keys cannot become eligible as the top-set cutoff falls.
- Prior exposure remains PRIOR_EXPOSURE_UNKNOWN: scoped inventory covers
  available TIDE query artifacts, not every historical machine/conversation.
  This allows diagnostic execution, not a strict never-seen-query claim.
- B-final fingerprints are stored separately and never passed to Stage A.
  A-screen is not passed to parameter selection. File permissions are a
  workflow guard, not a cryptographic blind to the machine owner.

## Dev choice and proxy conflict rule (no outcomes inspected)

For each dataset/method choose one configuration for both thresholds. Minimize
max(total logical bytes at tau / R0 total logical bytes at tau), then the sum
of the two ratios. R0 is the same frozen legal layout in each denominator.
If still tied, use lower resident reserved bytes, then the fixed order:
natural before descending-popcount word order; g=4 before g=8; h=1 before h=8;
row-major before word-major. Apply the same rule to the R0/R1 A control and V.
CPU wall time is never a GPU performance selector.

Logical bytes are the primary A access estimator. Both it and aligned
32-byte-sector proxies must include all components in protocol section 7.2.
Sector proxies sum touched sectors per explicitly documented processing step;
no cross-step cache reuse is assumed. The model/step definitions and accounting
tests must be frozen before A-screen. If logical and sector proxies disagree
on an A gate, use INCONCLUSIVE_PROXY, not whichever proxy is favorable. Missing
state/spill/control costs also prohibit A_GO; they are unknown, not zero.
A GO requires >=20% complete access reduction at both thresholds; B/P also
requires >=10% versus R2 at one threshold and <=5% regression at the other.
No screen execution is allowed before the complete access model is frozen.

## Resource mapping

Apply the original formula at the actual A N=100,000:
`2*N*D/8 + 16*N + 64*1048576` resident index bytes. Retain 256 MiB query
workspace and 8 GiB CPU RSS caps. Additionally report the exact 1M index size
from its frozen database before B admission; a 100K fit is not a 1M fit.
Payload, used, reserved, Python diagnostic overhead and process RSS remain
separate. GPU whole-card 4 GiB is unchanged and NOT_MEASURED in Stage A.

## Deferred gates, not silently resolved

Native 2048 entry, descriptor capacities, GPU UUID/toolchain, P state if chosen,
complete overflow recovery, p95 three-process gate, profiler metrics and real
release identity require a new pre-result B/C execution record. This intake
launcher cannot start these stages. Complete A access instrumentation is also
not claimed by reference semantic correctness.
