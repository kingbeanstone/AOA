@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   ANR 분석 도구 설치 준비 중...
echo ============================================================
echo.

set "REPO=kingbeanstone/aoa2"
set "BRANCH=claude/anr-analysis-tool-rz6Rv"
set "DL_URL=https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip"
set "TMP_ZIP=%TEMP%\anr-tool-latest.zip"
set "TMP_DIR=%TEMP%\anr-tool-latest"

echo GitHub에서 최신 버전 다운로드 중... (잠시 기다려주세요)
set "DL_OK=0"
curl.exe -fsSL "%DL_URL%" -o "%TMP_ZIP%" >nul 2>&1
if !errorlevel!==0 set "DL_OK=1"
if !DL_OK!==0 (
    powershell -Command "Invoke-WebRequest -Uri '%DL_URL%' -OutFile '%TMP_ZIP%'" >nul 2>&1
    if !errorlevel!==0 set "DL_OK=1"
)
if !DL_OK!==0 (
    echo.
    echo [오류] GitHub 연결에 실패했습니다.
    echo        네트워크 상태를 확인하거나 관리자에게 문의하세요.
    echo.
    pause
    exit /b 1
)

echo 파일 준비 중...
if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>&1
powershell -Command "Expand-Archive -Path '%TMP_ZIP%' -DestinationPath '%TMP_DIR%' -Force" >nul 2>&1
del /q "%TMP_ZIP%" >nul 2>&1

set "EXTRACTED="
for /D %%i in ("%TMP_DIR%\aoa2-*") do set "EXTRACTED=%%i"
if not defined EXTRACTED (
    echo.
    echo [오류] 파일 준비에 실패했습니다. 관리자에게 문의하세요.
    echo.
    pause
    exit /b 1
)

echo.
call "!EXTRACTED!\install.bat" skip

if exist "%TMP_DIR%" rd /s /q "%TMP_DIR%" >nul 2>&1
endlocal
pause
