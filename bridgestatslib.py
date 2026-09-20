"""Headless BridgeStats library: parquet discovery, filters, reports, DuckDB SQL.

Streamlit and MortyBridgeMCP must not import this module. Only the FastAPI
server imports it.
"""

from __future__ import annotations

import datetime
import json
import math
import os
import pathlib
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import polars as pl

import bridge_api_common as api_common

DATA_DIR_ENV = "BRIDGESTATS_DATA_DIR"
EXTRA_DATA_DIR_ENV = "BRIDGESTATS_EXTRA_DATA_DIR"

DEFAULT_SQL_ROW_LIMIT = api_common.DEFAULT_SQL_ROW_LIMIT
MAX_SQL_ROW_LIMIT = api_common.MAX_SQL_ROW_LIMIT
MAX_TABLE_ROWS = 500
MAX_LOOKUP_ROWS = 2000
MAX_CHART_BINS = 100
CON_REGISTER_NAME = "self"
FUZZY_NAME_THRESHOLD = 0.72
MIN_FUZZY_SUBSTRING_LEN = 3

BOARD_RESULT_COLUMNS = (
    "Club",
    "session_id",
    "Date",
    "Declarer_Direction",
    "Declarer",
    "Dummy",
    "OnLead",
    "NotOnLead",
    "Declarer_Name",
    "Player_ID_N",
    "Player_ID_E",
    "Player_ID_S",
    "Player_ID_W",
    "Player_Name_N",
    "Player_Name_E",
    "Player_Name_S",
    "Player_Name_W",
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
    "HandRecordBoard",
    "Board",
    "Result",
    "BidLvl",
    "BidSuit",
    "Dbl",
    "Vul",
    "ContractType",
    "PBN",
)

BOARD_RESULT_OPTIONAL_COLUMNS = (
    "Club",
    "Declarer",
    "Player_Name_N",
    "Player_Name_E",
    "Player_Name_S",
    "Player_Name_W",
)

HAND_RECORD_COLUMNS = (
    "PBN",
    "HandRecordBoard",
    "game_date",
    "session_id",
    "ParScore",
    "CT_N_S",
    "CT_N_H",
    "CT_N_D",
    "CT_N_C",
    "CT_N_N",
    "DD_N_C",
    "DD_N_D",
    "DD_N_H",
    "DD_N_S",
    "DD_N_N",
    "SL_N_C",
    "SL_N_D",
    "SL_N_H",
    "SL_N_S",
    "SL_N_ML_SJ",
    "HCP_NS",
    "HCP_EW",
    "HCP_N",
    "HCP_E",
    "HCP_S",
    "HCP_W",
    "QT_N",
    "QT_E",
    "QT_S",
    "QT_W",
    "QT_NS",
    "QT_EW",
    "DP_N",
    "DP_N_C",
    "DP_N_D",
    "DP_N_H",
    "DP_N_S",
    "DP_NS",
    "DP_EW",
)

SORT_OPTIONS = [
    "Declarer_Pct",
    "Score_Declarer",
    "DD_Score_Declarer",
    "ParScore",
    "EV_Score_Declarer",
    "EV_Max_Declarer",
    "DD_GE",
    "ParScore_GE",
    "Tricks_DD_Diff",
    "ParScore_DD_Diff",
    "Score_Declarer_DD_Diff",
    "OverTricks",
    "JustMade",
    "UnderTricks",
    "EV_Score_Declarer_Diff",
    "EV_Max_Declarer_Diff",
    "MP_Par_Pct_Declarer",
    "MP_EV_Pct_Declarer",
    "MP_EV_Max_Pct_Declarer",
    "MP_EV_Pct_Declarer_Diff",
    "MP_EV_Max_Pct_Declarer_Diff",
    "MP_EV_ParScore_Pct_Diff",
    "MP_EV_ParScore_Pct_Max_Diff",
]

SOURCE_FILES: Dict[str, Tuple[str, Tuple[str, ...], Tuple[str, ...]]] = {
    "club_board_results": (
        "acbl_club_board_results_augmented.parquet",
        BOARD_RESULT_COLUMNS,
        BOARD_RESULT_OPTIONAL_COLUMNS,
    ),
    "tournament_board_results": (
        "acbl_tournament_board_results_augmented.parquet",
        BOARD_RESULT_COLUMNS,
        BOARD_RESULT_OPTIONAL_COLUMNS,
    ),
    "club_hand_records": (
        "acbl_club_hand_records_augmented_narrow.parquet",
        HAND_RECORD_COLUMNS,
        (),
    ),
    "tournament_hand_records": (
        "acbl_tournament_hand_records_augmented_narrow.parquet",
        HAND_RECORD_COLUMNS,
        (),
    ),
    "player_info": ("acbl_player_info.parquet", ("acbl_number", "last_name"), ()),
    "clubs": ("acbl_club_clubs_cleaned.parquet", ("id", "name"), ()),
}

BOARD_RESULT_SOURCES = ("club_board_results", "tournament_board_results")
HAND_RECORD_SOURCES = ("club_hand_records", "tournament_hand_records")
SQL_VIEW_NAMES = frozenset(SOURCE_FILES) | {CON_REGISTER_NAME}
_DIRECTION_MACROS = (
    ("{Player_Direction}", "player_direction"),
    ("{Partner_Direction}", "partner_direction"),
    ("{Pair_Direction}", "pair_direction"),
    ("{Opponent_Pair_Direction}", "opponent_pair_direction"),
)
_VALUE_MACROS = (
    "Player_ID",
    "Players",
    "Players_List",
    "Clubs",
    "Pairs",
    "Start_Date",
    "End_Date",
    "Sort_Column",
    "Min_Declares",
    "Top_N",
    "Board_Source",
    "Hand_Source",
    "Date_Filter",
    "Club_Filter",
    "Player_Filter",
    "Pair_Filter",
    "Hand_Date_Filter",
)
_FILTER_MACROS = (
    "{Date_Filter}",
    "{Club_Filter}",
    "{Player_Filter}",
    "{Pair_Filter}",
    "{Hand_Date_Filter}",
)
_ALLOWED_SORT_COLUMNS = frozenset(SORT_OPTIONS) | {"Count", "Declarer", "session_id"}
_FAVORITES_CACHE: Optional[Dict[str, Any]] = None


def resolve_data_path() -> pathlib.Path:
    """Primary data directory. Env override wins; default is <repo>/data."""
    env = os.environ.get(DATA_DIR_ENV)
    if env:
        return pathlib.Path(env)
    for candidate in api_common.data_root_search_paths("acbl"):
        if candidate.exists():
            return candidate
    return pathlib.Path(__file__).resolve().parent / "data"


def data_search_roots() -> List[pathlib.Path]:
    """Places to look for pipeline parquets. Large Stage 3c files stay on E: / acbl-pipeline."""
    roots: List[pathlib.Path] = []
    for key in (DATA_DIR_ENV, EXTRA_DATA_DIR_ENV):
        env = os.environ.get(key)
        if env:
            roots.append(pathlib.Path(env))
    roots.extend(api_common.data_root_search_paths("acbl"))
    roots.append(pathlib.Path(__file__).resolve().parent / "data")
    for extra in (
        pathlib.Path("/app/extra-data"),
        pathlib.Path("/data/_wslc_host/acbl-stage/club_results_parquet"),
        pathlib.Path("e:/bridge/data/acbl"),
        pathlib.Path(__file__).resolve().parent.parent / "acbl-pipeline" / "club_results_parquet",
    ):
        if extra.exists():
            roots.append(extra)
    seen: set[str] = set()
    unique: List[pathlib.Path] = []
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def source_probe_columns(required, optional=()) -> Tuple[str, ...]:
    """Columns used to reject stale parquets. Skip source-optional names (Club)."""
    return tuple(col for col in required if col not in optional)[:2]


def resolve_data_file(*names, required_columns=()):
    """Return the first existing path among names in the search roots.

    If required_columns is set, skip files whose schema is missing those
    current pipeline names (stale local copies).
    """
    tried = []
    for root in data_search_roots():
        for name in names:
            path = root / name
            if not path.is_file():
                tried.append(str(path))
                continue
            if required_columns:
                schema = pl.read_parquet_schema(str(path))
                missing = [col for col in required_columns if col not in schema]
                if missing:
                    tried.append(f"{path} (missing columns: {', '.join(missing)})")
                    continue
            return path
    raise FileNotFoundError("Missing data file (tried): " + "; ".join(tried))


def _select_columns(schema, wanted, optional=()):
    missing = [col for col in wanted if col not in schema and col not in optional]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    return [col for col in wanted if col in schema]


def normalize_board_results(df):
    """Compute pair keys and diffs from current pipeline columns only."""
    if "Declarer" not in df.columns:
        needed = {
            "Declarer_Direction",
            "Player_ID_N",
            "Player_ID_E",
            "Player_ID_S",
            "Player_ID_W",
        }
        if not needed.issubset(df.columns):
            raise ValueError(
                "Declarer is required, or Declarer_Direction plus Player_ID_N/E/S/W"
            )
        df = df.with_columns(
            pl.struct(
                [
                    "Declarer_Direction",
                    "Player_ID_N",
                    "Player_ID_E",
                    "Player_ID_S",
                    "Player_ID_W",
                ]
            )
            .map_elements(
                lambda r: None
                if r["Declarer_Direction"] is None
                else r[f"Player_ID_{r['Declarer_Direction']}"],
                return_dtype=pl.String,
            )
            .alias("Declarer")
        )
    df = df.with_columns(
        [
            (pl.col("Tricks") - pl.col("DD_Tricks")).alias("Tricks_DD_Diff"),
            (pl.col("Score_Declarer") - pl.col("DD_Score_Declarer")).alias(
                "Score_Declarer_DD_Diff"
            ),
            (pl.col("ParScore") - pl.col("DD_Score_Declarer")).alias("ParScore_DD_Diff"),
            (pl.col("EV_Score_Declarer") - pl.col("Score_Declarer")).alias(
                "EV_Score_Declarer_Diff"
            ),
            (pl.col("EV_Max_Declarer") - pl.col("Score_Declarer")).alias(
                "EV_Max_Declarer_Diff"
            ),
            (pl.col("MP_EV_Pct_Declarer") - pl.col("Declarer_Pct")).alias(
                "MP_EV_Pct_Declarer_Diff"
            ),
            (pl.col("MP_EV_Max_Pct_Declarer") - pl.col("Declarer_Pct")).alias(
                "MP_EV_Max_Pct_Declarer_Diff"
            ),
            (pl.col("MP_EV_Max_Pct_Declarer") - pl.col("MP_Par_Pct_Declarer")).alias(
                "MP_EV_ParScore_Pct_Diff"
            ),
            (pl.col("MP_EV_Max_Pct_Declarer") - pl.col("MP_Par_Pct_Declarer")).alias(
                "MP_EV_ParScore_Pct_Max_Diff"
            ),
            (pl.col("Declarer").cast(pl.Utf8) + "_" + pl.col("Dummy").cast(pl.Utf8)).alias(
                "Declarer_Pair"
            ),
            (pl.col("OnLead").cast(pl.Utf8) + "_" + pl.col("NotOnLead").cast(pl.Utf8)).alias(
                "Defender_Pair"
            ),
        ]
    )
    for col in (
        "Declarer",
        "Dummy",
        "OnLead",
        "NotOnLead",
        "Player_ID_N",
        "Player_ID_E",
        "Player_ID_S",
        "Player_ID_W",
        "session_id",
    ):
        if col in df.columns:
            df = df.with_columns(pl.col(col).cast(pl.Utf8))
    return df


def normalize_hand_records(df):
    return df


def apply_filters(board_results_df, clubs, players, pairs, start_date, end_date):
    """Filter board results. Works on DataFrame or LazyFrame."""
    df = board_results_df
    columns = (
        set(df.collect_schema().names())
        if isinstance(df, pl.LazyFrame)
        else set(df.columns)
    )

    if clubs and "Club" in columns:
        club_list = [int(club) for club in clubs]
        df = df.filter(pl.col("Club").is_in(club_list))

    if players:
        player_list = [str(p) for p in players]
        player_columns = []
        for col_name in ("Player_ID_N", "Player_ID_E", "Player_ID_S", "Player_ID_W"):
            if col_name in columns:
                player_columns.append(pl.col(col_name).cast(pl.Utf8).is_in(player_list))
        if player_columns:
            player_filter = player_columns[0]
            for col_filter in player_columns[1:]:
                player_filter = player_filter | col_filter
            df = df.filter(player_filter)

    if pairs and {"Declarer", "Dummy"}.issubset(columns):
        pair_condition = None
        for pair in pairs:
            p1, p2 = pair.split("_")
            current = (
                (pl.col("Declarer").cast(pl.Utf8) == p1)
                & (pl.col("Dummy").cast(pl.Utf8) == p2)
            ) | (
                (pl.col("Declarer").cast(pl.Utf8) == p2)
                & (pl.col("Dummy").cast(pl.Utf8) == p1)
            )
            pair_condition = (
                current if pair_condition is None else pair_condition | current
            )
        if pair_condition is not None:
            df = df.filter(pair_condition)

    if start_date and end_date and "Date" in columns:
        start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        df = df.filter(
            (pl.col("Date").cast(pl.Date) >= start_date_obj)
            & (pl.col("Date").cast(pl.Date) <= end_date_obj)
        )
    return df


def apply_regex_filter(hand_records_df, brs_regex, sample_size=100000):
    """Apply regex filter and sampling using pure Polars operations."""
    df = hand_records_df
    if brs_regex:
        df = df.filter(pl.col("PBN").str.contains(brs_regex))
    if df.height > sample_size:
        df = df.sample(n=sample_size)
    return df


def sql_literal_list(values: Sequence[Any]) -> str:
    return ",".join("'" + str(value).replace("'", "''") + "'" for value in values)


def validate_sort_column(sort_column: str) -> str:
    name = str(sort_column or "Declarer_Pct")
    if name not in _ALLOWED_SORT_COLUMNS:
        raise ValueError(f"Unsupported sort column {name!r}")
    return name


def process_sql_macros(sql: str, meta: Optional[Dict[str, Any]] = None) -> str:
    """Replace postmortem-style and filter macros. Missing filter snippets become empty."""
    payload = meta or {}
    for macro, key in _DIRECTION_MACROS:
        value = payload.get(key)
        if value is None:
            value = payload.get(macro)
        if value is None or str(value) == "":
            continue
        sql = sql.replace(macro, str(value))
    for key in _VALUE_MACROS:
        macro = "{" + key + "}"
        if key in payload:
            value = payload[key]
        elif macro in payload:
            value = payload[macro]
        else:
            continue
        if value is None:
            continue
        sql = sql.replace(macro, str(value))
    for macro in _FILTER_MACROS:
        sql = sql.replace(macro, "")
    return sql


def reject_unresolved_direction_macros(sql: str) -> None:
    leftover = [macro for macro, _key in _DIRECTION_MACROS if macro in sql]
    if leftover:
        raise ValueError("Unresolved SQL macro: " + ", ".join(leftover))


def expand_sql(sql: str, meta: Optional[Dict[str, Any]] = None) -> str:
    """Expand macros with report defaults so sidecar SQL works without a full meta dict."""
    payload = build_report_meta()
    if meta:
        payload.update(meta)
    expanded = process_sql_macros((sql or "").strip().rstrip(";"), payload)
    reject_unresolved_direction_macros(expanded)
    return expanded


def build_report_meta(
    *,
    clubs: Sequence[str] = (),
    players: Sequence[str] = (),
    pairs: Sequence[str] = (),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_column: str = "Declarer_Pct",
    min_declares: int = 0,
    top_n: int = 100,
    club_or_tournament: str = "club",
    pair_direction: Optional[str] = None,
    opponent_pair_direction: Optional[str] = None,
    player_direction: Optional[str] = None,
    partner_direction: Optional[str] = None,
) -> Dict[str, Any]:
    sort_column = validate_sort_column(sort_column)
    player_ids = [str(player) for player in players]
    club_ids = [str(club) for club in clubs]
    pair_ids = [str(pair) for pair in pairs]
    player_list_sql = sql_literal_list(player_ids) if player_ids else ""
    club_list_sql = sql_literal_list(club_ids) if club_ids else ""
    pair_list_sql = sql_literal_list(pair_ids) if pair_ids else ""
    date_filter = (
        f"AND Date BETWEEN '{start_date}' AND '{end_date}'"
        if start_date and end_date
        else ""
    )
    hand_date_filter = (
        f"AND game_date BETWEEN '{start_date}' AND '{end_date}'"
        if start_date and end_date
        else ""
    )
    club_filter = (
        f"AND CAST(Club AS VARCHAR) IN ({club_list_sql})" if club_list_sql else ""
    )
    player_filter = ""
    if player_list_sql:
        seats = " OR ".join(
            f"CAST({col} AS VARCHAR) IN ({player_list_sql})"
            for col in ("Player_ID_N", "Player_ID_E", "Player_ID_S", "Player_ID_W")
        )
        player_filter = f"AND ({seats})"
    pair_filter = ""
    if pair_list_sql:
        pair_filter = (
            "AND (CONCAT(CAST(Declarer AS VARCHAR), '_', CAST(Dummy AS VARCHAR)) "
            f"IN ({pair_list_sql}) OR "
            "CONCAT(CAST(Dummy AS VARCHAR), '_', CAST(Declarer AS VARCHAR)) "
            f"IN ({pair_list_sql}))"
        )
    try:
        board_source = board_results_source(club_or_tournament)
    except ValueError:
        board_source = "club_board_results"
    try:
        hand_source = hand_records_source(club_or_tournament)
    except ValueError:
        hand_source = "club_hand_records"
    return {
        "player_direction": player_direction,
        "partner_direction": partner_direction,
        "pair_direction": pair_direction,
        "opponent_pair_direction": opponent_pair_direction,
        "Player_ID": player_ids[0] if player_ids else "",
        "Players": player_list_sql,
        "Players_List": player_list_sql,
        "Clubs": club_list_sql,
        "Pairs": pair_list_sql,
        "Start_Date": start_date or "",
        "End_Date": end_date or "",
        "Sort_Column": sort_column,
        "Min_Declares": str(int(min_declares)),
        "Top_N": str(int(top_n)),
        "Board_Source": board_source,
        "Hand_Source": hand_source,
        "Date_Filter": date_filter,
        "Club_Filter": club_filter,
        "Player_Filter": player_filter,
        "Pair_Filter": pair_filter,
        "Hand_Date_Filter": hand_date_filter,
    }


def infer_pair_direction(df: pl.DataFrame, player_id: str) -> Tuple[Optional[str], Optional[str]]:
    counts = {"NS": 0, "EW": 0}
    for col, pair in (
        ("Player_ID_N", "NS"),
        ("Player_ID_S", "NS"),
        ("Player_ID_E", "EW"),
        ("Player_ID_W", "EW"),
    ):
        if col in df.columns:
            counts[pair] += int(df.select(pl.col(col).cast(pl.Utf8).eq(player_id).sum()).item())
    if counts["NS"] == 0 and counts["EW"] == 0:
        return None, None
    if counts["NS"] >= counts["EW"]:
        return "NS", "EW"
    return "EW", "NS"


def favorites_file_path() -> pathlib.Path:
    env = os.environ.get("BRIDGESTATS_FAVORITES")
    if env:
        return pathlib.Path(env)
    return pathlib.Path(__file__).resolve().parent / "default.favorites.json"


def load_favorites_payload() -> Dict[str, Any]:
    global _FAVORITES_CACHE
    if _FAVORITES_CACHE is not None:
        return _FAVORITES_CACHE
    path = favorites_file_path()
    if not path.is_file():
        raise FileNotFoundError(f"Required configuration file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    _FAVORITES_CACHE = payload
    return payload


def flatten_favorites(payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    return api_common.flatten_favorites_payload(payload or load_favorites_payload())


def list_favorites(favorite_id: Optional[str] = None) -> Dict[str, Any]:
    return api_common.select_favorites(flatten_favorites(), favorite_id)


def get_favorite(favorite_id: str) -> Dict[str, Any]:
    listed = list_favorites(favorite_id)
    return listed["favorites"][0]


def execute_sql_on_frame(
    df: pl.DataFrame,
    sql: str,
    meta: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    source: str = CON_REGISTER_NAME,
) -> Dict[str, Any]:
    sql, limit = api_common.prepare_sql(expand_sql(sql, meta), source, limit)

    def _setup(con) -> None:
        con.register(CON_REGISTER_NAME, df)
        if source != CON_REGISTER_NAME:
            con.register(source, df)

    result, truncated = api_common.truncate_frame(
        api_common.run_duckdb_sql(sql, _setup), limit
    )
    table = frame_to_table(result)
    table.update({"sql": sql, "source": source, "truncated": truncated})
    return table


def run_favorite(
    favorite_id: str,
    meta: Optional[Dict[str, Any]] = None,
    df: Optional[pl.DataFrame] = None,
    source: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    favorite = get_favorite(favorite_id)
    payload = build_report_meta()
    if meta:
        payload.update(meta)
    sql = favorite["statements"][0]["sql"]
    resolved_source = source or process_sql_macros(
        favorite.get("source") or "{Board_Source}", payload
    )
    if resolved_source.startswith("{") or resolved_source not in SOURCE_FILES:
        resolved_source = payload.get("Board_Source") or "club_board_results"
    if df is not None:
        return execute_sql_on_frame(
            df, sql, meta=payload, limit=limit, source=resolved_source
        )
    return run_sql(sql, resolved_source, limit=limit or DEFAULT_SQL_ROW_LIMIT, meta=payload)


def player_position_frequency(df, players):
    """Boards sat by seat. Passed-out boards have no Declarer/Dummy/OnLead/NotOnLead."""
    if not players:
        return pl.DataFrame()
    meta = build_report_meta(players=players)
    return table_to_frame(run_favorite("Player_Position_Frequency", meta, df=df))


def load_board_results(
    filename, clubs=(), players=(), pairs=(), start_date=None, end_date=None
):
    """Column-project, filter in the scan, then collect the slice."""
    path = str(filename)
    schema = pl.read_parquet_schema(path)
    columns = _select_columns(
        schema, BOARD_RESULT_COLUMNS, BOARD_RESULT_OPTIONAL_COLUMNS
    )
    lf = pl.scan_parquet(path).select(columns)
    lf = apply_filters(lf, list(clubs), list(players), [], start_date, end_date)
    df = lf.collect()
    df = normalize_board_results(df)
    if pairs:
        df = apply_filters(df, [], [], list(pairs), None, None)
    return df


def load_hand_records(filename):
    path = str(filename)
    schema = pl.read_parquet_schema(path)
    columns = _select_columns(schema, HAND_RECORD_COLUMNS)
    df = pl.scan_parquet(path).select(columns).collect()
    return normalize_hand_records(df)


def load_player_name_dict():
    path = resolve_data_file("acbl_player_info.parquet")
    df = pl.read_parquet(path, columns=["acbl_number", "first_name", "last_name"])
    df = df.with_columns(
        [
            pl.col("acbl_number").cast(pl.Utf8),
            pl.col("first_name").fill_null(""),
            pl.col("last_name").fill_null(""),
        ]
    )
    names = (df["first_name"] + " " + df["last_name"]).str.strip_chars()
    return dict(zip(df["acbl_number"].to_list(), names.to_list()))


def load_player_info_df(filename=None):
    path = filename or resolve_data_file("acbl_player_info.parquet")
    return pl.read_parquet(path)


def load_club_df(filename=None):
    path = filename or resolve_data_file("acbl_club_clubs_cleaned.parquet")
    return pl.read_parquet(path)


def load_club_hand_records(filename):
    return load_hand_records(filename)


def load_tournament_hand_records(filename):
    return load_hand_records(filename)


def load_club_board_results(filename, **kwargs):
    return load_board_results(filename, **kwargs)


def load_tournament_board_results(filename, **kwargs):
    return load_board_results(filename, **kwargs)


def board_results_source(club_or_tournament: str) -> str:
    kind = (club_or_tournament or "").lower()
    if kind == "club":
        return "club_board_results"
    if kind == "tournament":
        return "tournament_board_results"
    raise ValueError("club_or_tournament must be 'club' or 'tournament'")


def hand_records_source(club_or_tournament: str) -> str:
    kind = (club_or_tournament or "").lower()
    if kind == "club":
        return "club_hand_records"
    if kind == "tournament":
        return "tournament_hand_records"
    raise ValueError("club_or_tournament must be 'club' or 'tournament'")


def resolve_source_path(source: str) -> pathlib.Path:
    if source not in SOURCE_FILES:
        raise ValueError(
            f"Unknown source {source!r}. Expected one of: {', '.join(SOURCE_FILES)}"
        )
    filename, required, optional = SOURCE_FILES[source]
    return resolve_data_file(
        filename, required_columns=source_probe_columns(required, optional)
    )


def add_board_scoring_columns(df: pl.DataFrame) -> pl.DataFrame:
    exprs = []
    if {"Tricks", "DD_Tricks"}.issubset(df.columns):
        exprs.append(
            pl.when(pl.col("Tricks") >= pl.col("DD_Tricks"))
            .then(1)
            .otherwise(0)
            .alias("DD_GE")
        )
    if {"Score_Declarer", "ParScore"}.issubset(df.columns):
        exprs.append(
            pl.when(pl.col("Score_Declarer") >= pl.col("ParScore"))
            .then(1)
            .otherwise(0)
            .alias("ParScore_GE")
        )
    if "Result" in df.columns:
        exprs.extend(
            [
                pl.when(pl.col("Result") > 0).then(1).otherwise(0).alias("OverTricks"),
                pl.when(pl.col("Result") == 0).then(1).otherwise(0).alias("JustMade"),
                pl.when(pl.col("Result") < 0).then(1).otherwise(0).alias("UnderTricks"),
            ]
        )
    if exprs:
        df = df.with_columns(exprs)
    return df


def attach_pair_player_names(
    df: pl.DataFrame, player_names: Optional[Dict[str, str]] = None
) -> pl.DataFrame:
    names = player_names or {}
    if "Declarer_Pair" in df.columns:
        parts = pl.col("Declarer_Pair").cast(pl.Utf8).str.split("_")
        if "Player1" not in df.columns:
            p1 = parts.list.get(0)
            if names:
                df = df.with_columns(
                    p1.replace_strict(names, default=p1).alias("Player1")
                )
            else:
                df = df.with_columns(p1.alias("Player1"))
        if "Player2" not in df.columns:
            p2 = parts.list.get(1)
            if names:
                df = df.with_columns(
                    p2.replace_strict(names, default=p2).alias("Player2")
                )
            else:
                df = df.with_columns(p2.alias("Player2"))
        if "Players" not in df.columns:
            df = df.with_columns(
                pl.concat_list([pl.col("Player1"), pl.col("Player2")]).alias("Players")
            )
    if "Count" not in df.columns:
        df = df.with_columns(pl.lit(0).alias("Count"))
    return df.select([col for col in df.columns if not col.startswith("__")])


def dedupe_boards_by_pbn_declarer(df: pl.DataFrame) -> pl.DataFrame:
    if "PBN" not in df.columns or "Declarer" not in df.columns:
        return df
    sort_cols = [col for col in ("PBN", "Declarer", "HandRecordBoard") if col in df.columns]
    return df.sort(sort_cols).unique(
        subset=["PBN", "Declarer"], maintain_order=True, keep="last"
    )


def identical_boards_comparison(df: pl.DataFrame, sort_column: str) -> Dict[str, Any]:
    needed = {"Date", "session_id", "HandRecordBoard"}
    empty = {
        "identical_boards": frame_to_table(pl.DataFrame()),
        "session_means": frame_to_table(pl.DataFrame()),
        "n_boards": 0,
        "n_sessions": 0,
    }
    if not needed.issubset(df.columns) or df.height == 0:
        return empty
    meta = build_report_meta(sort_column=sort_column, top_n=MAX_TABLE_ROWS)
    boards = run_favorite("Identical_Boards", meta, df=df, limit=MAX_TABLE_ROWS)
    board_df = table_to_frame(boards)
    if board_df.height == 0:
        return empty
    means = run_favorite(
        "Identical_Boards_Session_Means", meta, df=df, limit=MAX_TABLE_ROWS
    )
    n_boards = 0
    n_sessions = 0
    if "ngroup" in board_df.columns:
        n_boards = int(board_df.select(pl.col("ngroup").max()).item() or 0) + 1
    if "session_id" in board_df.columns:
        n_sessions = board_df.select(pl.col("session_id")).n_unique()
    return {
        "identical_boards": boards,
        "session_means": means,
        "n_boards": n_boards,
        "n_sessions": n_sessions,
    }


def pair_head_to_head(df: pl.DataFrame, sort_column: str) -> pl.DataFrame:
    if "HandRecordBoard" not in df.columns or "Declarer" not in df.columns:
        return pl.DataFrame()
    meta = build_report_meta(sort_column=sort_column, top_n=MAX_TABLE_ROWS)
    return table_to_frame(
        run_favorite("Pair_Head_To_Head", meta, df=df, limit=MAX_TABLE_ROWS)
    )


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_value(value.item())
        except Exception:
            return str(value)
    return value


def frame_to_table(df: Optional[pl.DataFrame], limit: Optional[int] = None) -> Dict[str, Any]:
    if df is None:
        return {"columns": [], "rows": [], "row_count": 0, "truncated": False}
    truncated = False
    if limit is not None and df.height > limit:
        truncated = True
        df = df.head(limit)
    rows = [{key: _json_value(value) for key, value in rec.items()} for rec in df.iter_rows(named=True)]
    return {
        "columns": list(df.columns),
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }


def table_to_frame(table: Optional[Dict[str, Any]]) -> pl.DataFrame:
    if not table or not table.get("rows"):
        columns = table.get("columns") if table else None
        return pl.DataFrame({col: [] for col in columns}) if columns else pl.DataFrame()
    # Scan every row. Club lookup has date strings that appear after a long
    # run of nulls; the default infer_schema_length=100 then rejects them.
    return pl.DataFrame(table["rows"], strict=False, infer_schema_length=None)


def _value_counts(series: pl.Series) -> Dict[str, float]:
    total = max(series.len(), 1)
    work = series.drop_nulls()
    if work.dtype in (pl.Float32, pl.Float64):
        chosen = None
        for places in (2, 1, 0, -1):
            rounded = work.round(places)
            counts = rounded.value_counts()
            if counts.height <= MAX_CHART_BINS:
                chosen = counts
                break
        work_counts = chosen if chosen is not None else work.round(0).value_counts()
        value_col = work_counts.columns[0]
        count_col = work_counts.columns[1]
        work_counts = work_counts.sort(value_col)
    else:
        work_counts = work.value_counts().sort(work.name)
        value_col = work_counts.columns[0]
        count_col = work_counts.columns[1]
    return {
        str(_json_value(row[value_col])): float(row[count_col]) / total
        for row in work_counts.iter_rows(named=True)
    }


def chart_series(
    df: pl.DataFrame, selected_charts: Sequence[str]
) -> List[Dict[str, Any]]:
    if df.height == 0:
        return [{"kind": "empty", "title": "No data available for charts."}]
    available: List[List[str]] = []
    for chart in selected_charts:
        parts = [part for part in chart.replace(" ", "").split(",") if part]
        if parts and all(col in df.columns for col in parts):
            available.append(parts)
    payloads: List[Dict[str, Any]] = []
    declarer_groups = pl.DataFrame()
    if {"Declarer", "Declarer_Name"}.issubset(df.columns):
        declarer_groups = df.group_by(["Declarer", "Declarer_Name"]).agg(pl.len())
        payloads.append(
            {
                "kind": "info",
                "title": (
                    f"Selected: Unique declarers:{declarer_groups.height} "
                    f"rows:{df.height} charts:{available}"
                ),
            }
        )
    if 0 < declarer_groups.height <= 10:
        for parts in available:
            if len(parts) == 1:
                col = parts[0]
                series: Dict[str, Dict[str, float]] = {}
                for row in declarer_groups.iter_rows(named=True):
                    label = f"({row['Declarer']},{row['Declarer_Name']})"
                    subset = df.filter(pl.col("Declarer") == row["Declarer"])[col]
                    series[label] = _value_counts(subset)
                payloads.append(
                    {
                        "kind": "bar",
                        "title": f"Frequency Percentage of {col}",
                        "columns": parts,
                        "series": series,
                    }
                )
            else:
                payloads.append(
                    {
                        "kind": "hist",
                        "title": f"Histogram of {', '.join(parts)}",
                        "columns": parts,
                        "series": {col: _value_counts(df[col]) for col in parts},
                    }
                )
        return payloads
    for parts in available:
        if len(parts) == 3:
            cross = (
                df.group_by([parts[0], parts[1]])
                .agg(pl.col(parts[2]).mean())
                .pivot(values=parts[2], index=parts[0], columns=parts[1])
            )
            index_col = cross.columns[0]
            payloads.append(
                {
                    "kind": "heatmap",
                    "title": f"{parts[2]} by {parts[0]} x {parts[1]}",
                    "columns": parts,
                    "index": [str(_json_value(v)) for v in cross[index_col].to_list()],
                    "x_labels": [str(c) for c in cross.columns[1:]],
                    "values": [
                        [_json_value(v) for v in row]
                        for row in cross.select(cross.columns[1:]).iter_rows()
                    ],
                    "zlabel": parts[2],
                }
            )
        else:
            payloads.append(
                {
                    "kind": "bar",
                    "title": (
                        f"Frequency of {', '.join(parts)} values. "
                        f"{df.height} observations."
                    ),
                    "columns": parts,
                    "series": {col: _value_counts(df[col]) for col in parts},
                }
            )
    return payloads


def dataset_info() -> Dict[str, Any]:
    sources: Dict[str, Any] = {}
    for source, (filename, required, optional) in SOURCE_FILES.items():
        try:
            path = resolve_data_file(
                filename, required_columns=source_probe_columns(required, optional)
            )
            schema = pl.read_parquet_schema(str(path))
            sources[source] = {
                "available": True,
                "filename": filename,
                "path": str(path),
                "columns": list(schema.keys()),
                "column_count": len(schema),
            }
        except FileNotFoundError as exc:
            sources[source] = {
                "available": False,
                "filename": filename,
                "error": str(exc),
            }
    return {
        "service": "acbl-stats",
        "data_path": str(resolve_data_path()),
        "search_roots": [str(root) for root in data_search_roots()],
        "sources": sources,
        "sql_tables": list(SOURCE_FILES),
    }


def schema_columns(
    source: str, pattern: Optional[str] = None, limit: int = 200
) -> Dict[str, Any]:
    path = resolve_source_path(source)
    schema = pl.read_parquet_schema(str(path))
    items = [{"name": name, "dtype": str(dtype)} for name, dtype in schema.items()]
    if pattern:
        regex = re.compile(pattern, re.IGNORECASE)
        items = [item for item in items if regex.search(item["name"])]
    limit = max(1, min(limit, 5000))
    return {
        "source": source,
        "path": str(path),
        "columns": items[:limit],
        "column_count": len(items),
        "truncated": len(items) > limit,
    }


def run_sql(
    sql: str,
    source: str,
    limit: int = DEFAULT_SQL_ROW_LIMIT,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if source not in SOURCE_FILES:
        raise ValueError(
            f"Unknown source {source!r}. Expected one of: {', '.join(SOURCE_FILES)}"
        )
    sql, limit = api_common.prepare_sql(expand_sql(sql, meta), source, limit)
    path = resolve_source_path(source)
    escaped = str(path).replace("'", "''")

    def _setup(con) -> None:
        con.execute(f"CREATE VIEW {source} AS SELECT * FROM read_parquet('{escaped}')")
        if source != CON_REGISTER_NAME:
            con.execute(f"CREATE VIEW {CON_REGISTER_NAME} AS SELECT * FROM {source}")

    result, truncated = api_common.truncate_frame(
        api_common.run_duckdb_sql(sql, _setup), limit
    )
    table = frame_to_table(result)
    table.update({"sql": sql, "source": source, "truncated": truncated})
    return table


def normalize_fuzzy_text(value: object) -> str:
    """Normalize accents, punctuation, whitespace, and case for fuzzy search."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def fuzzy_text_score(candidate: object, query: object) -> float:
    """Score a free-text candidate, preserving substring matches as exact."""
    haystack = normalize_fuzzy_text(candidate)
    needle = normalize_fuzzy_text(query)
    if not haystack or not needle:
        return 0.0
    if needle in haystack:
        return 1.0
    scores = [SequenceMatcher(None, needle, haystack).ratio()]
    candidate_tokens = haystack.split()
    query_word_count = max(1, len(needle.split()))
    for start in range(len(candidate_tokens)):
        window = " ".join(candidate_tokens[start : start + query_word_count])
        scores.append(SequenceMatcher(None, needle, window).ratio())
    return max(scores)


def _name_query_matches(candidate: object, query: object) -> bool:
    haystack = normalize_fuzzy_text(candidate)
    needle = normalize_fuzzy_text(query)
    if not haystack or not needle:
        return False
    if len(needle) < MIN_FUZZY_SUBSTRING_LEN:
        return needle in haystack.split() or haystack == needle
    return fuzzy_text_score(candidate, query) >= FUZZY_NAME_THRESHOLD


def _name_rank(display: object, last: object, query: object) -> tuple[float, int, int]:
    """Higher is better: fuzzy score, exact last name, last-name prefix."""
    needle = normalize_fuzzy_text(query)
    last_n = normalize_fuzzy_text(last)
    return (
        fuzzy_text_score(display, query),
        1 if last_n == needle else 0,
        1 if needle and last_n.startswith(needle) else 0,
    )


def filter_players_by_name(df: pl.DataFrame, names: Optional[str]) -> pl.DataFrame:
    """Elo-style fuzzy match on first+last name. Comma/semicolon separates OR queries.

    Matches are sorted best-first (score, exact last name, last-name prefix).
    """
    raw = (names or "").strip()
    if not raw or df.is_empty():
        return df
    queries = [part.strip() for part in re.split(r"[,;]", raw) if part.strip()]
    if not queries:
        return df
    work = df
    has_first = "first_name" in work.columns
    has_last = "last_name" in work.columns
    if not has_first and not has_last:
        return df
    first = (
        pl.col("first_name").cast(pl.Utf8).fill_null("") if has_first else pl.lit("")
    )
    last = pl.col("last_name").cast(pl.Utf8).fill_null("") if has_last else pl.lit("")
    work = work.with_columns((first + " " + last).str.strip_chars().alias("_display_name"))
    values = (
        work.select(pl.col("_display_name").drop_nulls().unique())
        .to_series()
        .to_list()
    )
    matched = [
        value
        for value in values
        if any(_name_query_matches(value, query) for query in queries)
    ]
    work = work.filter(pl.col("_display_name").is_in(matched))
    if work.is_empty():
        return work.drop("_display_name")
    last_values = (
        work["last_name"].cast(pl.Utf8).fill_null("").to_list()
        if has_last
        else [""] * work.height
    )
    ranks = [
        max(_name_rank(display, last_name, query) for query in queries)
        for display, last_name in zip(work["_display_name"].to_list(), last_values)
    ]
    work = (
        work.with_columns(
            [
                pl.Series("_name_score", [rank[0] for rank in ranks]),
                pl.Series("_exact_last", [rank[1] for rank in ranks]),
                pl.Series("_prefix_last", [rank[2] for rank in ranks]),
            ]
        )
        .sort(
            ["_name_score", "_exact_last", "_prefix_last", "last_name", "first_name"]
            if has_first
            else ["_name_score", "_exact_last", "_prefix_last", "last_name"],
            descending=[True, True, True, False, False] if has_first else [True, True, True, False],
        )
        .drop("_display_name", "_name_score", "_exact_last", "_prefix_last")
    )
    return work


def filter_players_by_number(
    df: pl.DataFrame, numbers: Optional[str], id_col: str
) -> pl.DataFrame:
    tokens = [token for token in (numbers or "").replace(",", " ").split() if token]
    if not tokens or df.is_empty() or id_col not in df.columns:
        return df
    return df.filter(pl.col(id_col).cast(pl.Utf8).is_in(tokens))


def player_lookup(
    clubs: Optional[str] = None,
    numbers: Optional[str] = None,
    names: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    df = load_player_info_df()
    casts = [pl.col("acbl_number").cast(pl.Utf8)]
    if "club" in df.columns:
        casts.append(pl.col("club").cast(pl.Utf8))
    df = df.with_columns(casts)
    if "mp_total" in df.columns:
        df = df.with_columns(pl.col("mp_total").cast(pl.Float64))
    clubs_regex = "|".join((clubs or "").replace(",", " ").split())
    if clubs_regex and "club" in df.columns:
        df = df.filter(pl.col("club").str.contains(clubs_regex))
    df = filter_players_by_number(df, numbers, "acbl_number")
    df = filter_players_by_name(df, names)
    drop_mp = [col for col in df.columns if col.startswith("mp_")]
    if drop_mp:
        df = df.drop(drop_mp)
    limit = max(1, min(limit, MAX_LOOKUP_ROWS))
    total = df.height
    return {
        "total": total,
        **frame_to_table(df, limit=limit),
    }


def club_lookup(
    clubs: Optional[str] = None,
    names: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    df = load_club_df().with_columns(pl.col("id").cast(pl.Utf8))
    clubs_regex = "|".join((clubs or "").replace(",", " ").split())
    names_regex = "|".join((names or "").split())
    if clubs_regex:
        df = df.filter(pl.col("id").str.contains(clubs_regex))
    if names_regex and "name" in df.columns:
        df = df.filter(pl.col("name").str.contains(names_regex, ignore_case=True))
    limit = max(1, min(limit, MAX_LOOKUP_ROWS))
    return {"total": df.height, **frame_to_table(df, limit=limit)}


def unknown_players(players: Sequence[str]) -> List[str]:
    if not players:
        return []
    names = load_player_name_dict()
    return [player for player in players if player not in names]


def _prepare_board_frames(
    club_or_tournament: str,
    clubs: Sequence[str],
    players: Sequence[str],
    pairs: Sequence[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> Tuple[str, pl.DataFrame, pl.DataFrame]:
    source = board_results_source(club_or_tournament)
    path = resolve_source_path(source)
    any_position = load_board_results(
        path,
        clubs=tuple(clubs),
        players=tuple(players),
        pairs=tuple(pairs),
        start_date=start_date,
        end_date=end_date,
    )
    if players:
        selected = any_position.filter(pl.col("Declarer").is_in([str(p) for p in players]))
    else:
        selected = any_position
    names = load_player_name_dict()
    selected = add_board_scoring_columns(selected)
    selected = attach_pair_player_names(selected, names)
    selected = dedupe_boards_by_pbn_declarer(selected)
    return source, any_position, selected


def board_results_report(
    club_or_tournament: str,
    clubs: Sequence[str] = (),
    players: Sequence[str] = (),
    pairs: Sequence[str] = (),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_column: str = "Declarer_Pct",
    min_declares: int = 0,
    top_n: int = 100,
    group_by: str = "Declarer",
    selected_charts: Optional[Sequence[str]] = None,
    include_charts: bool = True,
) -> Dict[str, Any]:
    unknown = unknown_players(list(players) + [part for pair in pairs for part in pair.split("_")])
    if unknown:
        raise ValueError("Unknown player(s): " + ", ".join(unknown))
    source, any_position, selected = _prepare_board_frames(
        club_or_tournament, clubs, players, pairs, start_date, end_date
    )
    if selected.height == 0:
        raise ValueError("No rows selected. Adjust club, player, pair, or date filters.")
    meta = build_report_meta(
        clubs=clubs,
        players=players,
        pairs=pairs,
        start_date=start_date,
        end_date=end_date,
        sort_column=sort_column,
        min_declares=min_declares,
        top_n=top_n,
        club_or_tournament=club_or_tournament,
    )
    if players:
        pair_direction, opponent_pair_direction = infer_pair_direction(
            any_position, str(players[0])
        )
        meta["pair_direction"] = pair_direction
        meta["opponent_pair_direction"] = opponent_pair_direction
    player_boards = []
    session_means = None
    position = None
    if players:
        position = run_favorite("Player_Position_Frequency", meta, df=any_position)
        boards = run_favorite(
            "Player_Boards", meta, df=selected, limit=MAX_TABLE_ROWS
        )
        boards_df = table_to_frame(boards)
        if boards_df.height and "Declarer" in boards_df.columns:
            for declarer in boards_df.select("Declarer").unique(maintain_order=True).to_series():
                player_df = boards_df.filter(pl.col("Declarer").eq(declarer))
                name = None
                if "Declarer_Name" in player_df.columns and player_df.height:
                    name = player_df.select("Declarer_Name").tail(1).row(0)[0]
                player_boards.append(
                    {
                        "declarer": declarer,
                        "declarer_name": name,
                        **frame_to_table(player_df, limit=MAX_TABLE_ROWS),
                    }
                )
        session_means = run_favorite(
            "Session_Leaderboard", meta, df=selected, limit=MAX_TABLE_ROWS
        )
        leaderboard_table = None
    else:
        favorite_id = (
            "Session_Leaderboard" if group_by == "session_id" else "Declarer_Leaderboard"
        )
        leaderboard_table = run_favorite(favorite_id, meta, df=selected, limit=top_n)
    charts = chart_series(selected, selected_charts or []) if include_charts else []
    if include_charts:
        pct_cols = [col for col in selected.columns if col.endswith("Pct") or col.endswith("Pct_Max")]
        if pct_cols:
            charts.extend(chart_series(selected.select(pct_cols), [",".join(pct_cols)]))
        diff_cols = [col for col in selected.columns if "Pct" in col and "Diff" in col]
        if diff_cols:
            charts.extend(chart_series(selected.select(diff_cols), [",".join(diff_cols)]))
    return {
        "source": source,
        "row_count": any_position.height,
        "selected_count": selected.height,
        "sort_column": sort_column,
        "position_frequency": position,
        "leaderboard": leaderboard_table,
        "player_boards": player_boards,
        "session_means": session_means,
        "charts": charts,
        "pair_or_player": "pair" if pairs else "player",
    }


def head_to_head(
    club_or_tournament: str,
    clubs: Sequence[str] = (),
    players: Sequence[str] = (),
    pairs: Sequence[str] = (),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_column: str = "Declarer_Pct",
    pair_or_player: str = "player",
) -> Dict[str, Any]:
    if len(players) < 2 and len(pairs) < 2:
        raise ValueError("Head-to-head needs at least two players or two pairs.")
    source, _any_position, selected = _prepare_board_frames(
        club_or_tournament, clubs, players, pairs, start_date, end_date
    )
    comparison = identical_boards_comparison(selected, sort_column)
    pair_table = None
    if pair_or_player == "pair" or pairs:
        pair_table = frame_to_table(pair_head_to_head(selected, sort_column), limit=MAX_TABLE_ROWS)
    return {
        "source": source,
        "selected_count": selected.height,
        "sort_column": sort_column,
        **comparison,
        "pair_head_to_head": pair_table,
    }


def _hand_records_for_players(
    df: pl.DataFrame,
    club_or_tournament: str,
    clubs: Sequence[str],
    players: Sequence[str],
    pairs: Sequence[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> pl.DataFrame:
    if not players and not pairs:
        return df
    unknown = unknown_players(
        list(players) + [part for pair in pairs for part in str(pair).split("_")]
    )
    if unknown:
        raise ValueError("Unknown player(s): " + ", ".join(unknown))
    boards = load_board_results(
        resolve_source_path(board_results_source(club_or_tournament)),
        clubs=tuple(clubs),
        players=tuple(players),
        pairs=tuple(pairs),
        start_date=start_date,
        end_date=end_date,
    )
    if boards.height == 0:
        raise ValueError("No boards found for the selected player filters.")
    if "PBN" in df.columns and "PBN" in boards.columns:
        keys = boards.select(pl.col("PBN").cast(pl.Utf8)).drop_nulls().unique()
        return df.with_columns(pl.col("PBN").cast(pl.Utf8)).join(keys, on="PBN", how="inner")
    if "session_id" in df.columns and "session_id" in boards.columns:
        keys = boards.select(pl.col("session_id").cast(pl.Utf8)).drop_nulls().unique()
        return df.with_columns(pl.col("session_id").cast(pl.Utf8)).join(
            keys, on="session_id", how="inner"
        )
    raise ValueError("Hand records cannot be filtered by player without PBN or session_id.")


def hand_records_report(
    club_or_tournament: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    brs_regex: str = "",
    sample_size: int = 100000,
    table_limit: int = 100,
    selected_charts: Optional[Sequence[str]] = None,
    clubs: Sequence[str] = (),
    players: Sequence[str] = (),
    pairs: Sequence[str] = (),
) -> Dict[str, Any]:
    source = hand_records_source(club_or_tournament)
    path = resolve_source_path(source)
    df = load_hand_records(path)
    source_count = df.height
    df = _hand_records_for_players(
        df, club_or_tournament, clubs, players, pairs, start_date, end_date
    )
    df = apply_regex_filter(df, brs_regex, sample_size)
    if "PBN" in df.columns:
        df = df.unique(subset=["PBN"])
    unique_hands = df.height
    if start_date and end_date and "game_date" in df.columns:
        start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        df = df.filter(
            (pl.col("game_date").cast(pl.Date) >= start_date_obj)
            & (pl.col("game_date").cast(pl.Date) <= end_date_obj)
        )
    df = df.select([col for col in df.columns if not col.startswith("__")])
    float_cols = [col for col in df.columns if df[col].dtype in (pl.Float32, pl.Float64)]
    if float_cols:
        df = df.with_columns([pl.col(col).round(2) for col in float_cols])
    meta = build_report_meta(
        clubs=clubs,
        players=players,
        pairs=pairs,
        start_date=start_date,
        end_date=end_date,
        top_n=table_limit,
        club_or_tournament=club_or_tournament,
    )
    table = run_favorite("Hand_Records_Sample", meta, df=df, limit=table_limit)
    return {
        "source": source,
        "row_count": source_count,
        "unique_hands": unique_hands,
        "selected_count": df.height,
        "sample_size": sample_size,
        "table": table,
        "charts": chart_series(df, selected_charts or []),
    }
