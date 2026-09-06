# todo:
# 1. move Date to first column or so.
# 2. data table columns need to be ordered by importance. possibly eliminate some unimportant columns.

import pathlib
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

    st.header(f"Hand Record Statistics for ACBL {club_or_tournament.capitalize()} Pair Games")
    st.sidebar.header("Settings for Hand Record Statistics")

    key_prefix = club_or_tournament
    start_date = st.sidebar.text_input(
        "Enter start date:",
        value="2000-01-01",
        key=key_prefix + "_HandRecord-Start_Date",
        help="Enter starting date in YYYY-MM-DD format. Earliest year is 2019",
    )
    end_date = st.sidebar.text_input(
        "Enter end date:",
        value=time.strftime("%Y-%m-%d"),
        key=key_prefix + "_HandRecord-End_Date",
        help="Enter ending date in YYYY-MM-DD format.",
    )
    chart_options = [
        "ParScore",
        "CT_N_S,CT_N_H,CT_N_D,CT_N_C,CT_N_N",
        "DD_N_C,DD_N_D,DD_N_H,DD_N_S,DD_N_N",
        "SL_N_C,SL_N_D,SL_N_H,SL_N_S",
        "SL_N_ML_SJ",
        "HCP_NS,HCP_EW",
        "HCP_N,HCP_E,HCP_S,HCP_W",
        "QT_N,QT_E,QT_S,QT_W",
        "QT_NS,QT_EW",
        "DP_N",
        "DP_N_C,DP_N_D,DP_N_H,DP_N_S",
        "DP_NS,DP_EW",
        "HCP_NS,DP_NS,DD_N_N",
        "HCP_NS,QT_NS,DD_N_N",
    ]
    selected_charts = st.sidebar.multiselect(
        "Select charts to display",
        chart_options,
        default=chart_options,
        key=key_prefix + "_HandRecord-Charts",
    )
    st.sidebar.header("Advanced Settings")
    brs_regex = st.sidebar.text_input(
        "Restrict results to boards matching this regex:",
        value="",
        key=key_prefix + "_HandRecord-brs",
        help="Example: ^SAK.*$",
    ).strip()
    table_display_limit = 100
    sample_size = 100000

    with st.spinner(text="Reading hand record data ..."):
        start_time = time.time()
        try:
            report = api.hand_records_report(
                club_or_tournament,
                start_date=start_date,
                end_date=end_date,
                brs_regex=brs_regex,
                sample_size=sample_size,
                table_limit=table_display_limit,
                selected_charts=selected_charts,
            )
        except api.BridgeStatsApiClientError as exc:
            st.error(str(exc))
            st.stop()
        st.info(
            f"Data read completed in {round(time.time() - start_time, 2)} seconds. "
            f"{report.get('row_count', 0)} rows read. Sampling {sample_size} random rows. "
            f"{report.get('unique_hands', 0)} unique hands found."
        )

    table, chart = st.tabs(["Data Table", "Charts"])
    with table:
        with st.spinner(text="Creating data table ..."):
            start_time = time.time()
            table_df = api.table_to_frame(report.get("table"))
            st.text(
                f"Table of Hand Records. {report.get('selected_count', 0)} random rows selected. "
                f"Table display limited to {table_df.height} random rows."
            )
            streamlitlib.ShowDataFrameTable(table_df)
            st.info(f"Data table created in {round(time.time() - start_time, 2)} seconds.")

    with chart:
        with st.spinner(text="Creating Charts"):
            start_time = time.time()
            st.write(
                "Abbreviations for Chart Type: CT is Contract Type (passed-out, partial, game, small slam, grand slam), "
                "DD is Double Dummy, DP is Distribution Points, HCP is High Card Points, LoTT is Law of Total Tricks, "
                "QT is Quick Tricks, SL is Suit Length"
            )
            st.write("Abbreviations for individual directions: N is North, S is South, E is East W is West.")
            st.write("Abbreviations for pair direction: NS is North-South, EW is East-West.")
            st.write("Abbreviations for strains (suits): C is Clubs, D is Diamonds, H is Hearts, S is Spades, N is No-Trump")
            st.write("For example: DD_N_N is Double Dummy - North - No-Trump")
            st.text(f"{report.get('selected_count', 0)} random rows selected.")
            render_chart_payloads(report.get("charts") or [])
            st.info(f"Charts created in {round(time.time() - start_time, 2)} seconds.")
