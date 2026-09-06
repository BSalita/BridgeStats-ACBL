# todo:
# 1. move Date to first column or so.
# 2. data table columns need to be ordered by importance. possibly eliminate some unimportant columns.

import streamlit as st
import datetime
import pathlib
import pyarrow.parquet as pq
import polars as pl
import altair as alt
import matplotlib.pyplot as plt
import time
import bridgestatslib
import sys
_APP_DIR = pathlib.Path(__file__).resolve().parent
_SRC_DIR = _APP_DIR.parent
_streamlit = next((p for p in (_APP_DIR / 'streamlitlib', _SRC_DIR / 'streamlitlib') if p.is_dir()), None)
if _streamlit is None:
    raise FileNotFoundError(f"streamlitlib not found under {_APP_DIR} or {_SRC_DIR}")
for _p in (_SRC_DIR, _streamlit):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.append(_s)
import streamlitlib # must be placed after sys.path.append. vscode re-format likes to move this to the top


def apply_regex_filter(hand_records_df, brs_regex, sample_size=100000):
    """Apply regex filter and sampling using pure Polars operations"""
    df = hand_records_df
    
    # Apply regex filter if provided
    if brs_regex:
        df = df.filter(pl.col('PBN').str.contains(brs_regex))
    
    # Apply sampling if the dataframe is larger than sample_size
    if df.height > sample_size:
        df = df.sample(n=sample_size)
    
    return df

 
def Stats(club_or_tournament, pair_or_player, chart_options, groupby):

    st.set_page_config(layout="wide", initial_sidebar_state="expanded")
    streamlitlib.widen_scrollbars()

    st.header(f"Hand Record Statistics for ACBL {club_or_tournament.capitalize()} Pair Games")
    st.sidebar.header("Settings for Hand Record Statistics")

    key_prefix = club_or_tournament # pair_or_player isn't used here

    try:
        acbl_hand_records_augmented_file = bridgestatslib.resolve_data_file(
            f"acbl_{club_or_tournament}_hand_records_augmented_narrow.parquet",
            required_columns=('PBN', 'game_date'),
        )
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

    # tournament data is as early as 2013? club data as early as 2019?
    start_date = st.sidebar.text_input('Enter start date:', value='2000-01-01', key=key_prefix+'_HandRecord-Start_Date', help='Enter starting date in YYYY-MM-DD format. Earliest year is 2019')
    end_date_default = time.strftime("%Y-%m-%d")
    end_date = st.sidebar.text_input('Enter end date:', value=end_date_default, key=key_prefix+'_HandRecord-End_Date', help='Enter ending date in YYYY-MM-DD format.')

    chart_options = ['ParScore','CT_N_S,CT_N_H,CT_N_D,CT_N_C,CT_N_N','DD_N_C,DD_N_D,DD_N_H,DD_N_S,DD_N_N','SL_N_C,SL_N_D,SL_N_H,SL_N_S','SL_N_ML_SJ','HCP_NS,HCP_EW','HCP_N,HCP_E,HCP_S,HCP_W','QT_N,QT_E,QT_S,QT_W','QT_NS,QT_EW','DP_N','DP_N_C,DP_N_D,DP_N_H,DP_N_S','DP_NS,DP_EW','HCP_NS,DP_NS,DD_N_N','HCP_NS,QT_NS,DD_N_N']
    selected_charts = st.sidebar.multiselect('Select charts to display', chart_options, default=chart_options, key=key_prefix+'_HandRecord-Charts')

    st.sidebar.header("Advanced Settings")

    # select using regex
    brs_regex = st.sidebar.text_input('Restrict results to boards matching this regex:', value='', key=key_prefix+'_HandRecord-brs', help='Example: ^SAK.*$').strip() # e.g. ^SAK.*$

    table_display_limit = 100 # streamlit gets choked up pretty quickly. need to limit table to 100.
    sample_size = 100000

    with st.spinner(text="Reading hand record data ..."):
        start_time = time.time()
        hand_records_df = bridgestatslib.load_hand_records(acbl_hand_records_augmented_file)
        hand_records_len = hand_records_df.height
        database_column_names = hand_records_df.columns
        end_time = time.time()
        st.info(f"Data read completed in {round(end_time-start_time,2)} seconds. {hand_records_len} rows read.")

    with st.spinner(text="Selecting database rows ..."):
        start_time = time.time()
        
        # Apply regex filter and sampling using pure Polars operations
        selected_df = apply_regex_filter(hand_records_df, brs_regex, sample_size)
        
        selected_df = selected_df.unique(subset=["PBN"])
        uniques = selected_df.height
        
        # Filter by date range
        start_date_obj = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        selected_df = selected_df.filter(
            (pl.col('game_date').cast(pl.Date) >= start_date_obj) & (pl.col('game_date').cast(pl.Date) <= end_date_obj)
        )
        selected_df_len = selected_df.height
        end_time = time.time()
        st.info(f"Filter completed in {round(end_time-start_time,2)} seconds. Database has {hand_records_len} rows. Sampling {sample_size} random rows. {uniques} unique hands found.")

    # prepare data columns
    # Remove columns starting with '__'
    selected_df = selected_df.select([
        col for col in selected_df.columns if not col.startswith('__')
    ])
    
    # Round float columns to 2 decimal places
    float_cols = [col for col in selected_df.columns if selected_df[col].dtype in [pl.Float32, pl.Float64]]
    selected_df = selected_df.with_columns([
        pl.col(col).round(2) for col in float_cols
    ])

    table, chart = st.tabs(["Data Table", "Charts"])

    with table:
        with st.spinner(text="Creating data table ..."):
            start_time = time.time()
            # Sample rows and sort
            table_df = selected_df.sample(n=min(table_display_limit, selected_df.height))
            st.text(f"Table of Hand Records. {selected_df_len} random rows selected. Table display limited to {table_df.height} random rows.")
            streamlitlib.ShowDataFrameTable(table_df)
            del table_df
            end_time = time.time()
            st.info(f"Data table created in {round(end_time-start_time,2)} seconds.")

    with chart:
        with st.spinner(text="Creating Charts"):
            start_time = time.time()

            st.write(f"Abbreviations for Chart Type: CT is Contract Type (passed-out, partial, game, small slam, grand slam), DD is Double Dummy, DP is Distribution Points, HCP is High Card Points, LoTT is Law of Total Tricks, QT is Quick Tricks, SL is Suit Length")
            st.write(f"Abbreviations for individual directions: N is North, S is South, E is East W is West.")
            st.write(f"Abbreviations for pair direction: NS is North-South, EW is East-West.")
            st.write(f"Abbreviations for strains (suits): C is Clubs, D is Diamonds, H is Hearts, S is Spades, N is No-Trump")
            st.write(f"For example: DD_N_N is Double Dummy - North - No-Trump")

            st.text(f"{selected_df_len} random rows selected.")
            bridgestatslib.ShowCharts(selected_df, selected_charts)
            
            end_time = time.time()
            st.info(f"Charts created in {round(end_time-start_time,2)} seconds.")
