# Changes between model versions

Each version below lives in its own subfolder (`lab_sim/v0/`, `lab_sim/v1/`, ...) as a
complete, independent copy of the package - not a shared codebase with version-specific
overrides. This is deliberate: the whole point of keeping an old version around is being
able to run *exactly* what it was, indefinitely, even after later versions change shared
code. See `lab_sim/__init__.py` for how to import a specific version.

## v1 (current)

- **Specimen types**: expanded from 6 placeholder types to 20 - every real specimen type
  with more than 20 occurrences in `Data/Received_sample_data.xlsx` gets its own type;
  everything rarer folds into `OTHER`.
- **Arrivals**: switched from a constant-rate Poisson process to a day-of-week
  non-homogeneous Poisson process, simulated via Lewis-Shedler thinning against real
  per-weekday arrival rates (candidates drawn at the week's max rate, accepted with
  probability `current_rate / max_rate`).
- **Positivity and organism mix**: calibrated from real data for all 20 types (previously
  placeholder values for everything except organism mix, which v0 already had calibrated -
  see the `model-v0` tag, which sits after that calibration).
- **Capacity**: scaled up roughly 38-45% to match the larger type set and arrival volume
  (HSSW 5->7, BMS 3->4, clinical microbiologists 1->2, identification analyzers 1->2,
  plate incubator slots 5000->7230; the blood-culture incubator pool is unaffected and
  stays at 2200).
- All calibration was done offline via scratchpad scripts against `Data/`, then
  hand-transcribed as static literals into `v1/config.py` - `lab_sim` has no runtime
  dependency on `Data/`.
- Cross-references: the pre-expansion model is tagged `model-v0` in git; the calibration
  and restructuring landed in this session's commits.

**Known limitation**: at v1's scaled capacity, the lab no longer clears its queue within
the simulation's observation window the way v0 did (~57% of arrivals complete within 3
days, vs. ~99% for v0; mean turnaround roughly doubles, from ~24h to ~58h). This is an
emergent finding from the higher, unevenly-distributed real arrival volume, not a bug -
see `README.md`'s "Emergent behavior" section for detail.

## v0

Initial model: 6 specimen types (blood culture, tissue, urine, swab, stool, sputum),
constant-rate Poisson arrivals per type. Organism mix was later calibrated from real data
(the version tagged `model-v0` includes that calibration); arrival rate and positivity
stayed placeholder values throughout v0's lifetime. Tagged `model-v0` in git.

## Out of scope so far

- `diagnostics/` output is a single flat, unversioned folder - running an older version's
  `main`-equivalent after a newer one overwrites the newer version's diagnostics output.
  Not addressed yet; each version's own `main.py`-style entry point should be run into a
  version-specific output directory if/when this becomes a problem.
- There is no permanent regression test for older versions - `tests/test_smoke.py` tests
  only the current version (v1).
- `analysis/` (the real-data comparison and distribution-fit tooling) is scoped to the
  current version only; it does not compare across model versions.
