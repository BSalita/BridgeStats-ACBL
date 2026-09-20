from __future__ import annotations

import os
import unittest
from pathlib import Path

import bridge_api_common as api_common


class BridgeApiCommonTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous = os.environ.pop(api_common.DATA_ROOT_ENV, None)

    def tearDown(self) -> None:
        if self._previous is None:
            os.environ.pop(api_common.DATA_ROOT_ENV, None)
        else:
            os.environ[api_common.DATA_ROOT_ENV] = self._previous

    def test_prepare_sql_rejects_forbidden_and_qualifies_from(self) -> None:
        sql, limit = api_common.prepare_sql("SELECT 1", "club_board_results", 99999)
        self.assertEqual(sql, "FROM self SELECT 1")
        self.assertEqual(limit, api_common.MAX_SQL_ROW_LIMIT)
        with self.assertRaises(ValueError):
            api_common.prepare_sql("COPY self TO 'x'", "club_board_results")

    def test_select_favorites(self) -> None:
        payload = {
            "SelectBoxes": {
                "Vetted_Prompts": {
                    "fav1": {
                        "title": "One",
                        "prompts": [{"prompt": "rows", "sql": "SELECT 1"}],
                    }
                }
            }
        }
        favorites = api_common.flatten_favorites_payload(payload)
        self.assertEqual(api_common.select_favorites(favorites, "fav1")["count"], 1)

    def test_data_root_search_paths(self) -> None:
        os.environ[api_common.DATA_ROOT_ENV] = "/data"
        self.assertEqual(
            api_common.data_root_search_paths("acbl")[0], Path("/data/stats/acbl")
        )


if __name__ == "__main__":
    unittest.main()
