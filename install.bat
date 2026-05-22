@echo off
if not defined ANR_SKIP_DOWNLOAD chcp 65001 > nul
setlocal enabledelayedexpansion

REM ============================================================
REM   ANR 분석 도구 설치 스크립트 (Windows)
REM   - GitHub에서 최신 파일 자동 다운로드 (실패 시 로컬 payload\ 폴백)
REM   - 글로벌 룰을 Cline 룰 폴더에 복사
REM   - anr_parse.py 를 %USERPROFILE%\.anr-tool\ 에 복사
REM ============================================================

if not defined ANR_SKIP_DOWNLOAD (
    echo.
    echo ============================================================
    echo   ANR 분석 도구 설치
    echo ============================================================
    echo.
)

REM --- 설정 --------------------------------------------------
set "REPO=kingbeanstone/aoa2"
set "BRANCH=claude/anr-analysis-tool-rz6Rv"
set "DL_URL=https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip"
set "TMP_ZIP=%TEMP%\anr-tool-latest.zip"
set "TMP_DIR=%TEMP%\anr-tool-latest"
set "PARSER_VER=1.2"
set "RULE_VER=1.1"
set "RULES_DIR=%USERPROFILE%\Documents\Cline\Rules"
set "TOOL_DIR=%USERPROFILE%\.anr-tool"

REM --- 0. GitHub 최신 버전 다운로드 -------------------------
echo [0/4] GitHub에서 최신 버전 다운로드 중...
if defined ANR_SKIP_DOWNLOAD (
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
    powershell -Command "Invoke-WebRequest -Uri '%DL_URL%' -OutFile '%TMP_ZIP%'" >nul 2>&1
    if !errorlevel!==0 set "DL_OK=1"
)

if !DL_OK!==1 (
    powershell -Command "Expand-Archive -Path '%TMP_ZIP%' -DestinationPath '%TMP_DIR%' -Force" >nul 2>&1
    set "EXTRACTED="
    for /D %%i in ("%TMP_DIR%\aoa2-*") do set "EXTRACTED=%%i"
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
echo [1/4] Python 확인 중...
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

REM --- 2. 대상 폴더 생성 -------------------------------------
echo [2/4] 설치 폴더 준비
echo       Rules: %RULES_DIR%
echo       Tool : %TOOL_DIR%
if not exist "%RULES_DIR%" mkdir "%RULES_DIR%"
if not exist "%TOOL_DIR%"  mkdir "%TOOL_DIR%"
echo.

REM --- payload 파일 위치 확인 --------------------------------
if not exist "%PAYLOAD%\zz-anr-rule.md" (
    echo [오류] payload 폴더에서 룰 파일을 찾을 수 없습니다.
    echo        경로: %PAYLOAD%
    echo        GitHub 연결에 실패한 경우 payload\ 폴더가 install.bat과 같은 위치에 있는지 확인하세요.
    if not defined ANR_SKIP_DOWNLOAD (
        if exist "%TMP_ZIP%" del /q "%TMP_ZIP%" >nul 2>&1
        if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>&1
    )
    pause
    exit /b 1
)

REM --- 3. 파일 복사 ------------------------------------------
echo [3/4] 글로벌 룰 복사  ^(v%RULE_VER%^)
copy /Y "%PAYLOAD%\zz-anr-rule.md" "%RULES_DIR%\zz-anr-rule.md" >nul
if !errorlevel! neq 0 (
    echo       실패. Documents 폴더에 쓰기 권한이 있는지 확인하세요.
    pause
    exit /b 1
)
echo       OK
echo.

echo [4/4] 파서 스크립트 복사  ^(v%PARSER_VER%^)
copy /Y "%PAYLOAD%\anr_parse.py" "%TOOL_DIR%\anr_parse.py" >nul
if !errorlevel! neq 0 (
    echo       실패.
    pause
    exit /b 1
)
echo       OK
echo.

REM --- 임시 파일 정리 (직접 실행 시만) ------------------
if not defined ANR_SKIP_DOWNLOAD (
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
echo 사용 방법:
echo   1. VSCode 를 실행 ^(또는 재시작^)
echo   2. Cline 채팅창에 경로 + "anr" 입력 후 Enter:
echo      예^) C:\path\to\dumpstate.txt anr
echo      예^) "C:\My Logs\dump.txt" anr
echo.
echo 설치된 위치:
echo   글로벌 룰    : %RULES_DIR%\zz-anr-rule.md
echo   파서 스크립트: %TOOL_DIR%\anr_parse.py
echo.
echo 제거하려면 같은 폴더의 uninstall.bat 을 실행하세요.
echo.
pause
endlocal
