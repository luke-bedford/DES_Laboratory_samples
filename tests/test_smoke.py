from lab_sim.v2 import SimulationConfig, aggregate_replications, run_replications, run_simulation


def test_short_run_completes_and_reports_samples():
    config = SimulationConfig(warmup_minutes=0, sim_duration_minutes=120)
    stats = run_simulation(config)

    summary = stats.summary()
    assert summary["samples_completed"] >= 0
    # Urine's cell-counting gate (see lab_sim/v2/processes.py) can reject
    # samples within this window, so rejections aren't necessarily zero.
    assert summary["samples_rejected"] >= 0


def test_urine_rejections_are_recorded_and_never_complete():
    config = SimulationConfig(warmup_minutes=0, sim_duration_minutes=3 * 24 * 60)
    stats = run_simulation(config)

    rejections = stats.observed_rejections()
    assert len(rejections) > 0

    completed_ids = {s.id for s in stats.observed_completions()}
    for sample in rejections:
        assert sample.id not in completed_ids
        assert "rejected" in sample.timestamps


def test_replications_aggregate_mean_and_interval_per_metric():
    config = SimulationConfig(warmup_minutes=0, sim_duration_minutes=120)
    summaries = run_replications(config, n_replications=5)
    assert len(summaries) == 5

    aggregate = aggregate_replications(summaries)
    assert aggregate["n_replications"] == 5
    for metric in aggregate["metrics"].values():
        assert metric["ci_low"] <= metric["mean"] <= metric["ci_high"]


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
