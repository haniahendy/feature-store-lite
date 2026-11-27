"""Command line entry point.

Join a labels CSV (entity, ts) with one or more feature CSVs into a
training-ready CSV, with an optional freshness TTL.
"""

from __future__ import annotations

import argparse
import csv
import sys

from .asof import point_in_time_join
from .table import FeatureTable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="featurestore",
        description="Point-in-time join of labels with feature tables.")
    parser.add_argument("--labels", required=True,
                        help="CSV with entity,ts columns")
    parser.add_argument("--features", required=True, nargs="+",
                        metavar="NAME=PATH",
                        help="feature tables as name=path.csv")
    parser.add_argument("--ttl-seconds", type=float, default=None,
                        help="drop feature rows older than this at label time")
    parser.add_argument("--out", default="-", help="output CSV (default stdout)")
    args = parser.parse_args(argv)

    labels = []
    with open(args.labels, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not {"entity", "ts"} <= set(reader.fieldnames or []):
            raise SystemExit("labels CSV needs entity and ts columns")
        labels = [(r["entity"], r["ts"]) for r in reader]

    tables = []
    for spec in args.features:
        if "=" not in spec:
            raise SystemExit(f"expected NAME=PATH, got {spec!r}")
        name, path = spec.split("=", 1)
        tables.append(FeatureTable.from_csv(name, path))

    report = point_in_time_join(labels, tables,
                                max_age_seconds=args.ttl_seconds)
    columns = ["entity", "ts"]
    for table in tables:
        columns += [f"{table.name}.{c}" for c in table.feature_names]

    out_fh = sys.stdout if args.out == "-" else open(args.out, "w", newline="",
                                                     encoding="utf-8")
    with out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(report.rows)
    print(f"joined rows: {len(report.rows)}, labels missing features: "
          f"{report.missing}, stale rows dropped: {report.stale_dropped}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
