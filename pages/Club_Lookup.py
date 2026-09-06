# todo:
# 1. put club lookup into bridgestats.py (and elsewhere?) to validate club entries.

import streamlit as st
import pathlib
import pyarrow.parquet as pq
import pandas as pd
import altair as alt
import time
import bridgestatslib
import sys
_APP_DIR = pathlib.Path(__file__).resolve().parent.parent
_SRC_DIR = _APP_DIR.parent
_streamlit = next((p for p in (_APP_DIR / 'streamlitlib', _SRC_DIR / 'streamlitlib') if p.is_dir()), None)
if _streamlit is None:
    raise FileNotFoundError(f"streamlitlib not found under {_APP_DIR} or {_SRC_DIR}")
for _p in (_SRC_DIR, _streamlit):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.append(_s)
import streamlitlib # must be placed after sys.path.append. vscode re-format likes to move this to the top
import polars as pl

st.header("Lookup Club Information")
st.sidebar.header("Settings for Club Lookup")

st.sidebar.header("Settings")

dataPath = bridgestatslib.resolve_data_path()

with st.spinner(text="Reading data ..."):
    start_time = time.time()
    acbl_club_dict_filename = 'acbl_clubs.parquet'
    acbl_club_dict_file = dataPath.joinpath(acbl_club_dict_filename)
    acbl_club_df = bridgestatslib.load_club_df(acbl_club_dict_file)
    end_time = time.time()
    st.caption(f"Data read completed in {round(end_time-start_time,2)} seconds.")

# clubs can be: [] [108571] FTBC, [267096] FLQT, [204891] HH
# todo: need to verify club numbers. At least check for 6 digits.
clubs = st.sidebar.text_input('Narrow search to these ACBL club numbers. Enter one or more 6 digit numbers (empty means all):', placeholder='Enter list of ACBL club numbers', key='Club_Lookup-Club', help='Example: 108571 (Fort Lauderdale Bridge Club')
clubs_l = clubs.replace(',',' ').split()
clubs_regex = '|'.join(clubs_l)

club_names = st.sidebar.text_input('Narrow search to these club names. Enter one or more club names (empty means all):', placeholder='Enter list of club names', key='Club_Lookup-Club_Name')
club_names_l = club_names.split()
club_names_regex = '|'.join(club_names_l)

# Cast id to string for regex matching and ensure proper types
selected_df = acbl_club_df.with_columns([
    pl.col('id').cast(pl.Utf8)
])

# Apply filters based on user input
selected_df = selected_df if len(clubs_regex)==0 else selected_df.filter(pl.col('id').str.contains(clubs_regex))
selected_df = selected_df if len(club_names_regex)==0 else selected_df.filter(pl.col('name').str.contains(club_names_regex, ignore_case=True))

table, charts = st.tabs(["Data Table", "Charts"])

st.caption(f"Database has {acbl_club_df.height} rows. {selected_df.height} rows selected.")
if selected_df.height == 0:
    st.warning('No rows selected')
    st.stop()

with table:
    with st.spinner(text="Creating data table ..."):
        start_time = time.time()
        streamlitlib.ShowDataFrameTable(selected_df)
        end_time = time.time()
        st.caption(f"Data table created in {round(end_time-start_time,2)} seconds.")

with charts:
    pass
