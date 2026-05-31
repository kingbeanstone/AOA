@echo off
set "ARG1=%~1"
if /I not "%ARG1%"=="skip" chcp 65001 > nul
setlocal enabledelayedexpansion

REM ============================================================
REM   ANR 분석 도구 설치 스크립트 (Windows)
REM   Cline / Cursor / Claude Code 공용 — 슬래시 커맨드 / 스킬 방식.
REM   - 파서(anr_parse.py)    → %USERPROFILE%\.anr-tool\
REM   - Claude Code 슬래시    → %USERPROFILE%\.claude\commands\anr.md
REM   - Cline 스킬            → %USERPROFILE%\.cline\skills\anr\SKILL.md
REM   - Cursor 스킬           → %USERPROFILE%\.cursor\skills\anr\SKILL.md
REM ============================================================

if /I not "%ARG1%"=="skip" (
    echo.
    echo ============================================================
    echo   ANR 분석 도구 설치 ^(Cline / Cursor / Claude Code^)
    echo ============================================================
    echo.
)

REM --- 설정 --------------------------------------------------
set "REPO=kingbeanstone/AOA"
set "BRANCH=main"
set "DL_URL=https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip"
set "TMP_ZIP=%TEMP%\anr-tool-latest.zip"
set "TMP_DIR=%TEMP%\anr-tool-latest"
set "TOOL_DIR=%USERPROFILE%\.anr-tool"
set "CLAUDE_CMDS=%USERPROFILE%\.claude\commands"
set "CLINE_SKILL_DIR=%USERPROFILE%\.cline\skills\anr"
set "CURSOR_SKILL_DIR=%USERPROFILE%\.cursor\skills\anr"

REM 구버전(글로벌 룰 / 워크플로우) 정리 대상
set "OLD_CLAUDE_MD=%USERPROFILE%\.claude\CLAUDE.md"
set "OLD_CLINE_RULE=%USERPROFILE%\Documents\Cline\Rules\zz-anr-rule.md"
set "OLD_CLINE_WORKFLOW=%USERPROFILE%\Documents\Cline\Workflows\anr.md"
set "OLD_TOOL_RULE=%USERPROFILE%\.anr-tool\zz-anr-rule.md"

REM --- 0. GitHub 최신 버전 다운로드 -------------------------
echo [0/6] GitHub에서 최신 버전 다운로드 중...
if /I "%ARG1%"=="skip" (
    echo       OK: 최신 버전 준비 완료
    set "PAYLOAD=%~dp0payload"
    goto SKIP_DOWNLOAD
)
set "DL_OK=0"
curl.exe -fsSL "%DL_URL%" -o "%TMP_ZIP%" >nul 2>&1
if !errorlevel!==0 set "DL_OK=1"
if !DL_OK!==0 (
    powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%DL_URL%' -OutFile '%TMP_ZIP%'" >nul 2>&1
    if !errorlevel!==0 set "DL_OK=1"
)
if !DL_OK!==1 (
    powershell -Command "$ProgressPreference='SilentlyContinue'; Expand-Archive -Path '%TMP_ZIP%' -DestinationPath '%TMP_DIR%' -Force" >nul 2>&1
    set "EXTRACTED="
    for /D %%i in ("%TMP_DIR%\AOA-*") do set "EXTRACTED=%%i"
    if defined EXTRACTED (
        set "PAYLOAD=!EXTRACTED!\payload"
        echo       OK: GitHub 최신 버전 다운로드 완료
    ) else (
        echo       추출 실패 -- 로컬 파일로 설치합니다.
        set "PAYLOAD=%~dp0payload"
    )
) else (
    echo       GitHub 연결 실패 -- 로컬 파일로 설치합니다.
    set "PAYLOAD=%~dp0payload"
)
:SKIP_DOWNLOAD
echo.

REM --- 1. Python 확인 ----------------------------------------
echo [1/6] Python 확인 중...
set "PYTHON="
where py >nul 2>&1 && set "PYTHON=py"
if not defined PYTHON (
    where python >nul 2>&1 && set "PYTHON=python"
)
if not defined PYTHON (
    where python3 >nul 2>&1 && set "PYTHON=python3"
)
if defined PYTHON (
    echo       OK: %PYTHON% 사용 가능
) else (
    echo       경고: Python이 설치되지 않은 것 같습니다.
    echo             사내 SW센터에서 Python 설치 후 다시 실행하세요.
    echo             ^(설치 자체는 계속 진행됩니다^)
)
echo.

REM --- payload 파일 위치 확인 --------------------------------
if not exist "%PAYLOAD%\anr-rule.md" (
    echo [오류] payload 폴더에서 필수 파일을 찾을 수 없습니다.
    echo        경로: %PAYLOAD%
    if /I not "%ARG1%"=="skip" (
        if exist "%TMP_ZIP%" del /q "%TMP_ZIP%" >nul 2>&1
        if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>&1
    )
    pause
    exit /b 1
)
if not exist "%PAYLOAD%\anr_parse.py" (
    echo [오류] payload 폴더에서 파서 파일을 찾을 수 없습니다.
    echo        경로: %PAYLOAD%
    pause
    exit /b 1
)

REM --- payload 에서 버전 추출 --------------------------------
for /f "tokens=3 delims= " %%a in ('findstr /B "__version__" "%PAYLOAD%\anr_parse.py"') do set "PARSER_VER=%%~a"
for /f "tokens=3 delims= " %%a in ('findstr /B "<!-- 버전:" "%PAYLOAD%\anr-rule.md"') do set "RULE_VER=%%a"
if not defined PARSER_VER set "PARSER_VER=?"
if not defined RULE_VER set "RULE_VER=?"

REM --- 2. 구버전(글로벌 룰 / 워크플로우) 정리 -----------------
echo [2/6] 구버전(글로벌 룰/워크플로우) 정리
set "CLEANED=0"
if exist "%OLD_CLINE_RULE%" (
    del /Q "%OLD_CLINE_RULE%"
    echo       - 옛 Cline 글로벌 룰 제거
    set "CLEANED=1"
)
if exist "%OLD_CLINE_WORKFLOW%" (
    del /Q "%OLD_CLINE_WORKFLOW%"
    echo       - 옛 Cline 워크플로우 제거
    set "CLEANED=1"
)
if exist "%OLD_CLAUDE_MD%" (
    findstr /C:"anr-tool/zz-anr-rule.md" "%OLD_CLAUDE_MD%" >nul 2>&1
    if !errorlevel!==0 (
        findstr /V /C:"anr-tool/zz-anr-rule.md" "%OLD_CLAUDE_MD%" > "%OLD_CLAUDE_MD%.tmp"
        move /Y "%OLD_CLAUDE_MD%.tmp" "%OLD_CLAUDE_MD%" >nul
        echo       - 옛 Claude Code import 제거 ^(CLAUDE.md 나머지 보존^)
        set "CLEANED=1"
    )
)
if exist "%OLD_TOOL_RULE%" (
    del /Q "%OLD_TOOL_RULE%"
    echo       - 옛 룰 정본 제거
    set "CLEANED=1"
)
REM 옛 Cursor state.vscdb 마커 블록 제거 (Python 있을 때만)
if defined PYTHON (
    set "CURSOR_PY=%TEMP%\anr_cursor_cleanup.py"
    > "!CURSOR_PY!" echo import os, sys, sqlite3, re
    >> "!CURSOR_PY!" echo db_path = os.path.join(os.environ.get('APPDATA',''), 'Cursor', 'User', 'globalStorage', 'state.vscdb')
    >> "!CURSOR_PY!" echo if not os.path.isfile(db_path): sys.exit(1)
    >> "!CURSOR_PY!" echo START = '^<!-- ANR-TOOL-START --^>'; END = '^<!-- ANR-TOOL-END --^>'
    >> "!CURSOR_PY!" echo try:
    >> "!CURSOR_PY!" echo     conn = sqlite3.connect(db_path); cur = conn.cursor()
    >> "!CURSOR_PY!" echo     cur.execute("SELECT value FROM ItemTable WHERE key='aicontext.personalContext'")
    >> "!CURSOR_PY!" echo     row = cur.fetchone()
    >> "!CURSOR_PY!" echo     if not row: conn.close(); sys.exit(1)
    >> "!CURSOR_PY!" echo     pattern = re.compile(re.escape(START) + '.*?' + re.escape(END), re.DOTALL)
    >> "!CURSOR_PY!" echo     if pattern.search(row[0]):
    >> "!CURSOR_PY!" echo         cur.execute("UPDATE ItemTable SET value=? WHERE key='aicontext.personalContext'", (pattern.sub('', row[0]).strip(),))
    >> "!CURSOR_PY!" echo         conn.commit(); conn.close(); sys.exit(0)
    >> "!CURSOR_PY!" echo     conn.close(); sys.exit(1)
    >> "!CURSOR_PY!" echo except Exception: sys.exit(1)
    %PYTHON% "!CURSOR_PY!" >nul 2>&1
    if !errorlevel!==0 (
        echo       - 옛 Cursor 전역 룰 블록 제거 ^(state.vscdb^)
        set "CLEANED=1"
    )
    del /q "!CURSOR_PY!" >nul 2>&1
)
if "!CLEANED!"=="0" echo       OK: 정리할 구버전 없음
echo.

REM --- 3. 공용 파서 배치 -------------------------------------
echo [3/6] 파서 배치  ^(anr_parse.py v%PARSER_VER%^)
echo       위치: %TOOL_DIR%\anr_parse.py
if not exist "%TOOL_DIR%" mkdir "%TOOL_DIR%"
copy /Y "%PAYLOAD%\anr_parse.py" "%TOOL_DIR%\anr_parse.py" >nul
if !errorlevel! neq 0 (
    echo       실패. 파일 복사 오류.
    pause & exit /b 1
)
if exist "%~dp0uninstall.bat" copy /Y "%~dp0uninstall.bat" "%TOOL_DIR%\uninstall.bat" >nul 2>&1
echo       OK
echo.

REM --- 4. Claude Code 슬래시 커맨드 배치 ---------------------
echo [4/6] Claude Code /anr 슬래시 커맨드 배치  ^(룰 v%RULE_VER%^)
echo       위치: %CLAUDE_CMDS%\anr.md
if not exist "%CLAUDE_CMDS%" mkdir "%CLAUDE_CMDS%"
copy /Y "%PAYLOAD%\anr-rule.md" "%CLAUDE_CMDS%\anr.md" >nul
if !errorlevel! neq 0 (
    echo       실패.
    pause & exit /b 1
)
echo       OK
echo.

REM --- 5. Cline 스킬 배치 ------------------------------------
echo [5/6] Cline /anr 스킬 배치  ^(룰 v%RULE_VER%^)
echo       위치: %CLINE_SKILL_DIR%\SKILL.md
if not exist "%CLINE_SKILL_DIR%" mkdir "%CLINE_SKILL_DIR%"
copy /Y "%PAYLOAD%\anr-rule.md" "%CLINE_SKILL_DIR%\SKILL.md" >nul
if !errorlevel! neq 0 (
    echo       실패.
    pause & exit /b 1
)
echo       OK
echo.

REM --- 6. Cursor 스킬 배치 -----------------------------------
echo [6/6] Cursor /anr 스킬 배치  ^(룰 v%RULE_VER%^)
echo       위치: %CURSOR_SKILL_DIR%\SKILL.md
if not exist "%CURSOR_SKILL_DIR%" mkdir "%CURSOR_SKILL_DIR%"
copy /Y "%PAYLOAD%\anr-rule.md" "%CURSOR_SKILL_DIR%\SKILL.md" >nul
if !errorlevel! neq 0 (
    echo       실패.
    pause & exit /b 1
)
echo       OK
echo.

REM --- 임시 파일 정리 ----------------------------------------
if /I not "%ARG1%"=="skip" (
    if exist "%TMP_ZIP%" del /q "%TMP_ZIP%" >nul 2>&1
    if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>&1
)

REM --- 완료 메시지 -------------------------------------------
echo ============================================================
echo   설치 완료
echo ============================================================
echo.
echo 설치된 버전:
echo   파서  : anr_parse.py    v%PARSER_VER%
echo   룰    : anr-rule.md     v%RULE_VER%
echo.
echo 사용 방법 ^(공통 -- 모든 툴에서 동일^):
echo   AI 어시스턴트 채팅에서 슬래시 커맨드로 호출:
echo      /anr C:\path\to\dumpstate.txt
echo      /anr "C:\My Logs\dump.txt"
echo.
echo   - Claude Code: 새 세션부터 즉시 사용 가능
echo   - Cline      : VSCode 재시작 후 사용
echo   - Cursor     : Cursor 재시작 후 사용
echo.
echo 설치된 위치:
echo   파서        : %TOOL_DIR%\anr_parse.py
echo   Claude Code : %CLAUDE_CMDS%\anr.md
echo   Cline       : %CLINE_SKILL_DIR%\SKILL.md
echo   Cursor      : %CURSOR_SKILL_DIR%\SKILL.md
echo.
echo 제거하려면: %TOOL_DIR%\uninstall.bat 실행
echo.
pause
endlocal
