@echo off
chcp 65001 > nul

echo ANR 분석 도구 제거
echo.

set "RULES_DIR=%USERPROFILE%\Documents\Cline\Rules"
set "TOOL_DIR=%USERPROFILE%\.anr-tool"

if exist "%RULES_DIR%\zz-anr-rule.md" del /Q "%RULES_DIR%\zz-anr-rule.md"
if exist "%TOOL_DIR%\anr_parse.py"    del /Q "%TOOL_DIR%\anr_parse.py"
if exist "%TOOL_DIR%"                 rmdir "%TOOL_DIR%" 2>nul

echo 제거 완료.
pause
