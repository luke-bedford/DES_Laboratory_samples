from lab_sim.v2 import SimulationConfig, run_simulation


def test_short_run_completes_and_reports_samples():
    config = SimulationConfig(warmup_minutes=0, sim_duration_minutes=120)
    stats = run_simulation(config)

    summary = stats.summary()
    assert summary["samples_completed"] >= 0
    assert summary["samples_rejected"] == 0


def test_warmup_period_excludes_early_arrivals_from_stats():
    config = SimulationConfig(warmup_minutes=180, sim_duration_minutes=60)
    stats = run_simulation(config)

    # The warm-up period should have simulated real traffic, not been skipped.
    assert any(s.arrival_time < config.warmup_minutes for s in stats.arrivals)

    # But none of that traffic should count as "observed".
    assert all(s.arrival_time >= config.warmup_minutes for s in stats.observed_arrivals())
    assert all(
        s.timestamps.get("reported", s.arrival_time) >= config.warmup_minutes
        for s in stats.observed_completions()
    )
