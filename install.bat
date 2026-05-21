@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM ============================================================
REM   ANR 분석 도구 설치 스크립트
REM   - 글로벌 룰을 Cline 룰 폴더에 복사
REM   - anr_parse.py 를 %USERPROFILE%\.anr-tool\ 에 복사
REM ============================================================

echo.
echo ============================================================
echo   ANR 분석 도구 설치
echo ============================================================
echo.

REM --- 0. Python 확인 ----------------------------------------
echo [0/3] Python 확인 중...
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

REM --- 1. 대상 폴더 경로 -------------------------------------
set "RULES_DIR=%USERPROFILE%\Documents\Cline\Rules"
set "TOOL_DIR=%USERPROFILE%\.anr-tool"

REM --- 2. 폴더 생성 ------------------------------------------
echo [1/3] 설치 폴더 준비
echo       Rules: %RULES_DIR%
echo       Tool : %TOOL_DIR%
if not exist "%RULES_DIR%" mkdir "%RULES_DIR%"
if not exist "%TOOL_DIR%"  mkdir "%TOOL_DIR%"
echo.

REM --- 3. payload 파일 위치 확인 -----------------------------
set "PAYLOAD=%~dp0payload"
if not exist "%PAYLOAD%\zz-anr-rule.md" (
    echo [오류] payload 폴더에서 룰 파일을 찾을 수 없습니다.
    echo        경로: %PAYLOAD%
    echo        설치 패키지가 손상되었거나 압축 해제가 잘못된 것 같습니다.
    pause
    exit /b 1
)

REM --- 4. 파일 복사 ------------------------------------------
echo [2/3] 글로벌 룰 복사
copy /Y "%PAYLOAD%\zz-anr-rule.md" "%RULES_DIR%\zz-anr-rule.md" >nul
if !errorlevel! neq 0 (
    echo       실패. Documents 폴더에 쓰기 권한이 있는지 확인하세요.
    pause
    exit /b 1
)
echo       OK
echo.

echo [3/3] 파서 스크립트 복사
copy /Y "%PAYLOAD%\anr_parse.py" "%TOOL_DIR%\anr_parse.py" >nul
if !errorlevel! neq 0 (
    echo       실패.
    pause
    exit /b 1
)
echo       OK
echo.

REM --- 5. 완료 메시지 ----------------------------------------
echo ============================================================
echo   설치 완료
echo ============================================================
echo.
echo 사용 방법:
echo   1. VSCode 를 실행 ^(또는 재시작^)
echo   2. Cline 채팅창에 ANR 덤프 파일 경로를 알려주세요:
echo      예^) "C:\path\to\dump.txt 분석해줘"
echo      예^) "이 ANR 덤프 좀 봐줘: C:\dump.txt"
echo.
echo 설치된 위치:
echo   글로벌 룰    : %RULES_DIR%\zz-anr-rule.md
echo   파서 스크립트: %TOOL_DIR%\anr_parse.py
echo.
echo 제거하려면 같은 폴더의 uninstall.bat 을 실행하세요.
echo.
pause
endlocal
