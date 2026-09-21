# TODO

- [ ] Extract specimen data while preserving the actual time of day of receipt.
      `Data/Received_sample_data/Received_sample_data.xlsx`'s `anon_received`/`anon_verified`
      columns are fractional days, but the decimal part is *not* zeroed to midnight - it
      doesn't currently line up with true time-of-day, so hour-of-day can't be read off it
      as-is. A re-extraction needs to anchor the fractional part to actual midnight (or
      otherwise supply the real offset) so arrivals can eventually be fitted per hour-of-day,
      not just per day-of-week (see `diagnostics/real_data_fit_report.html`'s day-of-week
      table for why the current constant-rate Poisson arrival model is missing this).
- [ ] Extract patient demographic data (age, gender, ...) alongside the specimen results.
      The real dataset currently has no patient-level fields at all, so the positivity/organism
      comparisons in `analysis/` can't be cross-checked against `lab_sim`'s age/gender
      positivity modifiers (`lab_sim/patients.py`, `SimulationConfig.elderly_age_threshold`
      etc.) the way specimen type already can be.
