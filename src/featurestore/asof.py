"""Point-in-time (as-of) joins with TTL and leakage accounting.

For each label (entity, ts) and each feature table, select the latest
feature row with feature_ts <= label_ts - this is the only direction a
real training pipeline may read. Rows newer than the label are never
selected (that would be leakage); rows older than the TTL are dropped as
stale and reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from .table import FeatureRow, FeatureTable


def _parse(ts: str) -> datetime:
    """ISO-8601 timestamps; 'Z' tolerated. Naive vs aware must not mix."""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt


@dataclass
class JoinReport:
    rows: List[Dict[str, object]] = field(default_factory=list)
    missing: int = 0        # labels with no usable row in some table
    stale_dropped: int = 0  # candidate rows excluded by TTL
    tables: List[str] = field(default_factory=list)


def _latest_at_or_before(rows: Sequence[FeatureRow], label_dt: datetime,
                         max_age: Optional[timedelta], counter) -> Optional[FeatureRow]:
    best: Optional[FeatureRow] = None
    for row in rows:  # rows are chronological
        row_dt = _parse(row.ts)
        if row_dt > label_dt:
            break  # leakage guard: never read the future
        if max_age is not None and label_dt - row_dt > max_age:
            counter["stale"] += 1
            continue
        best = row
    return best


def point_in_time_join(
    labels: Sequence[Tuple[str, str]],
    tables: Sequence[FeatureTable],
    max_age_seconds: Optional[float] = None,
) -> JoinReport:
    """Join (entity, ts) labels with feature tables as of the label time.

    Output row: entity, ts, then "<table>.<feature>" columns. A label
    missing a usable row in ANY table is skipped from ``rows`` and counted
    in ``missing`` - partial rows silently teach models the wrong thing.
    """
    max_age = (timedelta(seconds=max_age_seconds)
               if max_age_seconds is not None else None)
    report = JoinReport(tables=[t.name for t in tables])
    for entity, label_ts in labels:
        label_dt = _parse(label_ts)
        out: Dict[str, object] = {"entity": entity, "ts": label_ts}
        complete = True
        for table in tables:
            counter = {"stale": 0}
            row = _latest_at_or_before(table.rows_for(entity), label_dt,
                                       max_age, counter)
            report.stale_dropped += counter["stale"]
            if row is None:
                complete = False
                break
            for col in table.feature_names:
                values = row.as_dict()
                out[f"{table.name}.{col}"] = values.get(col)
        if complete:
            report.rows.append(out)
        else:
            report.missing += 1
    return report
