from __future__ import annotations


def normalize_ts(value: int | float) -> float:
    """Normalize timestamps to seconds if they look like milliseconds."""
    ts = float(value)
    if ts > 1_000_000_000_000:
        ts = ts / 1000.0
    return ts