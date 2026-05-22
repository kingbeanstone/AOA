#!/bin/bash
# ANR 분석 도구 설치 (Linux / macOS / WSL)
# GitHub에서 최신 파일 자동 다운로드 (실패 시 로컬 payload/ 폴백)

PARSER_VER="1.2"
RULE_VER="1.1"

REPO="kingbeanstone/aoa2"
BRANCH="claude/anr-analysis-tool-rz6Rv"
DL_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip"
TMP_ZIP="/tmp/anr-tool-latest.zip"
TMP_DIR="/tmp/anr-tool-latest"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RULES_DIR="$HOME/Documents/Cline/Rules"
TOOL_DIR="$HOME/.anr-tool"

if [ -z "$ANR_SKIP_DOWNLOAD" ]; then
    echo ""
    echo "============================================================"
    echo "  ANR 분석 도구 설치"
    echo "============================================================"
    echo ""
fi

# 0. GitHub 최신 버전 다운로드
echo "[0/4] GitHub에서 최신 버전 다운로드 중..."
if [ -n "$ANR_SKIP_DOWNLOAD" ]; then
    echo "      OK: 최신 버전 준비 완료"
    PAYLOAD_SRC="$SCRIPT_DIR/payload"
else
    DOWNLOADED=0
    if curl -fsSL "$DL_URL" -o "$TMP_ZIP" 2>/dev/null; then
        DOWNLOADED=1
    elif wget -q "$DL_URL" -O "$TMP_ZIP" 2>/dev/null; then
        DOWNLOADED=1
    fi

    if [ "$DOWNLOADED" -eq 1 ]; then
        rm -rf "$TMP_DIR"
        mkdir -p "$TMP_DIR"
        unzip -oq "$TMP_ZIP" -d "$TMP_DIR" 2>/dev/null
        PAYLOAD_SRC=$(ls -d "$TMP_DIR"/aoa2-*/payload 2>/dev/null | head -1)
        if [ -n "$PAYLOAD_SRC" ]; then
            echo "      OK: GitHub 최신 버전 다운로드 완료"
        else
            echo "      추출 실패 — 로컬 파일로 설치합니다."
            PAYLOAD_SRC="$SCRIPT_DIR/payload"
        fi
    else
        echo "      GitHub 연결 실패 — 로컬 파일로 설치합니다."
        PAYLOAD_SRC="$SCRIPT_DIR/payload"
    fi
fi
echo ""

# 1. Python 확인
echo "[1/4] Python 확인 중..."
if command -v python3 &>/dev/null; then
    echo "      OK: python3 사용 가능"
elif command -v python &>/dev/null; then
    echo "      OK: python 사용 가능"
else
    echo "      경고: Python이 설치되지 않은 것 같습니다."
    echo "            sudo apt install python3  또는  brew install python3"
    echo "            설치 후 다시 실행하세요. (설치 자체는 계속 진행됩니다)"
fi
echo ""

# 2. 폴더 생성
echo "[2/4] 설치 폴더 준비"
echo "      Rules: $RULES_DIR"
echo "      Tool : $TOOL_DIR"
mkdir -p "$RULES_DIR"
mkdir -p "$TOOL_DIR"
echo ""

# payload 파일 위치 확인
if [ ! -f "$PAYLOAD_SRC/zz-anr-rule.md" ]; then
    echo "[오류] payload 폴더에서 룰 파일을 찾을 수 없습니다."
    echo "       경로: $PAYLOAD_SRC"
    echo "       GitHub 연결에 실패한 경우 payload/ 폴더가 install.sh와 같은 위치에 있는지 확인하세요."
    if [ -z "$ANR_SKIP_DOWNLOAD" ]; then
        rm -f "$TMP_ZIP" 2>/dev/null
        rm -rf "$TMP_DIR" 2>/dev/null
    fi
    exit 1
fi

# 3. 파일 복사
echo "[3/4] 글로벌 룰 복사  (v${RULE_VER})"
cp "$PAYLOAD_SRC/zz-anr-rule.md" "$RULES_DIR/zz-anr-rule.md"
echo "      OK"
echo ""

echo "[4/4] 파서 스크립트 복사  (v${PARSER_VER})"
cp "$PAYLOAD_SRC/anr_parse.py" "$TOOL_DIR/anr_parse.py"
chmod +x "$TOOL_DIR/anr_parse.py"
echo "      OK"
echo ""

# 임시 파일 정리 (직접 실행 시만)
if [ -z "$ANR_SKIP_DOWNLOAD" ]; then
    rm -f "$TMP_ZIP" 2>/dev/null
    rm -rf "$TMP_DIR" 2>/dev/null
fi

# 완료 메시지
echo "============================================================"
echo "  설치 완료"
echo "============================================================"
echo ""
echo "설치된 버전:"
echo "  파서  : anr_parse.py      v${PARSER_VER}"
echo "  룰    : zz-anr-rule.md    v${RULE_VER}"
echo ""
echo "사용 방법:"
echo "  1. VSCode 를 실행 (또는 재시작)"
echo "  2. Cline 채팅창에 경로 + \"anr\" 입력 후 Enter:"
echo "     예) /path/to/dumpstate.txt anr"
echo "     예) ~/Downloads/bugreport.txt anr"
echo ""
echo "설치된 위치:"
echo "  글로벌 룰    : $RULES_DIR/zz-anr-rule.md"
echo "  파서 스크립트: $TOOL_DIR/anr_parse.py"
echo ""
echo "제거하려면 같은 폴더의 uninstall.sh 를 실행하세요."
echo ""
