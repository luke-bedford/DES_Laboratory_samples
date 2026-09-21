"""Analysis of real specimen-result data against the simulation's distributional
assumptions (see the repo root's analyze_real_data.py and README.md).

This package is one-directional: it reads from `lab_sim` (SampleType, Organism,
SimulationConfig) to compare real data against configured assumptions, but
nothing in `lab_sim` imports from here.
"""
