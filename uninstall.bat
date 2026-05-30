@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ANR 분석 도구 제거
echo.

set "TOOL_DIR=%USERPROFILE%\.anr-tool"
set "CLINE_RULES=%USERPROFILE%\Documents\Cline\Rules"
set "CLAUDE_MD=%USERPROFILE%\.claude\CLAUDE.md"

REM 1. Cline 룰 복사본
if exist "%CLINE_RULES%\zz-anr-rule.md" del /Q "%CLINE_RULES%\zz-anr-rule.md"

REM 2. Claude Code import 한 줄만 제거 (CLAUDE.md 의 나머지는 보존)
if exist "%CLAUDE_MD%" (
    findstr /V /C:"anr-tool/zz-anr-rule.md" "%CLAUDE_MD%" > "%CLAUDE_MD%.tmp"
    move /Y "%CLAUDE_MD%.tmp" "%CLAUDE_MD%" >nul
)

REM 3. 공용 도구 폴더 (파서 + 룰 정본 + Cursor mdc)
if exist "%TOOL_DIR%\anr_parse.py"     del /Q "%TOOL_DIR%\anr_parse.py"
if exist "%TOOL_DIR%\zz-anr-rule.md"   del /Q "%TOOL_DIR%\zz-anr-rule.md"
if exist "%TOOL_DIR%\anr-analysis.mdc" del /Q "%TOOL_DIR%\anr-analysis.mdc"

REM 자기 자신(파일)을 마지막에 삭제 후 폴더 제거
del /Q "%~f0" >nul 2>&1
rd "%TOOL_DIR%" >nul 2>&1

echo 제거 완료.
echo (Cursor 프로젝트에 .cursor\rules\anr-analysis.mdc 를 복사했다면 수동으로 지워주세요.)
pause
