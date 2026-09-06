# todo:

import streamlit as st
import os
import pathlib
import pyarrow.parquet as pq
import duckdb
import polars as pl
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
import time
import sys

DATA_DIR_ENV = 'BRIDGESTATS_DATA_DIR'
EXTRA_DATA_DIR_ENV = 'BRIDGESTATS_EXTRA_DATA_DIR'

BOARD_RESULT_COLUMNS = (
    'Club', 'session_id', 'Date',
    'Declarer_Direction', 'Declarer', 'Dummy', 'OnLead', 'NotOnLead',
    'Declarer_Name',
    'Player_ID_N', 'Player_ID_E', 'Player_ID_S', 'Player_ID_W',
    'Player_Name_N', 'Player_Name_E', 'Player_Name_S', 'Player_Name_W',
    'Vul_Declarer', 'ParScore', 'MP_Par_Pct_Declarer', 'Score_Declarer',
    'DD_Tricks', 'Tricks', 'DD_Score_Declarer', 'MP_DD_Pct_Declarer',
    'EV_Score_Declarer', 'EV_Max_Declarer', 'MP_EV_Pct_Declarer',
    'MP_EV_Max_Pct_Declarer', 'Declarer_Pct',
    'HandRecordBoard', 'Board', 'Result', 'BidLvl', 'BidSuit', 'Dbl', 'Vul',
    'ContractType', 'PBN',
)

BOARD_RESULT_OPTIONAL_COLUMNS = ('Club', 'Declarer', 'Player_Name_N', 'Player_Name_E', 'Player_Name_S', 'Player_Name_W')

HAND_RECORD_COLUMNS = (
    'PBN', 'HandRecordBoard', 'game_date', 'session_id',
    'ParScore', 'CT_N_S', 'CT_N_H', 'CT_N_D', 'CT_N_C', 'CT_N_N',
    'DD_N_C', 'DD_N_D', 'DD_N_H', 'DD_N_S', 'DD_N_N',
    'SL_N_C', 'SL_N_D', 'SL_N_H', 'SL_N_S', 'SL_N_ML_SJ',
    'HCP_NS', 'HCP_EW', 'HCP_N', 'HCP_E', 'HCP_S', 'HCP_W',
    'QT_N', 'QT_E', 'QT_S', 'QT_W', 'QT_NS', 'QT_EW',
    'DP_N', 'DP_N_C', 'DP_N_D', 'DP_N_H', 'DP_N_S', 'DP_NS', 'DP_EW',
)


def resolve_data_path():
    """Primary data directory. Env override wins; default is <repo>/data."""
    env = os.environ.get(DATA_DIR_ENV)
    if env:
        return pathlib.Path(env)
    return pathlib.Path(__file__).resolve().parent / 'data'


def data_search_roots():
    """Places to look for pipeline parquets. Large Stage 3c files stay on E: / acbl-pipeline."""
    roots = []
    for key in (DATA_DIR_ENV, EXTRA_DATA_DIR_ENV):
        env = os.environ.get(key)
        if env:
            roots.append(pathlib.Path(env))
    roots.append(pathlib.Path(__file__).resolve().parent / 'data')
    for extra in (
        pathlib.Path('/app/extra-data'),
        pathlib.Path('/data/_wslc_host/acbl-stage/club_results_parquet'),
        pathlib.Path('e:/bridge/data/acbl'),
        pathlib.Path(__file__).resolve().parent.parent / 'acbl-pipeline' / 'club_results_parquet',
    ):
        if extra.exists():
            roots.append(extra)
    seen = set()
    unique = []
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def resolve_data_file(*names, required_columns=()):
    """Return the first existing path among names in the search roots.

    If required_columns is set, skip files whose schema is missing those
    current pipeline names (stale local copies).
    """
    tried = []
    for root in data_search_roots():
        for name in names:
            path = root / name
            tried.append(str(path))
            if not path.is_file():
                continue
            if required_columns:
                schema = pl.read_parquet_schema(str(path))
                missing = [col for col in required_columns if col not in schema]
                if missing:
                    continue
            return path
    raise FileNotFoundError('Missing data file (tried): ' + '; '.join(tried))


def _select_columns(schema, wanted, optional=()):
    missing = [col for col in wanted if col not in schema and col not in optional]
    if missing:
        raise ValueError('Missing required columns: ' + ', '.join(missing))
    return [col for col in wanted if col in schema]


def normalize_board_results(df):
    """Compute pair keys and diffs from current pipeline columns only."""
    if 'Declarer' not in df.columns:
        needed = {'Declarer_Direction', 'Player_ID_N', 'Player_ID_E', 'Player_ID_S', 'Player_ID_W'}
        if not needed.issubset(df.columns):
            raise ValueError('Declarer is required, or Declarer_Direction plus Player_ID_N/E/S/W')
        df = df.with_columns(
            pl.struct(['Declarer_Direction', 'Player_ID_N', 'Player_ID_E', 'Player_ID_S', 'Player_ID_W']).map_elements(
                lambda r: None if r['Declarer_Direction'] is None else r[f"Player_ID_{r['Declarer_Direction']}"],
                return_dtype=pl.String,
            ).alias('Declarer')
        )
    df = df.with_columns([
        (pl.col('Tricks') - pl.col('DD_Tricks')).alias('Tricks_DD_Diff'),
        (pl.col('Score_Declarer') - pl.col('DD_Score_Declarer')).alias('Score_Declarer_DD_Diff'),
        (pl.col('ParScore') - pl.col('DD_Score_Declarer')).alias('ParScore_DD_Diff'),
        (pl.col('EV_Score_Declarer') - pl.col('Score_Declarer')).alias('EV_Score_Declarer_Diff'),
        (pl.col('EV_Max_Declarer') - pl.col('Score_Declarer')).alias('EV_Max_Declarer_Diff'),
        (pl.col('MP_EV_Pct_Declarer') - pl.col('Declarer_Pct')).alias('MP_EV_Pct_Declarer_Diff'),
        (pl.col('MP_EV_Max_Pct_Declarer') - pl.col('Declarer_Pct')).alias('MP_EV_Max_Pct_Declarer_Diff'),
        (pl.col('MP_EV_Max_Pct_Declarer') - pl.col('MP_Par_Pct_Declarer')).alias('MP_EV_ParScore_Pct_Diff'),
        (pl.col('MP_EV_Max_Pct_Declarer') - pl.col('MP_Par_Pct_Declarer')).alias('MP_EV_ParScore_Pct_Max_Diff'),
        (pl.col('Declarer').cast(pl.Utf8) + '_' + pl.col('Dummy').cast(pl.Utf8)).alias('Declarer_Pair'),
        (pl.col('OnLead').cast(pl.Utf8) + '_' + pl.col('NotOnLead').cast(pl.Utf8)).alias('Defender_Pair'),
    ])
    for col in ('Declarer', 'Dummy', 'OnLead', 'NotOnLead', 'Player_ID_N', 'Player_ID_E', 'Player_ID_S', 'Player_ID_W', 'session_id'):
        df = df.with_columns(pl.col(col).cast(pl.Utf8))
    return df


def normalize_hand_records(df):
    return df


def apply_filters(board_results_df, clubs, players, pairs, start_date, end_date):
    """Filter board results. Works on DataFrame or LazyFrame."""
    df = board_results_df
    columns = set(df.collect_schema().names()) if isinstance(df, pl.LazyFrame) else set(df.columns)

    if clubs and 'Club' in columns:
        club_list = [int(club) for club in clubs]
        df = df.filter(pl.col('Club').is_in(club_list))

    if players:
        player_list = [str(p) for p in players]
        player_columns = []
        for col_name in ('Player_ID_N', 'Player_ID_E', 'Player_ID_S', 'Player_ID_W'):
            if col_name in columns:
                player_columns.append(pl.col(col_name).cast(pl.Utf8).is_in(player_list))
        if player_columns:
            player_filter = player_columns[0]
            for col_filter in player_columns[1:]:
                player_filter = player_filter | col_filter
            df = df.filter(player_filter)

    if pairs and {'Declarer', 'Dummy'}.issubset(columns):
        pair_condition = None
        for pair in pairs:
            p1, p2 = pair.split('_')
            current = (
                ((pl.col('Declarer').cast(pl.Utf8) == p1) & (pl.col('Dummy').cast(pl.Utf8) == p2))
                | ((pl.col('Declarer').cast(pl.Utf8) == p2) & (pl.col('Dummy').cast(pl.Utf8) == p1))
            )
            pair_condition = current if pair_condition is None else pair_condition | current
        if pair_condition is not None:
            df = df.filter(pair_condition)

    if start_date and end_date and 'Date' in columns:
        import datetime
        start_date_obj = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        df = df.filter(
            (pl.col('Date').cast(pl.Date) >= start_date_obj)
            & (pl.col('Date').cast(pl.Date) <= end_date_obj)
        )
    return df


def player_position_frequency(df, players):
    """Boards sat by seat. Passed-out boards have no Declarer/Dummy/OnLead/NotOnLead."""
    rows = []
    for player in players:
        player = str(player)
        named = df.filter(pl.col('Declarer').eq(player))
        if named.height == 0 and 'Declarer_Name' in df.columns:
            named = df.filter(
                pl.col('Player_ID_N').eq(player)
                | pl.col('Player_ID_E').eq(player)
                | pl.col('Player_ID_S').eq(player)
                | pl.col('Player_ID_W').eq(player)
            )
        player_name = None
        if named.height and 'Declarer_Name' in named.columns:
            player_name = named.select('Declarer_Name').tail(1).row(0)[0]

        seats = {}
        for pos in ('Declarer', 'OnLead', 'Dummy', 'NotOnLead'):
            seats[pos] = int(df.select(pl.col(pos).eq(player).sum()).item())
        contract_total = sum(seats.values())

        directions = {}
        direction_total = 0
        for col, seat in (('Player_ID_N', 'N'), ('Player_ID_E', 'E'), ('Player_ID_S', 'S'), ('Player_ID_W', 'W')):
            count = int(df.select(pl.col(col).eq(player).sum()).item()) if col in df.columns else 0
            directions[seat] = count
            direction_total += count

        passed_out = max(direction_total - contract_total, 0)
        denom = direction_total if direction_total else contract_total
        row = {
            'Player': player,
            'Player_Name': player_name,
            'Count': denom,
            'PassedOut': passed_out,
        }
        for seat, count in directions.items():
            row[seat] = count
            row[f'{seat}_Pct'] = count / denom if denom else 0
        for pos, count in seats.items():
            row[pos] = count
            row[f'{pos}_Pct'] = count / denom if denom else 0
        rows.append(row)
    return pl.DataFrame(rows, strict=False)


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


@st.cache_data(show_spinner=False)
def load_board_results(filename, clubs=(), players=(), pairs=(), start_date=None, end_date=None):
    """Column-project the Stage 3c monolith, then collect the filtered slice."""
    path = str(filename)
    schema = pl.read_parquet_schema(path)
    columns = _select_columns(schema, BOARD_RESULT_COLUMNS, BOARD_RESULT_OPTIONAL_COLUMNS)
    lf = pl.scan_parquet(path).select(columns)
    df = lf.collect()
    df = normalize_board_results(df)
    return apply_filters(df, list(clubs), list(players), list(pairs), start_date, end_date)


@st.cache_data(show_spinner=False)
def load_hand_records(filename):
    path = str(filename)
    schema = pl.read_parquet_schema(path)
    columns = _select_columns(schema, HAND_RECORD_COLUMNS)
    df = pl.scan_parquet(path).select(columns).collect()
    return normalize_hand_records(df)


@st.cache_data(show_spinner=False)
def load_player_name_dict():
    path = resolve_data_file('acbl_player_info.parquet')
    df = pl.read_parquet(path, columns=['acbl_number', 'first_name', 'last_name'])
    df = df.with_columns([
        pl.col('acbl_number').cast(pl.Utf8),
        pl.col('first_name').fill_null(''),
        pl.col('last_name').fill_null(''),
    ])
    names = (df['first_name'] + ' ' + df['last_name']).str.strip_chars()
    return dict(zip(df['acbl_number'].to_list(), names.to_list()))


@st.cache_data(show_spinner=False)
def load_player_info_df(filename=None):
    path = filename or resolve_data_file('acbl_player_info.parquet')
    return pl.read_parquet(path)


@st.cache_data(show_spinner=False)
def load_club_df(filename=None):
    path = filename or resolve_data_file('acbl_club_clubs_cleaned.parquet')
    return pl.read_parquet(path)


def load_club_hand_records(filename):
    return load_hand_records(filename)


def load_tournament_hand_records(filename):
    return load_hand_records(filename)


def load_club_board_results(filename, **kwargs):
    return load_board_results(filename, **kwargs)


def load_tournament_board_results(filename, **kwargs):
    return load_board_results(filename, **kwargs)


# todo: is this obsolete? Seems to freeze or slow webpages.
#@st.cache_resource()
def duckdb_query(query):
    return duckdb.query(query).to_df()

    
def CreateCheckBoxesFromColumns(column_names,mandatory_columns,special_columns,show_cbd_default):
    cb_d = mandatory_columns
    columns = ', '.join([v if k not in special_columns else special_columns[k][1] if special_columns[k][2] is None else special_columns[k][1]+' AS '+special_columns[k][2] for k,v in cb_d.items()]) # required columns
    for col in list(column_names)+list(special_columns.keys()):
        as_name = col
        if col not in cb_d and not col.startswith('__'):
            if col in special_columns:
                show_cb = special_columns[col][0]
                value = special_columns[col][1]
                if special_columns[col][2] is not None:
                    as_name = special_columns[col][2]
                    value += ' AS '+as_name
            else:
                show_cb = show_cbd_default
                value = col
            if show_cb:
                checked = st.sidebar.checkbox(as_name,value=show_cb,key='Player-CheckBox-'+as_name)
                cb_d[col] = checked
                if checked:
                    if columns == '':
                        columns = value
                    else:
                        columns += ', '+value
    return columns


# todo: remove stat_column in favor of column_filter?
def ShowCharts(selected_df,selected_charts,stat_column=None,column_filter='.*'):
    # Check if dataframe is empty
    if selected_df.height == 0:
        st.info("No data available for charts.")
        return
    
    # Convert polars DataFrame to pandas for plotting
    # This is temporary until we implement native polars plotting
    selected_df_pd = selected_df.to_pandas()
    
    available_charts = []
    for chart in selected_charts:
        stat_column_split = chart.replace(' ','').split(',')
        if all([col in selected_df.columns for col in stat_column_split]):
            available_charts.append(stat_column_split)

    selected_df_len = len(selected_df)
    if 'Declarer' in selected_df.columns:
        declarer_groups = (
            selected_df
            .group_by(['Declarer', 'Declarer_Name'])
            .agg(pl.len())
        )
        st.info(f"Selected: Unique declarers:{len(declarer_groups)} rows:{selected_df_len} charts:{available_charts}")
    else:
        declarer_groups = pl.DataFrame()

    figsize = (26,2)
    if 0 < len(declarer_groups) <= 10:
        # For small number of declarers, show unaggregated data
        for stat_column_split in available_charts:
            if len(stat_column_split) == 1:
                players_d = {}
                for col in stat_column_split:
                    for row in declarer_groups.iter_rows(named=True):
                        declarer, declarer_name = row['Declarer'], row['Declarer_Name']
                        s = selected_df.filter(pl.col('Declarer') == declarer)[col]
                        
                        # Convert to pandas for value_counts operation
                        s_pd = s.to_pandas()
                        if pl.Series(s).dtype in [pl.Float32, pl.Float64]:
                            for r in [2,1,0,-1]:
                                vc = s_pd.round(r).value_counts(normalize=True).sort_index()
                                if len(vc) <= 100:
                                    break
                        else:
                            vc = s_pd.value_counts(normalize=True).sort_index()
                        players_d[f'({declarer},{declarer_name},{len(vc)})'] = vc
                
                title = f"Frequency Percentage of {', '.join(stat_column_split)} {', '.join(players_d.keys())}"
                if players_d:  # Check if players_d is not empty
                    try:
                        df_to_plot = pd.DataFrame(players_d)
                        if df_to_plot.empty or df_to_plot.shape[0] == 0:
                            st.info(f"No data to plot for chart: {', '.join(stat_column_split)}")
                            continue
                        ax = df_to_plot.plot(kind='bar',figsize=figsize,title=title)
                        ax.legend(title='(Player Number, Player Name, Rows Found, Mean)')
                    except Exception as e:
                        st.warning(f"Failed to create chart for {', '.join(stat_column_split)}: {str(e)}")
                        continue
                else:
                    st.info(f"No data available for chart: {', '.join(stat_column_split)}")
                    continue
            else:
                selected_cols = selected_df.select(stat_column_split).to_pandas()
                ax = selected_cols.hist(figsize=figsize)
            st.pyplot(plt,clear_figure=True)
    else:
        for stat_column_split in available_charts:
            if len(stat_column_split) == 3:
                # 3 variable heat map
                cross_table = (
                    selected_df
                    .group_by([stat_column_split[0], stat_column_split[1]])
                    .agg(pl.col(stat_column_split[2]).mean())
                    .pivot(
                        values=stat_column_split[2],
                        index=stat_column_split[0],
                        columns=stat_column_split[1]
                    )
                    .to_pandas()
                )
                streamlitlib.plot_heatmap(cross_table, zlabel=stat_column_split[2])
                del cross_table
            else:
                d = {}
                for col in stat_column_split:
                    s = selected_df.select(col).to_pandas()[col]
                    if pd.api.types.is_float_dtype(s):
                        for r in [2,1,0,-1]:
                            d[col] = s.round(r).value_counts(normalize=True).sort_index()
                            if len(d[col]) <= 100:
                                break
                    else:
                        d[col] = s.value_counts(normalize=True).sort_index()
                
                if d:  # Check if d is not empty
                    try:
                        df_to_plot = pd.DataFrame(d)
                        if df_to_plot.empty or df_to_plot.shape[0] == 0:
                            st.info(f"No data to plot for chart: {', '.join(stat_column_split)}")
                            continue
                        ax = df_to_plot.plot(
                            kind='bar',
                            xlabel=stat_column_split,
                            ylabel="Percentage Frequency",
                            title=f"Frequency of {', '.join(d.keys())} values. {selected_df_len} observations.",
                            figsize=figsize
                        )
                    except Exception as e:
                        st.warning(f"Failed to create chart for {', '.join(stat_column_split)}: {str(e)}")
                        continue
                else:
                    st.info(f"No data available for chart: {', '.join(stat_column_split)}")
                    continue
                st.pyplot(plt,clear_figure=True)
                del d
                
                if False: # altair charting works but needs some niceification e.g. width.
                    chart_df = selected_df[stat_column_split].melt(var_name='column')
                    chart = alt.Chart(chart_df).mark_bar().encode(
                        x='column',
                        y='count()',
                        column='value:O',
                        color='column'
                    )
                    st.altair_chart(chart)
                    del split_df, chart_df
