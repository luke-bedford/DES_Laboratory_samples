# TODO

- [ ] `anon_received` is the sample's **booking-in** time (when reception logs it on the LIS),
      not the moment the physical sample reaches the lab - there can be a queueing/batching
      delay between the two that the current data can't see. This matters in two ways: the
      `analysis/` inter-arrival gaps (fitted against `SampleTypeProfile.mean_interarrival_minutes`,
      which models the simulation's true physical arrival process in `lab_sim/v1/arrivals.py`) are
      really inter-*booking-in* gaps - staff-paced, not a clean external process - which is a
      much better-grounded explanation for the overdispersion the day-of-week NHPP/Weibull
      review couldn't fully explain (see `diagnostics/real_data_fit_report.html`) than
      day-of-week alone. And real turnaround (verified − received) excludes whatever wait
      happens before booking-in, so it understates true sample-to-result time from a clinical
      perspective. A future re-extraction should capture true physical arrival time separately
      from booking-in time.
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
      positivity modifiers (`lab_sim/v1/patients.py`, `SimulationConfig.elderly_age_threshold`
      etc.) the way specimen type already can be.
