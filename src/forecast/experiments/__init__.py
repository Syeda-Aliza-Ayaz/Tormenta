"""Experiments on the forecaster that are not part of the live system (DECISIONS D-66 to D-75).

Each module reproduces one recorded experiment; none is imported by the daily job or the apps. The yearly
validation harness itself (`src/forecast/validate_yearly.py`) stays next to the production code, because the
locked model's test (`src/forecast/test_locked.py`) uses it.
"""
