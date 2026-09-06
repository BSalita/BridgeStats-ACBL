@echo off
rem Sync BridgeStats data the same way elo\u.bat and acbl-pipeline\u.bat do:
rem   1) refresh safe artifacts from E:\ when this is the data host
rem   2) publish the loadable app files to the prod host
rem
rem Do NOT copy acbl_*_board_results_augmented.parquet from E:\. Those Stage 3c
rem files are ~81 GB / ~20 GB and the app still does a full in-memory read.
rem Keep the existing loadable copies in data\ until the lazy-load rewrite.

set "acbl_source=e:\bridge\data\acbl"
set "prod_bridgestats=\\X1-pro-470-1tb\c\sw\bridge\ML-Contract-Bridge\src\bridgestats\data"

if not exist "data\" (
    mkdir data
    if errorlevel 1 exit /b 1
)

rem Small / legacy lookup files that still fit in RAM. Skip if E: is absent
rem (deploy running on the prod host).
if exist "%acbl_source%\" (
    for %%F in (
        acbl_club_hand_records_augmented_narrow.parquet
        acbl_tournament_hand_records_augmented_narrow.parquet
        acbl_club_player_name_dict.pkl
        acbl_tournament_player_name_dict.pkl
        acbl_club_hand_records_d.pkl
        acbl_tournament_hand_records_d.pkl
        acbl_player_info.parquet
    ) do (
        if exist "%acbl_source%\%%F" (
            xcopy "%acbl_source%\%%F" "data\" /D /Y
            if errorlevel 1 exit /b 1
        )
    )
    if exist "%acbl_source%\acbl_clubs.parquet" (
        xcopy "%acbl_source%\acbl_clubs.parquet" "data\" /D /Y
        if errorlevel 1 exit /b 1
    )
)

rem Files the running app requires. board_results stay the local loadable copies.
for %%F in (
    acbl_club_board_results_augmented.parquet
    acbl_tournament_board_results_augmented.parquet
    acbl_club_hand_records_augmented_narrow.parquet
    acbl_tournament_hand_records_augmented_narrow.parquet
    acbl_club_player_name_dict.pkl
    acbl_tournament_player_name_dict.pkl
    acbl_club_hand_records_d.pkl
    acbl_tournament_hand_records_d.pkl
    acbl_clubs.parquet
    acbl_player_info.parquet
) do (
    if not exist "data\%%F" (
        echo Missing required data file: data\%%F
        exit /b 1
    )
)

if not exist "%prod_bridgestats%\" (
    mkdir "%prod_bridgestats%"
    if errorlevel 1 (
        echo Prod data directory not reachable: %prod_bridgestats%
        exit /b 1
    )
)

for %%F in (
    acbl_club_board_results_augmented.parquet
    acbl_tournament_board_results_augmented.parquet
    acbl_club_hand_records_augmented_narrow.parquet
    acbl_tournament_hand_records_augmented_narrow.parquet
    acbl_club_player_name_dict.pkl
    acbl_tournament_player_name_dict.pkl
    acbl_club_hand_records_d.pkl
    acbl_tournament_hand_records_d.pkl
    acbl_clubs.parquet
    acbl_player_info.parquet
) do (
    xcopy "data\%%F" "%prod_bridgestats%\" /D /Y
    if errorlevel 1 exit /b 1
)

exit /b 0
