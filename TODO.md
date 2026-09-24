# TODO

- [ ] `anon_received` is the sample's **booking-in** time (when reception logs it on the LIS),
      not the moment the physical sample reaches the lab - there can be a queueing/batching
      delay between the two that the current data can't see. This matters in two ways: the
      `analysis/` inter-arrival gaps (fitted against `SampleTypeProfile.arrivals_per_day_by_weekday`
      and, as of v2, `hourly_fraction_of_day` - which together model the simulation's true
      physical arrival process in `lab_sim/v2/arrivals.py`) are really inter-*booking-in* gaps -
      staff-paced, not a clean external process - which is a much better-grounded explanation
      for the overdispersion the day-of-week/hour-of-day NHPP/Weibull review couldn't fully
      explain (see `diagnostics/v2/real_data_fit_report.html`) than time-of-arrival granularity
      alone. And real turnaround (verified − received) excludes whatever wait happens before
      booking-in, so it understates true sample-to-result time from a clinical perspective. A
      future re-extraction should capture true physical arrival time separately from
      booking-in time.
- [x] Extract specimen data while preserving the actual time of day of receipt. Resolved: a
      later re-extraction added a `received_hour` column (integer 0-23), directly and
      reliably giving true hour-of-day - unlike `anon_received`'s fractional-day component,
      which is still not usable for this (see `analysis/load_real_data.py`'s module docstring
      for the discovered constant 3-hour offset between the two, and
      `diagnostics/v2/real_data_fit_report.html` for the resulting hour-of-day NHPP review).
      Model v2 uses `received_hour` for its arrival model (`SampleTypeProfile.
      hourly_fraction_of_day`, `lab_sim/v2/config.py`).
- [ ] Extract patient demographic data (age, gender, ...) alongside the specimen results.
      The real dataset currently has no patient-level fields at all, so the positivity/organism
      comparisons in `analysis/` can't be cross-checked against `lab_sim`'s age/gender
      positivity modifiers (`lab_sim/v2/patients.py`, `SimulationConfig.elderly_age_threshold`
      etc.) the way specimen type already can be.
