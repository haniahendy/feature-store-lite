# feature-store-lite

A minimal point-in-time correct feature store: entity-timestamped
feature tables, as-of joins against a label set, TTL staleness control,
and leakage accounting. The piece of the ML workflow that keeps training
data honest when features and labels arrive at different times.

Pure Python 3.10+, zero dependencies.

## Usage

```bash
PYTHONPATH=src python3 -m featurestore.cli \
    --labels labels.csv --features clicks=clicks.csv profile=profile.csv \
    --ttl-seconds 7200 --out training.csv
```

```
joined rows: 2, labels missing features: 1, stale rows dropped: 0
```

CSVs share `entity,ts` columns (ISO-8601); every other column is a
feature. Output rows carry `<table>.<feature>` columns as of each
label's timestamp.

## Guarantees and semantics

- For each label (entity, ts) and table, the join selects the latest
  feature row with `feature_ts <= label_ts`. Future rows are never
  read - that direction is leakage by definition.
- `--ttl-seconds` drops candidates older than the TTL as stale and
  counts them, so silently ancient features cannot pass as fresh.
- A label with no usable row in ANY table is excluded from the output
  and counted in `missing` - partial rows quietly teach models the
  wrong thing, so they are not emitted.
- Duplicate (entity, ts) rows inside a table are rejected at load.

## Honest limits

- In-memory and single-machine: fine for thousands-to-low-millions of
  rows; a real feature store adds storage, serving, and backfills.
- Timestamps are compared as ISO-8601 strings after parsing; mixing
  naive and timezone-aware timestamps in one input raises - normalize
  to UTC first.
- Numeric features only; categorical encoding belongs one layer up.
- No feature versioning or registry metadata; the table name and the
  CSV are the contract.
- As-of correctness protects the *time* direction only. Group leakage
  (same user in train and test) still needs a proper split strategy.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

9 tests: as-of row selection, future-leakage exclusion, TTL staleness,
missing-entity/missing-history accounting, duplicate rejection,
multi-entity joins.
