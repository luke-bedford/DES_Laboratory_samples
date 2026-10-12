"""NHS microbiology lab sample flow simulation.

This package holds one complete, independent implementation per model
version - see CHANGES.md in this directory for what changed between
versions and why. There is no implicit "latest" import from the top
level; pick a version explicitly, e.g.:

    from lab_sim.v3 import SimulationConfig, run_simulation

lab_sim.v0, lab_sim.v1, and lab_sim.v2 are frozen snapshots (the original
6-specimen-type constant-rate-Poisson model, the 20-specimen-type
day-of-week NHPP model, and the day-of-week x hour-of-day NHPP model with
blood-culture/urine pathways, respectively). lab_sim.v3 is the current
model, adding queueing-wait statistics on top of v2 unchanged.
"""
