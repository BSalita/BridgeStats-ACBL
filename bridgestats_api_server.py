"""First-party REST API for ACBL BridgeStats historical analytics."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

import bridge_api_common as api_common
import bridgestatslib as service

API_BUILD_TAG = "2026-09-07-acbl-stats"
app = FastAPI(title="ACBL BridgeStats API", version="1.0.0")


class SqlRequest(BaseModel):
    sql: str
    source: str = "club_board_results"
    limit: int = 500
    meta: Optional[Dict[str, Any]] = None


class FavoriteRunRequest(BaseModel):
    source: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 500
    club_or_tournament: Optional[str] = None
    clubs: List[str] = Field(default_factory=list)
    players: List[str] = Field(default_factory=list)
    pairs: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class BoardResultsRequest(BaseModel):
    club_or_tournament: str
    clubs: List[str] = Field(default_factory=list)
    players: List[str] = Field(default_factory=list)
    pairs: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    sort_column: str = "Declarer_Pct"
    min_declares: int = 0
    top_n: int = 100
    group_by: str = "Declarer"
    selected_charts: List[str] = Field(default_factory=list)
    include_charts: bool = True


class HeadToHeadRequest(BaseModel):
    club_or_tournament: str
    clubs: List[str] = Field(default_factory=list)
    players: List[str] = Field(default_factory=list)
    pairs: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    sort_column: str = "Declarer_Pct"
    pair_or_player: str = "player"


class HandRecordsRequest(BaseModel):
    club_or_tournament: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    brs_regex: str = ""
    sample_size: int = 100000
    table_limit: int = 100
    selected_charts: List[str] = Field(default_factory=list)
    clubs: List[str] = Field(default_factory=list)
    players: List[str] = Field(default_factory=list)
    pairs: List[str] = Field(default_factory=list)


def _run(callable_, /, *args, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict:
    info = _run(service.dataset_info)
    return api_common.health_payload(
        info,
        service="acbl-stats-api",
        api_version=app.version,
        build_tag=API_BUILD_TAG,
    )


@app.get("/acbl-stats/dataset-info")
def dataset_info() -> dict:
    return _run(service.dataset_info)


@app.get("/acbl-stats/schema")
def schema(
    source: str,
    pattern: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=5000),
) -> dict:
    return _run(service.schema_columns, source, pattern=pattern, limit=limit)


@app.post("/acbl-stats/sql")
def sql(request: SqlRequest) -> dict:
    return _run(service.run_sql, request.sql, request.source, request.limit, meta=request.meta)


@app.get("/acbl-stats/favorites")
def favorites(id: Optional[str] = Query(None)) -> dict:
    return _run(service.list_favorites, id)


@app.post("/acbl-stats/favorites/{favorite_id}")
def run_favorite(favorite_id: str, request: FavoriteRunRequest) -> dict:
    meta = dict(request.meta or {})
    built = service.build_report_meta(
        clubs=request.clubs,
        players=request.players,
        pairs=request.pairs,
        start_date=request.start_date,
        end_date=request.end_date,
        club_or_tournament=request.club_or_tournament or "club",
        pair_direction=meta.get("pair_direction"),
        opponent_pair_direction=meta.get("opponent_pair_direction"),
        player_direction=meta.get("player_direction"),
        partner_direction=meta.get("partner_direction"),
        sort_column=str(meta.get("Sort_Column") or "Declarer_Pct"),
        min_declares=int(meta.get("Min_Declares") or 0),
        top_n=int(meta.get("Top_N") or request.limit),
    )
    built.update(meta)
    frame = None
    if request.club_or_tournament or request.clubs or request.players or request.pairs:
        _source, _any_position, selected = _run(
            service._prepare_board_frames,
            request.club_or_tournament or "club",
            request.clubs,
            request.players,
            request.pairs,
            request.start_date,
            request.end_date,
        )
        frame = selected
    return _run(
        service.run_favorite,
        favorite_id,
        built,
        frame,
        request.source,
        request.limit,
    )


@app.get("/acbl-stats/players/lookup")
def players_lookup(
    clubs: Optional[str] = Query(None),
    numbers: Optional[str] = Query(None),
    names: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    return _run(
        service.player_lookup,
        clubs=clubs,
        numbers=numbers,
        names=names,
        limit=limit,
    )


@app.get("/acbl-stats/clubs/lookup")
def clubs_lookup(
    clubs: Optional[str] = Query(None),
    names: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    return _run(service.club_lookup, clubs=clubs, names=names, limit=limit)


@app.get("/acbl-stats/player-positions")
def player_positions(
    club_or_tournament: str,
    players: str,
    clubs: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
) -> dict:
    player_list = [item for item in players.replace(",", " ").split() if item]
    club_list = [item for item in (clubs or "").replace(",", " ").split() if item]
    source, any_position, _selected = _run(
        service._prepare_board_frames,
        club_or_tournament,
        club_list,
        player_list,
        [],
        start_date,
        end_date,
    )
    return {
        "source": source,
        **service.frame_to_table(
            service.player_position_frequency(any_position, player_list)
        ),
    }


@app.post("/acbl-stats/board-results")
def board_results(request: BoardResultsRequest) -> dict:
    return _run(
        service.board_results_report,
        request.club_or_tournament,
        clubs=request.clubs,
        players=request.players,
        pairs=request.pairs,
        start_date=request.start_date,
        end_date=request.end_date,
        sort_column=request.sort_column,
        min_declares=request.min_declares,
        top_n=request.top_n,
        group_by=request.group_by,
        selected_charts=request.selected_charts,
        include_charts=request.include_charts,
    )


@app.post("/acbl-stats/head-to-head")
def head_to_head(request: HeadToHeadRequest) -> dict:
    return _run(
        service.head_to_head,
        request.club_or_tournament,
        clubs=request.clubs,
        players=request.players,
        pairs=request.pairs,
        start_date=request.start_date,
        end_date=request.end_date,
        sort_column=request.sort_column,
        pair_or_player=request.pair_or_player,
    )


@app.post("/acbl-stats/hand-records")
def hand_records(request: HandRecordsRequest) -> dict:
    return _run(
        service.hand_records_report,
        request.club_or_tournament,
        start_date=request.start_date,
        end_date=request.end_date,
        brs_regex=request.brs_regex,
        sample_size=request.sample_size,
        table_limit=request.table_limit,
        selected_charts=request.selected_charts,
        clubs=request.clubs,
        players=request.players,
        pairs=request.pairs,
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("BRIDGESTATS_API_PORT", "8523"))
    print(
        f"[acbl-stats-api] start {datetime.now(timezone.utc).isoformat()} port={port}",
        flush=True,
    )
    uvicorn.run(app, host="0.0.0.0", port=port)
