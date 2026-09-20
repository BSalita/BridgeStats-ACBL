"""Shared FastAPI/SQL/favorites helpers. Domain handlers stay in each app.

Vendored from src/mlBridge/mlBridgeApiCommon.py. Do not import mlBridge here;
stats images clone only this repo (see test_imports).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

DATA_ROOT_ENV = "DATA_ROOT"
CON_REGISTER_NAME = "self"
DEFAULT_SQL_ROW_LIMIT = 500
MAX_SQL_ROW_LIMIT = 2000
SQL_FORBIDDEN = re.compile(
    r"\b(COPY|INSTALL|LOAD|ATTACH|EXPORT|PRAGMA|CALL|SET)\b",
    re.IGNORECASE,
)


def resolve_data_root(default: Optional[Path] = None) -> Optional[Path]:
    env = (os.environ.get(DATA_ROOT_ENV) or "").strip()
    if env:
        return Path(env)
    if default is not None:
        return default
    return None


def data_root_search_paths(organization: str) -> List[Path]:
    root = resolve_data_root()
    if root is None:
        return []
    org = organization.strip().lower()
    if org == "acbl":
        return [
            root / "stats" / "acbl",
            root / "_wslc_host" / "acbl-stage" / "club_results_parquet",
        ]
    if org == "ffbridge":
        return [
            root / "stats" / "ffbridge",
            root / "ffbridge",
        ]
    raise ValueError(f"Unknown organization {organization!r}")


def clamp_sql_limit(
    limit: Optional[int],
    default: int = DEFAULT_SQL_ROW_LIMIT,
    maximum: int = MAX_SQL_ROW_LIMIT,
) -> int:
    return max(1, min(limit or default, maximum))


def assert_readonly_sql(sql: str) -> None:
    if SQL_FORBIDDEN.search(sql):
        raise ValueError("SQL contains a forbidden statement")


def qualify_from_clause(
    sql: str,
    source: str,
    table_name: str = CON_REGISTER_NAME,
) -> str:
    lowered = sql.lower()
    if f"from {table_name}" not in lowered and f"from {source}" not in lowered:
        return f"FROM {table_name} " + sql
    return sql


def prepare_sql(
    sql: str,
    source: str,
    limit: Optional[int] = None,
    table_name: str = CON_REGISTER_NAME,
    default_limit: int = DEFAULT_SQL_ROW_LIMIT,
    max_limit: int = MAX_SQL_ROW_LIMIT,
) -> tuple[str, int]:
    sql = (sql or "").strip()
    if not sql:
        raise ValueError("sql is required")
    assert_readonly_sql(sql)
    return (
        qualify_from_clause(sql, source, table_name=table_name),
        clamp_sql_limit(limit, default=default_limit, maximum=max_limit),
    )


def run_duckdb_sql(sql: str, setup: Callable[[Any], None]) -> Any:
    import duckdb

    con = duckdb.connect()
    try:
        setup(con)
        return con.execute(sql).pl()
    finally:
        con.close()


def truncate_frame(result: Any, limit: int) -> tuple[Any, bool]:
    truncated = result.height > limit
    if truncated:
        result = result.head(limit)
    return result, truncated


def flatten_favorites_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    buttons = payload.get("Buttons") or {}
    id_to_buttons: Dict[str, List[str]] = {}
    if isinstance(buttons, dict):
        for button_id, button in buttons.items():
            if not isinstance(button, dict):
                continue
            for ref in button.get("prompts") or []:
                if isinstance(ref, str) and ref.startswith("@") and len(ref) > 1:
                    id_to_buttons.setdefault(ref[1:], []).append(str(button_id))
    select_boxes = payload.get("SelectBoxes") or {}
    vetted = select_boxes.get("Vetted_Prompts") if isinstance(select_boxes, dict) else {}
    if not isinstance(vetted, dict):
        return []
    favorites: List[Dict[str, Any]] = []
    for fav_id, entry in vetted.items():
        if not isinstance(entry, dict):
            continue
        statements: List[Dict[str, str]] = []
        for item in entry.get("prompts") or []:
            if not isinstance(item, dict):
                continue
            sql = str(item.get("sql") or "").strip()
            prompt = str(item.get("prompt") or "").strip()
            if not sql or prompt.startswith("/"):
                continue
            statements.append({"prompt": prompt, "sql": sql})
        if not statements:
            continue
        favorites.append(
            {
                "id": str(fav_id),
                "title": str(entry.get("title") or fav_id),
                "help": str(entry.get("help") or ""),
                "source": str(entry.get("source") or "{Board_Source}"),
                "buttons": id_to_buttons.get(str(fav_id), []),
                "statements": statements,
            }
        )
    return favorites


def select_favorites(
    favorites: Sequence[Dict[str, Any]],
    favorite_id: Optional[str] = None,
) -> Dict[str, Any]:
    wanted = str(favorite_id or "").strip()
    selected = list(favorites)
    if wanted:
        selected = [item for item in selected if item["id"] == wanted]
        if not selected:
            raise KeyError(f"Unknown favorite id {wanted!r}")
    return {"count": len(selected), "favorites": selected}


def health_payload(
    info: Optional[Dict[str, Any]] = None,
    *,
    service: str,
    api_version: str,
    build_tag: str,
    info_first: bool = False,
) -> Dict[str, Any]:
    core = {
        "status": "ok",
        "service": service,
        "api_version": api_version,
        "build_tag": build_tag,
    }
    body = dict(info or {})
    if info_first:
        return {**body, **core}
    return {**core, **body}
