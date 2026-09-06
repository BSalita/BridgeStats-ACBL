# todo:
# 1. is match point charting implemented and proper? something's .5%
# 2. Output chart label with names instead of Declarer_Pairs
# 3. Due to rendering delays, limit charts to the 100 most frequent x labels.

import pathlib
import re
import sys
import time

import streamlit as st

_APP_DIR = pathlib.Path(__file__).resolve().parent
_SRC_DIR = _APP_DIR.parent
_streamlit = next(
    (p for p in (_APP_DIR / "streamlitlib", _SRC_DIR / "streamlitlib") if p.is_dir()),
    None,
)
if _streamlit is None:
    raise FileNotFoundError(f"streamlitlib not found under {_APP_DIR} or {_SRC_DIR}")
for _p in (_SRC_DIR, _streamlit):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.append(_s)
import streamlitlib  # must be placed after sys.path.append. vscode re-format likes to move this to the top

import bridgestats_api_client as api
from bridgestats_charts import render_chart_payloads


def Stats(club_or_tournament, pair_or_player, chart_options, groupby):
    st.set_page_config(layout="wide", initial_sidebar_state="expanded")
    streamlitlib.widen_scrollbars()

    st.header(
        f"{pair_or_player.capitalize()} Statistics for ACBL {club_or_tournament.capitalize()} Pair Games"
    )
    st.sidebar.header(f"Settings for {pair_or_player.capitalize()} Statistics")

    key_prefix = groupby[0] + club_or_tournament + "_" + pair_or_player

    if club_or_tournament == "club":
        clubs = st.sidebar.text_input(
            "Club ACBL Numbers - Restrict results to these 6 digit ACBL club numbers (empty means all). Examples: 108571  267096",
            placeholder="Enter club numbers",
            value="108571 267096",
            key=key_prefix + "-Clubs",
            help="Enter zero or more ACBL club numbers. Use Club Lookup, in above list, to find a club number. Examples: 108571  267096",
        )
        clubs = clubs.replace(",", " ").replace("_", " ").split()
        clubs = [] if clubs == [""] else clubs
        for club in clubs:
            if not re.match(r"^\d{6}$", club):
                st.warning(
                    f"Club {club} has invalid syntax. Expecting one or more six digit ACBL club numbers e.g 123456. Please correct."
                )
                st.stop()
    else:
        clubs = []

    if pair_or_player == "player":
        players = st.sidebar.text_input(
            "Player ACBL Numbers - Restrict results to these 7 digit ACBL player numbers (empty means all). Examples: 2663279 9524304 6941303 6941346",
            placeholder="Enter player numbers",
            value="2663279 9524304 6941303 6941346",
            key=key_prefix + "-Players",
            help="Enter zero or more ACBL player numbers. Use Player Lookup, in above list, to find a player number. Examples: 2663279 9524304 6941303 6941346",
        )
        players = players.replace(",", " ").replace("_", " ").split()
        players = [] if players == [""] else players
        for player in players:
            if not re.match(r"^\d{7}$", player):
                st.warning(
                    f"Player {player} has invalid syntax. Expecting one or more valid seven digit ACBL player numbers. Please correct."
                )
                st.stop()
    else:
        players = []

    if pair_or_player == "pair":
        pairs = st.sidebar.text_input(
            "Pair ACBL Numbers - Restrict results to these pairs. Use two 7 digit ACBL player numbers separated by an underscore (empty means all). Examples: 2663279_9524304  6941303_6941346",
            placeholder="Enter Pair Numbers",
            value="2663279_9524304 6941303_6941346",
            key=key_prefix + "-Pairs",
        )
        pairs = pairs.replace(",", " ").split()
        pairs = [] if pairs == [""] else pairs
        for pair in pairs:
            if not re.match(r"^\d{7}_\d{7}$", pair):
                st.warning(
                    f"Pair {pair} has invalid syntax. Expecting two valid ACBL numbers separated by an underscore e.g. 1234567_7654321. You can enter multiple sets of pair numbers. Please correct."
                )
                st.stop()
            for player in pair.split("_"):
                if player not in players:
                    players.append(player)
    else:
        pairs = []

    sort_options = [
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
        "Count",
    ]
    sort_column = st.sidebar.selectbox(
        "Sort table by:",
        options=sort_options,
        key=key_prefix + "-Stat",
        help="Choose statistic to use as primary sort",
    )

    minimum_declares = (
        0 if len(players) or len(pairs) else 6 if groupby[0] == "session_id" else 30
    )
    min_declares = st.sidebar.number_input(
        f"Enter minimum number of times a player must have declared (default {minimum_declares}):",
        value=minimum_declares,
        min_value=0,
        key=key_prefix + "-Declares-Min",
    )
    top_ranked = st.sidebar.number_input(
        "Enter number of top ranked results to show (default 100):",
        value=100,
        min_value=10,
        key=key_prefix + "-Declares-Top-Rank",
    )
    start_date = st.sidebar.text_input(
        "Enter start date:",
        value="2019-01-01",
        key=key_prefix + "-Start_Date",
        help="Enter starting date in YYYY-MM-DD format. Earliest year is 2019",
    )
    end_date = st.sidebar.text_input(
        "Enter end date:",
        value=time.strftime("%Y-%m-%d"),
        key=key_prefix + "-End_Date",
        help="Enter ending date in YYYY-MM-DD format.",
    )
    selected_charts = st.sidebar.multiselect(
        "Select charts to display",
        chart_options,
        default=chart_options,
        key=key_prefix + "-Charts",
    )

    if players:
        try:
            lookup = api.player_lookup(numbers=" ".join(players), limit=max(len(players), 1))
        except api.BridgeStatsApiClientError as exc:
            st.error(str(exc))
            st.stop()
        found = {
            str(row.get("acbl_number"))
            for row in lookup.get("rows", [])
            if row.get("acbl_number") is not None
        }
        missing = [player for player in players if player not in found]
        if missing:
            st.warning(f"Player {', '.join(missing)} is unknown. Remove from list.")
            st.stop()

    group_by = "session_id" if groupby[0] == "session_id" else "Declarer"
    with st.spinner(text="Reading board result data ..."):
        start_time = time.time()
        try:
            report = api.board_results_report(
                club_or_tournament,
                clubs=clubs,
                players=players,
                pairs=pairs,
                start_date=start_date,
                end_date=end_date,
                sort_column=sort_column,
                min_declares=min_declares,
                top_n=top_ranked,
                group_by=group_by,
                selected_charts=selected_charts,
            )
        except api.BridgeStatsApiClientError as exc:
            st.error(str(exc))
            st.stop()
        st.info(
            f"Data read completed in {round(time.time() - start_time, 2)} seconds. "
            f"{report.get('row_count', 0)} rows read. {report.get('selected_count', 0)} rows selected."
        )

    table, chart = st.tabs(["Data Tables", "Charts"])
    with table:
        with st.spinner(text="Creating data table ..."):
            start_time = time.time()
            if report.get("position_frequency"):
                st.info(
                    "Frequency of player positions. PassedOut is boards sat with no contract (usually passed out)."
                )
                streamlitlib.ShowDataFrameTable(
                    api.table_to_frame(report["position_frequency"]), round=2
                )
            if report.get("leaderboard"):
                leaderboard = api.table_to_frame(report["leaderboard"])
                st.info(
                    f"Table of {report.get('selected_count', 0)} rows sorted by {sort_column}. "
                    f"Top performing {leaderboard.height} {pair_or_player}s shown."
                )
                streamlitlib.ShowDataFrameTable(
                    leaderboard, color_column=sort_column, round=2
                )
            for player_table in report.get("player_boards") or []:
                st.info(
                    f"Boards played by {player_table.get('declarer_name')}. "
                    f"Sorted by {sort_column}. {player_table.get('row_count', 0)} boards found."
                )
                streamlitlib.ShowDataFrameTable(
                    api.table_to_frame(player_table),
                    color_column=sort_column,
                    round=2,
                )
            if report.get("session_means"):
                st.info(
                    f"Means of boards played by {pair_or_player}s aggregated per session. Sorted by {sort_column}."
                )
                streamlitlib.ShowDataFrameTable(
                    api.table_to_frame(report["session_means"]),
                    color_column=sort_column,
                    round=2,
                )
            if (len(players) > 1 or len(pairs) > 1):
                try:
                    comparison = api.head_to_head(
                        club_or_tournament,
                        clubs=clubs,
                        players=players,
                        pairs=pairs,
                        start_date=start_date,
                        end_date=end_date,
                        sort_column=sort_column,
                        pair_or_player=pair_or_player,
                    )
                except api.BridgeStatsApiClientError as exc:
                    st.info(str(exc))
                else:
                    n_boards = comparison.get("n_boards") or 0
                    n_sessions = comparison.get("n_sessions") or 0
                    identical = api.table_to_frame(comparison.get("identical_boards"))
                    if identical.height == 0:
                        st.info(
                            f"No identical boards found for head-to-head comparison between selected {pair_or_player}s."
                        )
                    else:
                        st.info(
                            f"Comparison of results of identical boards played by {pair_or_player}s. "
                            f"{n_boards} boards found in {n_sessions} sessions. "
                            f"Sorted by Date, session_id, HandRecordBoard, Declarer_Name."
                        )
                        streamlitlib.ShowDataFrameTable(
                            identical,
                            color_column=sort_column,
                            ngroup_name="ngroup",
                            round=2,
                            key="polars_identical_boards_table",
                        )
                        session_cmp = api.table_to_frame(comparison.get("session_means"))
                        if session_cmp.height:
                            st.info(
                                f"Comparison of results of identical boards played by {pair_or_player}s aggregated per session. "
                                f"{n_boards} boards found in {n_sessions} sessions. Sorted by {sort_column}."
                            )
                            streamlitlib.ShowDataFrameTable(
                                session_cmp,
                                color_column=sort_column,
                                round=2,
                                key="polars_aggregated_per_session_table",
                            )
                    pair_cmp = api.table_to_frame(comparison.get("pair_head_to_head"))
                    if pair_or_player == "pair" and pair_cmp.height:
                        st.info(
                            "Comparison of head-to-head results of identical boards played between pairs aggregated per boards. Sorted by Declarer_Name."
                        )
                        streamlitlib.ShowDataFrameTable(
                            pair_cmp,
                            color_column=sort_column,
                            ngroup_name="ngroup",
                            round=2,
                        )
            st.info(f"Data table created in {round(time.time() - start_time, 2)} seconds.")

    with chart:
        with st.spinner(text="Creating charts ..."):
            start_time = time.time()
            st.write(
                "Acronyms: BidLvl is Contract Level, BidSuit is Contract Suit, "
                "ContractType is Type of Contract (passed-out, partial, game, small slam, grand slam), "
                "Dbl is Doubled, MP is Player's Master Points Pct is Match Point Percent"
            )
            render_chart_payloads(report.get("charts") or [])
            st.info(f"Charts created in {round(time.time() - start_time, 2)} seconds.")
