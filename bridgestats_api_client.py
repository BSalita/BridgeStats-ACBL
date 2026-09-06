"""HTTP client for the BridgeStats API.

Streamlit and MortyBridgeBot use this instead of importing the library.
Configure with BRIDGESTATS_API_BASE_URL (default http://127.0.0.1:8523).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Sequence

import polars as pl
import requests

BRIDGESTATS_API_BASE_URL = os.environ.get(
    "BRIDGESTATS_API_BASE_URL",
    os.environ.get("ACBL_STATS_API_BASE_URL", "http://127.0.0.1:8523"),
).rstrip("/")
_TIMEOUT_S = 300


class BridgeStatsApiClientError(RuntimeError):
    def __init__(self, detail: str, status_code: Optional[int] = None):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout_s: float = _TIMEOUT_S,
) -> Any:
    url = f"{BRIDGESTATS_API_BASE_URL}{path}"
    try:
        resp = requests.request(
            method,
            url,
            params={k: v for k, v in (params or {}).items() if v is not None},
            json=json,
            timeout=timeout_s,
        )
    except requests.RequestException as exc:
        raise BridgeStatsApiClientError(
            f"BridgeStats API unreachable at {BRIDGESTATS_API_BASE_URL}: {exc}"
        ) from exc
    if not resp.ok:
        try:
            body = resp.json()
            detail = body.get("detail") or resp.text
        except ValueError:
            detail = resp.text
        raise BridgeStatsApiClientError(str(detail), status_code=resp.status_code)
    return resp.json()


def health() -> Dict[str, Any]:
    return _request("GET", "/health", timeout_s=2)


def dataset_info() -> Dict[str, Any]:
    return _request("GET", "/acbl-stats/dataset-info")


def schema(source: str, pattern: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    return _request(
        "GET",
        "/acbl-stats/schema",
        {"source": source, "pattern": pattern, "limit": limit},
    )


def sql(sql: str, source: str = "club_board_results", limit: int = 500) -> Dict[str, Any]:
    return _request(
        "POST",
        "/acbl-stats/sql",
        json={"sql": sql, "source": source, "limit": limit},
    )


def player_lookup(
    clubs: Optional[str] = None,
    numbers: Optional[str] = None,
    names: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    return _request(
        "GET",
        "/acbl-stats/players/lookup",
        {"clubs": clubs, "numbers": numbers, "names": names, "limit": limit},
    )


def club_lookup(
    clubs: Optional[str] = None,
    names: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    return _request(
        "GET",
        "/acbl-stats/clubs/lookup",
        {"clubs": clubs, "names": names, "limit": limit},
    )


def player_positions(
    club_or_tournament: str,
    players: str,
    clubs: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    return _request(
        "GET",
        "/acbl-stats/player-positions",
        {
            "club_or_tournament": club_or_tournament,
            "players": players,
            "clubs": clubs,
            "start_date": start_date,
            "end_date": end_date,
        },
    )


def board_results_report(
    club_or_tournament: str,
    clubs: Optional[Sequence[str]] = None,
    players: Optional[Sequence[str]] = None,
    pairs: Optional[Sequence[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_column: str = "Declarer_Pct",
    min_declares: int = 0,
    top_n: int = 100,
    group_by: str = "Declarer",
    selected_charts: Optional[Sequence[str]] = None,
    include_charts: bool = True,
) -> Dict[str, Any]:
    return _request(
        "POST",
        "/acbl-stats/board-results",
        json={
            "club_or_tournament": club_or_tournament,
            "clubs": list(clubs or []),
            "players": list(players or []),
            "pairs": list(pairs or []),
            "start_date": start_date,
            "end_date": end_date,
            "sort_column": sort_column,
            "min_declares": min_declares,
            "top_n": top_n,
            "group_by": group_by,
            "selected_charts": list(selected_charts or []),
            "include_charts": include_charts,
        },
    )


def head_to_head(
    club_or_tournament: str,
    clubs: Optional[Sequence[str]] = None,
    players: Optional[Sequence[str]] = None,
    pairs: Optional[Sequence[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_column: str = "Declarer_Pct",
    pair_or_player: str = "player",
) -> Dict[str, Any]:
    return _request(
        "POST",
        "/acbl-stats/head-to-head",
        json={
            "club_or_tournament": club_or_tournament,
            "clubs": list(clubs or []),
            "players": list(players or []),
            "pairs": list(pairs or []),
            "start_date": start_date,
            "end_date": end_date,
            "sort_column": sort_column,
            "pair_or_player": pair_or_player,
        },
    )


def hand_records_report(
    club_or_tournament: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    brs_regex: str = "",
    sample_size: int = 100000,
    table_limit: int = 100,
    selected_charts: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    return _request(
        "POST",
        "/acbl-stats/hand-records",
        json={
            "club_or_tournament": club_or_tournament,
            "start_date": start_date,
            "end_date": end_date,
            "brs_regex": brs_regex,
            "sample_size": sample_size,
            "table_limit": table_limit,
            "selected_charts": list(selected_charts or []),
        },
    )


def table_to_frame(table: Optional[Dict[str, Any]]) -> pl.DataFrame:
    if not table or not table.get("rows"):
        columns = table.get("columns") if table else None
        return pl.DataFrame({col: [] for col in columns}) if columns else pl.DataFrame()
    # Scan every row. Club lookup has date strings that appear after a long
    # run of nulls; the default infer_schema_length=100 then rejects them.
    return pl.DataFrame(table["rows"], strict=False, infer_schema_length=None)
