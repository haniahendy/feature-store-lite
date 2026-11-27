import unittest

from featurestore import FeatureRow, FeatureTable, point_in_time_join


def row(entity, ts, **values):
    return FeatureRow(entity=entity, ts=ts, values=tuple(sorted(values.items())))


# Click features for user u1: count grows over the day.
CLICKS = FeatureTable("clicks", [
    row("u1", "2026-01-01T09:00:00", count=3.0, spend=1.5),
    row("u1", "2026-01-01T14:00:00", count=9.0, spend=4.0),
    row("u2", "2026-01-01T10:00:00", count=1.0, spend=0.5),
])
# Profile features captured at 08:00 for u1 only.
PROFILE = FeatureTable("profile", [
    row("u1", "2026-01-01T08:00:00", age_days=30.0),
])


class TestTable(unittest.TestCase):
    def test_rows_for_entity_sorted(self):
        ts = [r.ts for r in CLICKS.rows_for("u1")]
        self.assertEqual(ts, sorted(ts))
        self.assertEqual(len(CLICKS), 3)

    def test_duplicate_entity_ts_rejected(self):
        table = FeatureTable("t")
        table.add(row("e", "2026-01-01T00:00:00", x=1.0))
        with self.assertRaises(ValueError):
            table.add(row("e", "2026-01-01T00:00:00", x=2.0))

    def test_empty_entity_rejected(self):
        with self.assertRaises(ValueError):
            FeatureTable("t").add(row("", "2026-01-01T00:00:00", x=1.0))


class TestPointInTimeJoin(unittest.TestCase):
    def test_as_of_picks_latest_before_label(self):
        report = point_in_time_join(
            [("u1", "2026-01-01T15:00:00")], [CLICKS, PROFILE])
        self.assertEqual(len(report.rows), 1)
        joined = report.rows[0]
        self.assertEqual(joined["clicks.count"], 9.0)   # 14:00 row, not 09:00
        self.assertEqual(joined["profile.age_days"], 30.0)

    def test_never_reads_future_rows(self):
        # Label at 12:00 must see the 09:00 clicks row, not the 14:00 one.
        report = point_in_time_join([("u1", "2026-01-01T12:00:00")], [CLICKS])
        self.assertEqual(report.rows[0]["clicks.count"], 3.0)

    def test_label_before_any_feature_is_missing(self):
        report = point_in_time_join([("u1", "2026-01-01T07:00:00")], [CLICKS])
        self.assertEqual(report.rows, [])
        self.assertEqual(report.missing, 1)

    def test_unknown_entity_is_missing(self):
        report = point_in_time_join([("ghost", "2026-01-01T12:00:00")], [CLICKS])
        self.assertEqual(report.missing, 1)

    def test_ttl_drops_stale_rows(self):
        # 2-hour TTL: at 15:00 the 09:00 row is stale, 14:00 row survives.
        report = point_in_time_join([("u1", "2026-01-01T15:00:00")],
                                    [CLICKS], max_age_seconds=2 * 3600)
        self.assertEqual(report.rows[0]["clicks.count"], 9.0)
        # 2-hour TTL at 12:30: only 09:00 exists and it is 3.5h old -> stale.
        report = point_in_time_join([("u1", "2026-01-01T12:30:00")],
                                    [CLICKS], max_age_seconds=2 * 3600)
        self.assertEqual(report.rows, [])
        self.assertEqual(report.missing, 1)
        self.assertEqual(report.stale_dropped, 1)

    def test_multi_entity(self):
        report = point_in_time_join(
            [("u1", "2026-01-01T15:00:00"), ("u2", "2026-01-01T11:00:00")],
            [CLICKS])
        self.assertEqual(len(report.rows), 2)
        by_entity = {r["entity"]: r for r in report.rows}
        self.assertEqual(by_entity["u2"]["clicks.count"], 1.0)


if __name__ == "__main__":
    unittest.main()
