@echo off
REM OBSOLETE: Local junctions are no longer required.
REM Use each project's .venv (Python 3.12) with monorepo_src.pth so sibling
REM packages under src\ (mlBridge, streamlitlib, chatlib, acbllib) import
REM without mklink/J. Entry points also resolve ../lib when ./lib is missing.
REM Keeping this file only as historical documentation of the old layout.
echo mklinks.bat is obsolete. Use .venv + sibling src imports instead.
exit /b 0
REM echo symlinks appear to work following this procedure. 1) mklink/J 2) git add 3) append sys.path 4) import
REM
REM mklink/J mlBridge ..\mlBridge
REM mklink/J acbllib ..\acbllib
REM #mklink/J chatlib ..\chatlib
REM mklink/J streamlitlib ..\streamlitlib
REM
REM git add mlBridgeLib\mlBridgeLib.py
REM git add acbllib
REM #git add chatlib\chatlib.py
REM git add streamlitlib\streamlitlib.py
REM
REM echo change python file to add all paths. e.g. sys.path.append(str(pathlib.Path.cwd().joinpath('mlBridgeLib'))) # global
REM echo afterwards import libs. e.g. import mlBridgeLib
REM
REM
