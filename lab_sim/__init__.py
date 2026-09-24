"""NHS microbiology lab sample flow simulation.

This package holds one complete, independent implementation per model
version - see CHANGES.md in this directory for what changed between
versions and why. There is no implicit "latest" import from the top
level; pick a version explicitly, e.g.:

    from lab_sim.v1 import SimulationConfig, run_simulation

lab_sim.v0 is a frozen snapshot of the original 6-specimen-type,
constant-rate-Poisson model (tagged `model-v0` in git). lab_sim.v1 is
the current 20-specimen-type, day-of-week NHPP model.
"""
