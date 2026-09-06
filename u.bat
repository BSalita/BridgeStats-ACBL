@echo off
rem Sync BridgeStats parquet from the pipeline (no pkl files).
rem Large Stage 3c board-results monoliths stay on E: / acbl-pipeline and are
rem found at runtime via resolve_data_file. Only the small lookup/narrow files
rem are copied into data\ and published to prod.

set "acbl_source=e:\bridge\data\acbl"
set "prod_bridgestats=\\X1-pro-470-1tb\c\sw\bridge\ML-Contract-Bridge\src\bridgestats-acbl\data"
rem Do not treat C:\sw\bridge\...\data as prod: that path is also the OneDrive
rem junction on the data host (P620). Detect the prod box by computer name.

if not exist "data\" (
    mkdir data
    if errorlevel 1 exit /b 1
)

if exist "%acbl_source%\" (
    for %%F in (
        acbl_club_hand_records_augmented_narrow.parquet
        acbl_tournament_hand_records_augmented_narrow.parquet
        acbl_player_info.parquet
        acbl_club_clubs_cleaned.parquet
    ) do (
        if exist "%acbl_source%\%%F" (
            xcopy "%acbl_source%\%%F" "data\" /D /Y
            if errorlevel 1 exit /b 1
        )
    )
)

if /i "%COMPUTERNAME%"=="X1-PRO-470-1TB" (
    echo Already on prod host; using local data\ and skipping UNC publish.
    exit /b 0
)

if not exist "%prod_bridgestats%\" (
    mkdir "%prod_bridgestats%"
    if errorlevel 1 (
        echo Prod data directory not reachable: %prod_bridgestats%
        exit /b 1
    )
)

for %%F in (
    acbl_club_hand_records_augmented_narrow.parquet
    acbl_tournament_hand_records_augmented_narrow.parquet
    acbl_player_info.parquet
    acbl_club_clubs_cleaned.parquet
) do (
    if exist "data\%%F" (
        xcopy "data\%%F" "%prod_bridgestats%\" /D /Y
        if errorlevel 1 exit /b 1
    )
)

exit /b 0
