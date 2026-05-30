@echo off
set "ARG1=%~1"
if /I not "%ARG1%"=="skip" chcp 65001 > nul
setlocal enabledelayedexpansion

REM ============================================================
REM   ANR 분석 도구 설치 스크립트 (Windows)
REM   Cline / Cursor / Claude Code 공용.
REM   - 파서(anr_parse.py)는 공용이라 %USERPROFILE%\.anr-tool 에 한 번만 배치
REM   - 룰(zz-anr-rule.md)은 툴마다 읽는 위치가 달라 각 위치에 배치
REM   - Cline / Claude Code 는 고정 전역 경로라 미설치여도 미리 배치(무해)
REM   - Cursor 는 전역 룰 파일이 없어 .mdc 정본 준비 후 안내
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
set "CLINE_RULES=%USERPROFILE%\Documents\Cline\Rules"
set "CLAUDE_DIR=%USERPROFILE%\.claude"
set "CLAUDE_MD=%CLAUDE_DIR%\CLAUDE.md"

REM --- 0. GitHub 최신 버전 다운로드 -------------------------
echo [0/5] GitHub에서 최신 버전 다운로드 중...
if /I "%ARG1%"=="skip" (
    echo       OK: 최신 버전 준비 완료
    set "PAYLOAD=%~dp0payload"
    goto SKIP_DOWNLOAD
)
set "DL_OK=0"

REM 1차: curl.exe (Windows 10 1803 이상 내장)
curl.exe -fsSL "%DL_URL%" -o "%TMP_ZIP%" >nul 2>&1
if !errorlevel!==0 set "DL_OK=1"

REM 2차: PowerShell Invoke-WebRequest (curl.exe 없는 구형 환경 폴백)
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
echo [1/5] Python 확인 중...
where py >nul 2>&1
if %errorlevel%==0 (
    echo       OK: py 명령 사용 가능
) else (
    where python >nul 2>&1
    if !errorlevel!==0 (
        echo       OK: python 명령 사용 가능
    ) else (
        echo       경고: Python이 설치되지 않은 것 같습니다.
        echo             사내 SW센터에서 Python 설치 후 다시 실행하세요.
        echo             ^(설치 자체는 계속 진행됩니다^)
    )
)
echo.

REM --- payload 파일 위치 확인 --------------------------------
if not exist "%PAYLOAD%\zz-anr-rule.md" (
    echo [오류] payload 폴더에서 룰 파일을 찾을 수 없습니다.
    echo        경로: %PAYLOAD%
    echo        GitHub 연결에 실패한 경우 payload\ 폴더가 install.bat과 같은 위치에 있는지 확인하세요.
    if /I not "%ARG1%"=="skip" (
        if exist "%TMP_ZIP%" del /q "%TMP_ZIP%" >nul 2>&1
        if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>&1
    )
    pause
    exit /b 1
)

REM --- payload 에서 버전 추출 (하드코딩 방지) -------------
for /f "tokens=3 delims= " %%a in ('findstr /B "__version__" "%PAYLOAD%\anr_parse.py"') do set "PARSER_VER=%%~a"
for /f "tokens=3 delims= " %%a in ('findstr /B "<!-- 버전:" "%PAYLOAD%\zz-anr-rule.md"') do set "RULE_VER=%%a"
if not defined PARSER_VER set "PARSER_VER=?"
if not defined RULE_VER set "RULE_VER=?"

REM --- 2. 공용 파일 배치 (파서 + 룰 정본 + Cursor mdc) -----
echo [2/5] 공용 파일 배치  ^(파서 v%PARSER_VER% / 룰 v%RULE_VER%^)
echo       위치: %TOOL_DIR%
if not exist "%TOOL_DIR%" mkdir "%TOOL_DIR%"
copy /Y "%PAYLOAD%\anr_parse.py" "%TOOL_DIR%\anr_parse.py" >nul
if !errorlevel! neq 0 (
    echo       실패.
    pause
    exit /b 1
)
copy /Y "%PAYLOAD%\zz-anr-rule.md" "%TOOL_DIR%\zz-anr-rule.md" >nul
REM Cursor 프로젝트 룰(.cursor/rules)용 .mdc 정본 생성 (frontmatter + 룰 본문)
set "CURSOR_MDC=%TOOL_DIR%\anr-analysis.mdc"
> "%CURSOR_MDC%" echo ---
>> "%CURSOR_MDC%" echo description: Android ANR dumpstate analysis. Apply when an ANR/dumpstate file path is given with an analysis request (path + "anr").
>> "%CURSOR_MDC%" echo alwaysApply: false
>> "%CURSOR_MDC%" echo ---
>> "%CURSOR_MDC%" echo.
type "%TOOL_DIR%\zz-anr-rule.md" >> "%CURSOR_MDC%"
if exist "%~dp0uninstall.bat" copy /Y "%~dp0uninstall.bat" "%TOOL_DIR%\uninstall.bat" >nul 2>&1
echo       OK
echo.

REM --- 3. Cline 룰 배치 (고정 전역 경로, 미설치여도 미리 배치) ---
echo [3/5] Cline 룰 배치
echo       위치: %CLINE_RULES%
if not exist "%CLINE_RULES%" mkdir "%CLINE_RULES%"
copy /Y "%TOOL_DIR%\zz-anr-rule.md" "%CLINE_RULES%\zz-anr-rule.md" >nul
if !errorlevel! neq 0 (
    echo       실패. Documents 폴더에 쓰기 권한이 있는지 확인하세요.
    pause
    exit /b 1
)
echo       OK
echo.

REM --- 4. Claude Code: CLAUDE.md 에 import 한 줄 멱등 추가 ---
echo [4/5] Claude Code 룰 연결
echo       위치: %CLAUDE_MD%
if not exist "%CLAUDE_DIR%" mkdir "%CLAUDE_DIR%"
findstr /C:"anr-tool/zz-anr-rule.md" "%CLAUDE_MD%" >nul 2>&1
if !errorlevel!==0 (
    echo       이미 등록됨 -- 건너뜀
) else (
    >> "%CLAUDE_MD%" echo.
    >> "%CLAUDE_MD%" echo @~/.anr-tool/zz-anr-rule.md
    echo       OK ^(CLAUDE.md 에 import 추가 -- 기존 내용은 보존^)
)
echo.

REM --- 5. Cursor 안내 (전역 룰 파일 없음) -------------------
echo [5/5] Cursor 안내
echo       Cursor 는 전역 룰 파일이 없어 자동 배치가 안 됩니다. 둘 중 하나:
echo       ^(A^) 전역: Cursor 설정 - Rules - User Rules 에 아래 파일 내용을 붙여넣기 ^(1회^)
echo           %TOOL_DIR%\zz-anr-rule.md
echo       ^(B^) 프로젝트별: 분석할 프로젝트에서 .cursor\rules 폴더를 만들고
echo           %CURSOR_MDC% 를 그 안에 복사
echo.

REM --- 임시 파일 정리 (직접 실행 시만) ------------------
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
echo   파서  : anr_parse.py      v%PARSER_VER%
echo   룰    : zz-anr-rule.md    v%RULE_VER%
echo.
echo 사용 방법 ^(공통^):
echo   AI 어시스턴트 채팅에 덤프 경로 + "anr" 를 입력 후 Enter:
echo      예^) C:\path\to\dumpstate.txt anr
echo      예^) "C:\My Logs\dump.txt" anr
echo.
echo   - Cline      : VSCode 재시작 후 Cline 채팅에 입력
echo   - Claude Code: 새 세션에서 바로 입력 ^(CLAUDE.md 자동 로드^)
echo   - Cursor     : 위 [5/5] 안내대로 룰 등록 후 채팅^(Ctrl/Cmd+L^)에 입력
echo.
echo 설치된 위치:
echo   파서/룰 정본 : %TOOL_DIR%\
echo   Cline 룰     : %CLINE_RULES%\zz-anr-rule.md
echo   Claude Code  : %CLAUDE_MD%  ^(import 한 줄^)
echo   Cursor mdc   : %CURSOR_MDC%
echo.
echo 제거하려면: %TOOL_DIR%\uninstall.bat 실행
echo.
pause
endlocal
