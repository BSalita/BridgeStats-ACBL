"""Elo-style player name / number sidebar widgets for ACBL BridgeStats."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import streamlit as st

import bridgestats_api_client as api

PLAYER_NUMBER_PATTERN = r"^\d{7}$"
PLAYER_NUMBER_HELP = (
    "Digits-only exact match. Enter one or more 7-digit ACBL player numbers. "
    "For pairs, matches either partner."
)
PLAYER_NAME_HELP = (
    "Case-insensitive fuzzy match on first and last name. "
    "Comma or semicolon separates multiple names. For pairs, matches either partner. "
    "If several people match, the best match is selected; pick another from the list."
)
MAX_NAME_SELECT_OPTIONS = 200


def sidebar_player_filters(key_prefix: str) -> Tuple[str, str]:
    name_filter = st.sidebar.text_input(
        "Filter by player name",
        key=f"{key_prefix}-Name",
        placeholder="Fuzzy name match...",
        help=PLAYER_NAME_HELP,
    )
    number_filter = st.sidebar.text_input(
        "Filter by player number",
        key=f"{key_prefix}-Number",
        placeholder="Exact player number...",
        help=PLAYER_NUMBER_HELP,
    )
    return (name_filter or "").strip(), (number_filter or "").strip()


def parse_player_numbers(raw: str) -> List[str]:
    tokens = (raw or "").replace(",", " ").replace("_", " ").split()
    tokens = [] if tokens == [""] else tokens
    for token in tokens:
        if not re.match(PLAYER_NUMBER_PATTERN, token):
            st.warning(
                f"Player {token} has invalid syntax. "
                "Expecting one or more valid seven digit ACBL player numbers."
            )
            st.stop()
    return tokens


def _row_player_id(row: Dict[str, Any]) -> Optional[str]:
    pid = row.get("acbl_number")
    if pid is None:
        pid = row.get("player_id")
    if pid is None:
        return None
    return str(pid)


def _row_label(row: Dict[str, Any]) -> str:
    pid = _row_player_id(row) or ""
    first = str(row.get("first_name") or "").strip()
    last = str(row.get("last_name") or "").strip()
    name = f"{first} {last}".strip() or pid
    return f"{name} ({pid})"


def resolve_player_ids(
    name_filter: str,
    numbers: Sequence[str],
    clubs: Optional[Iterable[str]] = None,
    *,
    key_prefix: str = "",
    max_options: int = MAX_NAME_SELECT_OPTIONS,
) -> List[str]:
    resolved = list(numbers)
    queries = [part.strip() for part in re.split(r"[,;]", name_filter or "") if part.strip()]
    if not queries:
        return resolved
    clubs_arg = " ".join(str(club) for club in clubs) if clubs else None
    seen = set(resolved)
    for index, query in enumerate(queries):
        letters = re.sub(r"[^a-z0-9]+", "", query, flags=re.I)
        if len(letters) < 3:
            st.warning("Player name filter needs at least 3 letters.")
            st.stop()
        try:
            payload = api.player_lookup(
                clubs=clubs_arg,
                names=query,
                limit=max_options,
            )
        except api.BridgeStatsApiClientError as exc:
            st.error(str(exc))
            st.stop()
        rows = [row for row in (payload.get("rows") or []) if _row_player_id(row)]
        total = payload.get("total", len(rows))
        if total == 0 or not rows:
            st.warning(f"No players match the name filter '{query}'.")
            st.stop()
        labels = [_row_label(row) for row in rows]
        by_label = {label: _row_player_id(row) for label, row in zip(labels, rows)}
        if len(labels) == 1:
            chosen_label = labels[0]
        else:
            help_bits = [f"{total} matches. Best match is selected."]
            if total > len(labels):
                help_bits.append(f"Showing top {len(labels)}. Narrow the name to see others.")
            chosen_label = st.sidebar.selectbox(
                f"Matching '{query}'",
                options=labels,
                index=0,
                key=f"{key_prefix}-NamePick-{index}",
                help=" ".join(help_bits),
            )
        pid = by_label[chosen_label]
        if pid and pid not in seen:
            seen.add(pid)
            resolved.append(pid)
    return resolved
