from __future__ import annotations

import unittest

import polars as pl

import bridgestatslib

REQUIRED_FILES = (
    "acbl_club_board_results_augmented.parquet",
    "acbl_tournament_board_results_augmented.parquet",
    "acbl_club_hand_records_augmented_narrow.parquet",
    "acbl_tournament_hand_records_augmented_narrow.parquet",
    "acbl_club_player_name_dict.pkl",
    "acbl_tournament_player_name_dict.pkl",
    "acbl_club_hand_records_d.pkl",
    "acbl_tournament_hand_records_d.pkl",
    "acbl_clubs.parquet",
    "acbl_player_info.parquet",
)

REQUIRED_COLUMNS = {
    "acbl_club_board_results_augmented.parquet": (
        "Club",
        "Declarer_Direction",
        "Player_ID_N",
        "Player_ID_E",
        "Player_ID_S",
        "Player_ID_W",
        "Vul_Declarer",
        "ParScore",
        "MP_Par_Pct_Declarer",
        "Score_Declarer",
        "DD_Tricks",
        "Tricks",
        "DD_Score_Declarer",
        "MP_DD_Pct_Declarer",
        "EV_Score_Declarer",
        "EV_Max_Declarer",
        "MP_EV_Pct_Declarer",
        "MP_EV_Max_Pct_Declarer",
        "Declarer_Pct",
        "game_date",
        "Dummy",
        "OnLead",
        "NotOnLead",
        "Declarer_Name",
        "Session",
        "HandRecordBoard",
        "Board",
        "Result",
        "BidLvl",
        "BidSuit",
        "Dbl",
        "Vul",
        "ContractType",
    ),
    "acbl_tournament_board_results_augmented.parquet": (
        "Tricks",
        "Declarer_DD_Tricks",
        "Declarer_Score",
        "Declarer_DD_Score",
        "Declarer_ParScore",
        "Player_Number_N",
        "Player_Number_E",
        "Player_Number_S",
        "Player_Number_W",
        "Declarer",
        "Dummy",
        "OnLead",
        "NotOnLead",
        "Date",
        "Session",
        "HandRecordBoard",
        "Declarer_Name",
        "Declarer_Pct",
    ),
    "acbl_club_hand_records_augmented_narrow.parquet": (
        "game_date",
        "board_record_string",
    ),
    "acbl_tournament_hand_records_augmented_narrow.parquet": (
        "Date",
        "board_record_string",
    ),
    "acbl_clubs.parquet": ("id", "name"),
    "acbl_player_info.parquet": (
        "mp_total",
        "club",
        "acbl_number",
        "last_name",
        "rank_description",
    ),
}


class DataManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data_path = bridgestatslib.resolve_data_path()

    def test_required_files_exist(self) -> None:
        missing = [
            name
            for name in REQUIRED_FILES
            if not (self.data_path / name).is_file()
        ]
        self.assertEqual(
            missing,
            [],
            f"Missing required data files under {self.data_path}: {missing}",
        )

    def test_parquet_schemas_have_required_columns(self) -> None:
        for name, columns in REQUIRED_COLUMNS.items():
            with self.subTest(name=name):
                path = self.data_path / name
                self.assertTrue(path.is_file(), f"missing {path}")
                schema = pl.read_parquet_schema(path)
                missing = [col for col in columns if col not in schema]
                self.assertEqual(missing, [], f"{name} missing columns: {missing}")


if __name__ == "__main__":
    unittest.main()
