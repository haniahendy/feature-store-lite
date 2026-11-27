"""A minimal point-in-time correct feature store.

Entity-timestamped feature tables, as-of joins against a label set, TTL
staleness control, and leakage guards - the pieces that keep training
data honest when features and labels arrive at different times.
"""

from .table import FeatureRow, FeatureTable
from .asof import JoinReport, point_in_time_join

__all__ = ["FeatureRow", "FeatureTable", "JoinReport", "point_in_time_join"]

__version__ = "0.1.0"
