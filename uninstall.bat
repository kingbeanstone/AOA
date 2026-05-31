@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ANR 분석 도구 제거
echo.

set "TOOL_DIR=%USERPROFILE%\.anr-tool"
set "CLINE_RULES=%USERPROFILE%\Documents\Cline\Rules"
set "CLAUDE_MD=%USERPROFILE%\.claude\CLAUDE.md"

REM 1. Cline 룰
if exist "%CLINE_RULES%\zz-anr-rule.md" del /Q "%CLINE_RULES%\zz-anr-rule.md"

REM 2. Claude Code import 한 줄만 제거 (나머지 보존)
if exist "%CLAUDE_MD%" (
    findstr /V /C:"anr-tool/zz-anr-rule.md" "%CLAUDE_MD%" > "%CLAUDE_MD%.tmp"
    move /Y "%CLAUDE_MD%.tmp" "%CLAUDE_MD%" >nul
)

REM 3. Cursor 전역 룰 제거 (ANR-TOOL 마커 블록만 삭제)
set "PYTHON="
where py >nul 2>&1 && set "PYTHON=py"
if not defined PYTHON ( where python >nul 2>&1 && set "PYTHON=python" )
if not defined PYTHON ( where python3 >nul 2>&1 && set "PYTHON=python3" )
if defined PYTHON (
    set "CURSOR_PY=%TEMP%\anr_cursor_remove.py"
    > "!CURSOR_PY!" echo import os, sys, sqlite3, re
    >> "!CURSOR_PY!" echo db_path = os.path.join(os.environ.get('APPDATA',''), 'Cursor', 'User', 'globalStorage', 'state.vscdb')
    >> "!CURSOR_PY!" echo if not os.path.isfile(db_path): sys.exit(0)
    >> "!CURSOR_PY!" echo START = '<!-- ANR-TOOL-START -->'; END = '<!-- ANR-TOOL-END -->'
    >> "!CURSOR_PY!" echo conn = sqlite3.connect(db_path); cur = conn.cursor()
    >> "!CURSOR_PY!" echo cur.execute("SELECT value FROM ItemTable WHERE key='aicontext.personalContext'")
    >> "!CURSOR_PY!" echo row = cur.fetchone()
    >> "!CURSOR_PY!" echo if not row: conn.close(); sys.exit(0)
    >> "!CURSOR_PY!" echo pattern = re.compile(re.escape(START) + '.*?' + re.escape(END), re.DOTALL)
    >> "!CURSOR_PY!" echo if pattern.search(row[0]):
    >> "!CURSOR_PY!" echo     cur.execute("UPDATE ItemTable SET value=? WHERE key='aicontext.personalContext'", (pattern.sub('', row[0]).strip(),)); conn.commit(); print('  Cursor 전역 룰 제거 완료')
    >> "!CURSOR_PY!" echo conn.close()
    %PYTHON% "!CURSOR_PY!"
    del /q "!CURSOR_PY!" >nul 2>&1
)

REM 4. 공용 도구 폴더
if exist "%TOOL_DIR%\anr_parse.py"   del /Q "%TOOL_DIR%\anr_parse.py"
if exist "%TOOL_DIR%\zz-anr-rule.md" del /Q "%TOOL_DIR%\zz-anr-rule.md"
del /Q "%~f0" >nul 2>&1
rd "%TOOL_DIR%" >nul 2>&1

echo 제거 완료.
pause
