from __future__ import annotations

import datetime
import unittest

import polars as pl

import bridgestatslib as lib


def _selected_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Date": [datetime.date(2020, 1, 15), datetime.date(2020, 1, 15)],
            "session_id": ["s1", "s1"],
            "HandRecordBoard": ["b1", "b1"],
            "Declarer": ["2663279", "9524304"],
            "Declarer_Name": ["Robert", "Kerry"],
            "Dummy": ["9524304", "2663279"],
            "Declarer_Pair": ["2663279_9524304", "9524304_2663279"],
            "Declarer_Pct": [0.6, 0.4],
            "Score_Declarer": [420, -50],
            "Tricks": [10, 8],
            "DD_Tricks": [9, 9],
            "ParScore": [400, 400],
            "Result": [1, -1],
            "Count": [0, 0],
            "PBN": ["N:AK...", "N:AK..."],
        }
    )


class ReportLibTests(unittest.TestCase):
    def test_add_board_scoring_columns(self) -> None:
        out = lib.add_board_scoring_columns(_selected_df())
        self.assertEqual(out["DD_GE"][0], 1)
        self.assertEqual(out["OverTricks"][0], 1)
        self.assertEqual(out["UnderTricks"][1], 1)

    def test_dedupe_keeps_last_pbn_declarer(self) -> None:
        df = pl.concat([_selected_df(), _selected_df()])
        out = lib.dedupe_boards_by_pbn_declarer(df)
        self.assertEqual(out.height, 2)

    def test_aggregate_by_declarer_and_session(self) -> None:
        df = lib.add_board_scoring_columns(_selected_df())
        df = lib.attach_pair_player_names(df, {"2663279": "Robert", "9524304": "Kerry"})
        by_decl = lib.aggregate_by_declarer(df, "Declarer_Pct", min_declares=1, top_n=10)
        self.assertEqual(by_decl.height, 2)
        by_sess = lib.aggregate_by_session(df, "Declarer_Pct")
        self.assertEqual(by_sess.height, 1)

    def test_identical_boards_and_pair_h2h(self) -> None:
        df = lib.add_board_scoring_columns(_selected_df())
        df = lib.attach_pair_player_names(df)
        comparison = lib.identical_boards_comparison(df, "Declarer_Pct")
        self.assertEqual(comparison["n_boards"], 1)
        self.assertGreater(comparison["identical_boards"]["row_count"], 0)
        h2h = lib.pair_head_to_head(df, "Declarer_Pct")
        self.assertGreater(h2h.height, 0)

    def test_chart_series_bar_payload(self) -> None:
        df = lib.add_board_scoring_columns(_selected_df())
        charts = lib.chart_series(df, ["Declarer_Pct"])
        kinds = {chart["kind"] for chart in charts}
        self.assertTrue({"info", "bar"} & kinds)

    def test_run_sql_rejects_unknown_source_and_forbidden(self) -> None:
        with self.assertRaises(ValueError):
            lib.run_sql("SELECT 1", "not_a_source")
        with self.assertRaises(ValueError):
            lib.run_sql("COPY self TO 'x.csv'", "club_board_results")

    def test_frame_to_table_round_trip(self) -> None:
        table = lib.frame_to_table(_selected_df(), limit=1)
        self.assertEqual(table["row_count"], 1)
        self.assertTrue(table["truncated"])
        back = lib.table_to_frame(table)
        self.assertEqual(back.height, 1)

    def test_table_to_frame_accepts_late_date_strings(self) -> None:
        rows = [{"club_enrolled": None} for _ in range(120)]
        rows.append({"club_enrolled": "2018-12-29"})
        table = {"columns": ["club_enrolled"], "rows": rows, "row_count": len(rows)}
        back = lib.table_to_frame(table)
        self.assertEqual(back.height, 121)
        self.assertEqual(back["club_enrolled"][-1], "2018-12-29")


if __name__ == "__main__":
    unittest.main()
