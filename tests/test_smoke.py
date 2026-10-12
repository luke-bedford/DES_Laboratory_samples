import math

from lab_sim.v3 import (
    Sample,
    SimulationConfig,
    aggregate_queueing_replications,
    aggregate_replications,
    run_replications,
    run_simulation,
    total_queue_wait_minutes,
)


def test_short_run_completes_and_reports_samples():
    config = SimulationConfig(warmup_minutes=0, sim_duration_minutes=120)
    stats = run_simulation(config)

    summary = stats.summary()
    assert summary["samples_completed"] >= 0
    # Urine's cell-counting gate (see lab_sim/v3/processes.py) can reject
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


def test_total_queue_wait_minutes_sums_marked_stages_and_ignores_missing():
    sample = Sample()
    sample.mark("reception_queue_start", 0.0)
    sample.mark("reception_start", 5.0)
    sample.mark("reading_queue_start", 10.0)
    sample.mark("reading_start", 12.5)
    # No incubation_queue_start/incubation_start marks at all - a stage the
    # sample never reached shouldn't contribute.

    assert total_queue_wait_minutes(sample) == 5.0 + 2.5


def test_queueing_replications_report_nan_not_zero_for_types_with_no_completions():
    config = SimulationConfig(warmup_minutes=0, sim_duration_minutes=3 * 24 * 60)
    summaries = run_replications(config, n_replications=3)

    aggregate = aggregate_queueing_replications(summaries)

    # Blood culture incubates for up to 5 days
    # (config.blood_culture_max_incubation_minutes) - longer than this
    # 3-day window - so no replication sees a completed blood culture
    # sample. That must report as "no data" (NaN), not bias toward 0.0.
    blood_culture = aggregate["by_type"]["BLOOD_CULTURE"]
    assert blood_culture["n_replications_with_completions"] == 0
    assert math.isnan(blood_culture["mean_minutes"])
    assert math.isnan(blood_culture["ci_low_minutes"])
    assert math.isnan(blood_culture["ci_high_minutes"])

    swab = aggregate["by_type"]["SWAB"]
    assert swab["n_replications_with_completions"] == 3
    assert swab["ci_low_minutes"] <= swab["mean_minutes"] <= swab["ci_high_minutes"]

    overall = aggregate["overall"]
    assert overall["ci_low_minutes"] <= overall["mean_minutes"] <= overall["ci_high_minutes"]


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
