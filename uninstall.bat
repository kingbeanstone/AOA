@echo off
chcp 65001 > nul

echo ANR 분석 도구 제거
echo.

set "RULES_DIR=%USERPROFILE%\Documents\Cline\Rules"
set "TOOL_DIR=%USERPROFILE%\.anr-tool"

if exist "%RULES_DIR%\zz-anr-rule.md" del /Q "%RULES_DIR%\zz-anr-rule.md"
if exist "%TOOL_DIR%\anr_parse.py"    del /Q "%TOOL_DIR%\anr_parse.py"

REM 자기 자신(파일)을 마지막에 삭제 후 폴더 제거
del /Q "%~f0" >nul 2>&1
rd "%TOOL_DIR%" >nul 2>&1

echo 제거 완료.
pause
