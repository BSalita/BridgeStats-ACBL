from __future__ import annotations

import datetime
import unittest

import polars as pl

from bridgestats import apply_filters
from handstats import apply_regex_filter


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

    def test_apply_regex_filter_matches_board_record(self) -> None:
        df = pl.DataFrame(
            {
                "board_record_string": ["SAKQxxx", "HAKxxx", "SAKQxxx"],
            }
        )
        filtered = apply_regex_filter(df, r"^SAK", sample_size=100000)
        self.assertEqual(filtered.height, 2)
        self.assertTrue(all(s.startswith("SAK") for s in filtered["board_record_string"]))

    def test_apply_regex_filter_samples_when_over_limit(self) -> None:
        df = pl.DataFrame({"board_record_string": [f"S{i:04d}" for i in range(20)]})
        filtered = apply_regex_filter(df, "", sample_size=5)
        self.assertEqual(filtered.height, 5)


if __name__ == "__main__":
    unittest.main()
