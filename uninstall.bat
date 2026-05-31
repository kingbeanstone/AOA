@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ANR 분석 도구 제거
echo.

set "TOOL_DIR=%USERPROFILE%\.anr-tool"
set "CLAUDE_CMD=%USERPROFILE%\.claude\commands\anr.md"
set "CLINE_WORKFLOW=%USERPROFILE%\Documents\Cline\Workflows\anr.md"
set "CURSOR_SKILL_DIR=%USERPROFILE%\.cursor\skills\anr"

REM 구버전
set "OLD_CLAUDE_MD=%USERPROFILE%\.claude\CLAUDE.md"
set "OLD_CLINE_RULE=%USERPROFILE%\Documents\Cline\Rules\zz-anr-rule.md"
set "OLD_CLINE_SKILL=%USERPROFILE%\.cline\skills\anr"

REM 1. Claude Code 슬래시 커맨드
if exist "%CLAUDE_CMD%" del /Q "%CLAUDE_CMD%" && echo   Claude Code /anr 커맨드 제거

REM 2. Cline 워크플로우
if exist "%CLINE_WORKFLOW%" del /Q "%CLINE_WORKFLOW%" && echo   Cline /anr 워크플로우 제거

REM 3. Cursor 스킬
if exist "%CURSOR_SKILL_DIR%" (
    rd /s /q "%CURSOR_SKILL_DIR%"
    echo   Cursor /anr 스킬 제거
)

REM 4. 구버전 — Cline 글로벌 룰 / 스킬 폴더
if exist "%OLD_CLINE_RULE%" del /Q "%OLD_CLINE_RULE%" && echo   옛 Cline 글로벌 룰 제거
if exist "%OLD_CLINE_SKILL%" rd /s /q "%OLD_CLINE_SKILL%" && echo   옛 Cline 스킬 폴더 제거

REM 5. 구버전 — Claude Code import 한 줄
if exist "%OLD_CLAUDE_MD%" (
    findstr /C:"anr-tool/zz-anr-rule.md" "%OLD_CLAUDE_MD%" >nul 2>&1
    if !errorlevel!==0 (
        findstr /V /C:"anr-tool/zz-anr-rule.md" "%OLD_CLAUDE_MD%" > "%OLD_CLAUDE_MD%.tmp"
        move /Y "%OLD_CLAUDE_MD%.tmp" "%OLD_CLAUDE_MD%" >nul
        echo   옛 Claude Code import 제거 ^(CLAUDE.md 나머지 유지^)
    )
)

REM 6. 구버전 — Cursor state.vscdb 마커 블록
set "PYTHON="
where py >nul 2>&1 && set "PYTHON=py"
if not defined PYTHON ( where python >nul 2>&1 && set "PYTHON=python" )
if not defined PYTHON ( where python3 >nul 2>&1 && set "PYTHON=python3" )
REM goto 가드: echo 줄의 이스케이프 안 된 괄호가 if(...) 블록을 깨뜨리는 것 방지
if not defined PYTHON goto AFTER_CURSOR_REMOVE
set "CURSOR_PY=%TEMP%\anr_cursor_remove.py"
> "!CURSOR_PY!" echo import os, sys, sqlite3, re
>> "!CURSOR_PY!" echo db_path = os.path.join(os.environ.get('APPDATA',''), 'Cursor', 'User', 'globalStorage', 'state.vscdb')
>> "!CURSOR_PY!" echo if not os.path.isfile(db_path): sys.exit(0)
>> "!CURSOR_PY!" echo START = '^<!-- ANR-TOOL-START --^>'; END = '^<!-- ANR-TOOL-END --^>'
>> "!CURSOR_PY!" echo try:
>> "!CURSOR_PY!" echo     conn = sqlite3.connect(db_path); cur = conn.cursor()
>> "!CURSOR_PY!" echo     cur.execute("SELECT value FROM ItemTable WHERE key='aicontext.personalContext'")
>> "!CURSOR_PY!" echo     row = cur.fetchone()
>> "!CURSOR_PY!" echo     if not row: conn.close(); sys.exit(0)
>> "!CURSOR_PY!" echo     pattern = re.compile(re.escape(START) + '.*?' + re.escape(END), re.DOTALL)
>> "!CURSOR_PY!" echo     if pattern.search(row[0]):
>> "!CURSOR_PY!" echo         cur.execute("UPDATE ItemTable SET value=? WHERE key='aicontext.personalContext'", (pattern.sub('', row[0]).strip(),))
>> "!CURSOR_PY!" echo         conn.commit(); print('  옛 Cursor 전역 룰 블록 제거 (state.vscdb)')
>> "!CURSOR_PY!" echo     conn.close()
>> "!CURSOR_PY!" echo except Exception: pass
%PYTHON% "!CURSOR_PY!"
del /q "!CURSOR_PY!" >nul 2>&1
:AFTER_CURSOR_REMOVE

REM 7. 공용 도구 폴더
if exist "%TOOL_DIR%\anr_parse.py"    del /Q "%TOOL_DIR%\anr_parse.py"    && echo   파서 제거
if exist "%TOOL_DIR%\zz-anr-rule.md"  del /Q "%TOOL_DIR%\zz-anr-rule.md"
if exist "%TOOL_DIR%\anr-rule.md"     del /Q "%TOOL_DIR%\anr-rule.md"
del /Q "%~f0" >nul 2>&1
rd "%TOOL_DIR%" >nul 2>&1

echo.
echo 제거 완료.
pause
