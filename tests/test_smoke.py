from lab_sim import SimulationConfig, run_simulation


def test_short_run_completes_and_reports_samples():
    config = SimulationConfig(sim_duration_minutes=120, mean_interarrival_minutes=5.0)
    stats = run_simulation(config)

    summary = stats.summary()
    assert summary["samples_completed"] >= 0
    assert summary["samples_rejected"] == 0
