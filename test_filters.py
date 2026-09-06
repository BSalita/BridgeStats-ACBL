from __future__ import annotations

import datetime
import unittest

import polars as pl

from bridgestatslib import apply_filters, apply_regex_filter, create_query
import bridgestatslib


def _board_results_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Club": [108571, 267096, 108571],
            "Player_ID_N": ["2663279", "1111111", "2222222"],
            "Player_ID_E": ["9524304", "3333333", "4444444"],
            "Player_ID_S": ["5555555", "6666666", "7777777"],
            "Player_ID_W": ["8888888", "9999999", "0000000"],
            "Declarer": ["2663279", "1111111", "2222222"],
            "Dummy": ["9524304", "3333333", "4444444"],
            "Date": [
                datetime.date(2020, 1, 15),
                datetime.date(2021, 6, 1),
                datetime.date(2018, 1, 1),
            ],
        }
    )


class FilterTests(unittest.TestCase):
    def test_apply_filters_by_club_player_and_date(self) -> None:
        df = apply_filters(
            _board_results_df(),
            clubs=["108571"],
            players=["2663279"],
            pairs=[],
            start_date="2019-01-01",
            end_date="2022-12-31",
        )
        self.assertEqual(df.height, 1)
        self.assertEqual(df["Declarer"][0], "2663279")

    def test_apply_filters_by_pair_either_order(self) -> None:
        df = apply_filters(
            _board_results_df(),
            clubs=[],
            players=[],
            pairs=["9524304_2663279"],
            start_date="2019-01-01",
            end_date="2022-12-31",
        )
        self.assertEqual(df.height, 1)
        self.assertEqual(df["Dummy"][0], "9524304")

    def test_apply_filters_empty_when_outside_date_range(self) -> None:
        df = apply_filters(
            _board_results_df(),
            clubs=[],
            players=[],
            pairs=[],
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        self.assertEqual(df.height, 0)

    def test_apply_regex_filter_matches_pbn(self) -> None:
        df = pl.DataFrame({"PBN": ["SAKQxxx", "HAKxxx", "SAKQxxx"]})
        filtered = apply_regex_filter(df, r"^SAK", sample_size=100000)
        self.assertEqual(filtered.height, 2)
        self.assertTrue(all(s.startswith("SAK") for s in filtered["PBN"]))

    def test_apply_regex_filter_samples_when_over_limit(self) -> None:
        df = pl.DataFrame({"PBN": [f"S{i:04d}" for i in range(20)]})
        filtered = apply_regex_filter(df, "", sample_size=5)
        self.assertEqual(filtered.height, 5)

    def test_create_query_uses_current_player_id_columns(self) -> None:
        query = create_query(
            "board_results",
            "",
            "",
            0,
            "Score_Declarer,PBN,session_id",
            ["108571"],
            ["2663279"],
            ["2663279_9524304"],
            0,
            "Declarer_Pct",
            0,
            9999999,
            "2019-01-01",
            "2022-12-31",
        )
        self.assertIn("Player_ID_N", query)
        self.assertIn("Player_ID_E", query)
        self.assertIn("Score_Declarer", query)
        self.assertIn("session_id", query)
        self.assertNotIn("Player_Number_", query)
        self.assertNotIn("board_record_string", query)
        self.assertNotIn("Declarer_Score", query)

    def test_normalize_board_results_uses_current_names(self) -> None:
        df = pl.DataFrame(
            {
                "session_id": ["s1"],
                "Declarer_Direction": ["N"],
                "Player_ID_N": ["1"],
                "Player_ID_E": ["2"],
                "Player_ID_S": ["3"],
                "Player_ID_W": ["4"],
                "Dummy": ["3"],
                "OnLead": ["2"],
                "NotOnLead": ["4"],
                "Tricks": [10],
                "DD_Tricks": [9],
                "Score_Declarer": [420],
                "DD_Score_Declarer": [400],
                "ParScore": [430],
                "EV_Score_Declarer": [410],
                "EV_Max_Declarer": [450],
                "MP_EV_Pct_Declarer": [0.6],
                "MP_EV_Max_Pct_Declarer": [0.7],
                "MP_Par_Pct_Declarer": [0.55],
                "Declarer_Pct": [0.5],
            }
        )
        out = bridgestatslib.normalize_board_results(df)
        self.assertIn("Declarer", out.columns)
        self.assertEqual(out["Declarer"][0], "1")
        self.assertEqual(out["Tricks_DD_Diff"][0], 1)
        self.assertEqual(out["Score_Declarer_DD_Diff"][0], 20)
        self.assertNotIn("Declarer_Score", out.columns)
        self.assertNotIn("Session", out.columns)

    def test_player_position_frequency_counts_passed_out_boards(self) -> None:
        df = pl.DataFrame(
            {
                "Player_ID_N": ["2663279", "2663279"],
                "Player_ID_E": ["2", "2"],
                "Player_ID_S": ["3", "3"],
                "Player_ID_W": ["4", "4"],
                "Declarer": ["2663279", None],
                "Dummy": ["3", None],
                "OnLead": ["2", None],
                "NotOnLead": ["4", None],
                "Declarer_Name": ["Robert", None],
            }
        )
        out = bridgestatslib.player_position_frequency(df, ["2663279"])
        self.assertEqual(out["Count"][0], 2)
        self.assertEqual(out["PassedOut"][0], 1)
        self.assertEqual(out["Declarer"][0], 1)
        self.assertEqual(out["N"][0], 2)


if __name__ == "__main__":
    unittest.main()
