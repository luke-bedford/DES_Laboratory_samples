"""Convenience entry point for the current model version. Equivalent to
`python -m lab_sim.v1`; see lab_sim/v0/__main__.py to run the frozen v0
snapshot standalone instead.
"""

from lab_sim.v1.__main__ import main

if __name__ == "__main__":
    main()
