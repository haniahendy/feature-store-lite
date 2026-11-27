"""Entity-timestamped feature tables."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FeatureRow:
    entity: str
    ts: str  # ISO-8601; lexical order must match chronological order
    values: Tuple[Tuple[str, float], ...]

    def as_dict(self) -> Dict[str, float]:
        return dict(self.values)


class FeatureTable:
    """Rows of (entity, timestamp, named numeric features) for one topic."""

    def __init__(self, name: str, rows: Optional[List[FeatureRow]] = None) -> None:
        if not name:
            raise ValueError("table name must not be empty")
        self.name = name
        self._by_entity: Dict[str, List[FeatureRow]] = {}
        self._seen_keys = set()
        self.feature_names: List[str] = []
        for row in rows or []:
            self.add(row)

    def add(self, row: FeatureRow) -> None:
        if not row.entity:
            raise ValueError("row entity must not be empty")
        if not row.ts:
            raise ValueError("row timestamp must not be empty")
        key = (row.entity, row.ts)
        if key in self._seen_keys:
            raise ValueError(
                f"duplicate row for entity={row.entity!r} ts={row.ts!r} "
                f"in table {self.name!r}")
        self._seen_keys.add(key)
        for col, _ in row.values:
            if col not in self.feature_names:
                self.feature_names.append(col)
        self._by_entity.setdefault(row.entity, []).append(row)

    def rows_for(self, entity: str) -> List[FeatureRow]:
        """Chronologically ordered rows for one entity."""
        return sorted(self._by_entity.get(entity, []), key=lambda r: r.ts)

    def entities(self) -> List[str]:
        return sorted(self._by_entity)

    def __len__(self) -> int:
        return sum(len(v) for v in self._by_entity.values())

    @classmethod
    def from_csv(cls, name: str, path: str, entity_col: str = "entity",
                 ts_col: str = "ts") -> "FeatureTable":
        """Load a CSV: entity, ts, then one column per feature."""
        table = cls(name)
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            missing = {entity_col, ts_col} - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"missing columns in {path}: {sorted(missing)}")
            feature_cols = [c for c in (reader.fieldnames or [])
                            if c not in (entity_col, ts_col)]
            for line_no, record in enumerate(reader, start=2):
                try:
                    values = tuple((c, float(record[c])) for c in feature_cols
                                   if record[c] not in ("", None))
                    table.add(FeatureRow(entity=record[entity_col],
                                         ts=record[ts_col], values=values))
                except ValueError as exc:
                    raise ValueError(f"{path} line {line_no}: {exc}") from exc
        return table
