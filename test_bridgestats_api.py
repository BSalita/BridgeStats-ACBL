from __future__ import annotations

import datetime
import os
import tempfile
import unittest

import polars as pl
from fastapi.testclient import TestClient


def _write_player_and_club(root) -> None:
    pl.DataFrame(
        {
            "acbl_number": ["2663279", "9524304"],
            "first_name": ["Robert", "Kerry"],
            "last_name": ["Salita", "Flom"],
            "club": ["108571", "108571"],
            "mp_total": [100.0, 200.0],
            "rank_description": ["Life Master", "Life Master"],
        }
    ).write_parquet(root / "acbl_player_info.parquet")
    pl.DataFrame({"id": ["108571"], "name": ["Fort Lauderdale"]}).write_parquet(
        root / "acbl_club_clubs_cleaned.parquet"
    )


def _write_board_results(root) -> None:
    pl.DataFrame(
        {
            "Club": [108571, 108571],
            "session_id": ["s1", "s1"],
            "Date": [datetime.date(2020, 1, 15), datetime.date(2020, 1, 15)],
            "Declarer_Direction": ["N", "S"],
            "Declarer": ["2663279", "9524304"],
            "Dummy": ["9524304", "2663279"],
            "OnLead": ["1111111", "2222222"],
            "NotOnLead": ["3333333", "4444444"],
            "Declarer_Name": ["Robert", "Kerry"],
            "Player_ID_N": ["2663279", "9524304"],
            "Player_ID_E": ["1111111", "2222222"],
            "Player_ID_S": ["9524304", "2663279"],
            "Player_ID_W": ["3333333", "4444444"],
            "Vul_Declarer": ["None", "None"],
            "ParScore": [400, 400],
            "MP_Par_Pct_Declarer": [0.5, 0.5],
            "Score_Declarer": [420, -50],
            "DD_Tricks": [9, 9],
            "Tricks": [10, 8],
            "DD_Score_Declarer": [400, 400],
            "MP_DD_Pct_Declarer": [0.6, 0.4],
            "EV_Score_Declarer": [410, 390],
            "EV_Max_Declarer": [450, 450],
            "MP_EV_Pct_Declarer": [0.55, 0.45],
            "MP_EV_Max_Pct_Declarer": [0.7, 0.7],
            "Declarer_Pct": [0.6, 0.4],
            "HandRecordBoard": ["b1", "b1"],
            "Board": [1, 1],
            "Result": [1, -1],
            "BidLvl": [4, 4],
            "BidSuit": ["H", "H"],
            "Dbl": ["", ""],
            "Vul": ["None", "None"],
            "ContractType": ["game", "game"],
            "PBN": ["N:AK...", "N:AK..."],
        }
    ).write_parquet(root / "acbl_club_board_results_augmented.parquet")


class BridgeStatsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = __import__("pathlib").Path(self._tmpdir.name)
        _write_player_and_club(self.root)
        _write_board_results(self.root)
        self._prev_data = os.environ.get("BRIDGESTATS_DATA_DIR")
        os.environ["BRIDGESTATS_DATA_DIR"] = str(self.root)
        import importlib

        import bridgestatslib
        import bridgestats_api_server

        importlib.reload(bridgestatslib)
        importlib.reload(bridgestats_api_server)
        self.client = TestClient(bridgestats_api_server.app)

    def tearDown(self) -> None:
        if self._prev_data is None:
            os.environ.pop("BRIDGESTATS_DATA_DIR", None)
        else:
            os.environ["BRIDGESTATS_DATA_DIR"] = self._prev_data
        self._tmpdir.cleanup()

    def test_health_and_dataset_info(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        info = self.client.get("/acbl-stats/dataset-info")
        self.assertEqual(info.status_code, 200)
        self.assertIn("sources", info.json())

    def test_sql_and_board_results(self) -> None:
        sql = self.client.post(
            "/acbl-stats/sql",
            json={"sql": "SELECT Club, Declarer FROM self LIMIT 2", "source": "club_board_results"},
        )
        self.assertEqual(sql.status_code, 200)
        self.assertGreaterEqual(sql.json()["row_count"], 1)
        report = self.client.post(
            "/acbl-stats/board-results",
            json={
                "club_or_tournament": "club",
                "clubs": ["108571"],
                "players": ["2663279"],
                "start_date": "2019-01-01",
                "end_date": "2021-01-01",
                "include_charts": False,
            },
        )
        self.assertEqual(report.status_code, 200, report.text)
        body = report.json()
        self.assertGreaterEqual(body["selected_count"], 1)
        self.assertTrue(body["player_boards"])

    def test_player_lookup_fuzzy_name_and_exact_number(self) -> None:
        by_name = self.client.get(
            "/acbl-stats/players/lookup",
            params={"names": "salitta", "limit": 10},
        )
        self.assertEqual(by_name.status_code, 200, by_name.text)
        ids = [row["acbl_number"] for row in by_name.json()["rows"]]
        self.assertEqual(ids, ["2663279"])
        by_number = self.client.get(
            "/acbl-stats/players/lookup",
            params={"numbers": "2663279", "limit": 10},
        )
        self.assertEqual(by_number.status_code, 200, by_number.text)
        self.assertEqual(
            [row["acbl_number"] for row in by_number.json()["rows"]], ["2663279"]
        )
        partial = self.client.get(
            "/acbl-stats/players/lookup",
            params={"numbers": "2663", "limit": 10},
        )
        self.assertEqual(partial.status_code, 200, partial.text)
        self.assertEqual(partial.json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
