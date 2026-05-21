#!/bin/bash
# ANR 분석 도구 설치 (Linux / macOS / WSL)

PARSER_VER="1.1"
RULE_VER="1.1"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="$SCRIPT_DIR/payload"
RULES_DIR="$HOME/Documents/Cline/Rules"
TOOL_DIR="$HOME/.anr-tool"

echo ""
echo "============================================================"
echo "  ANR 분석 도구 설치"
echo "============================================================"
echo ""

# 0. Python 확인
echo "[0/3] Python 확인 중..."
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

# 1. 폴더 생성
echo "[1/3] 설치 폴더 준비"
echo "      Rules: $RULES_DIR"
echo "      Tool : $TOOL_DIR"
mkdir -p "$RULES_DIR"
mkdir -p "$TOOL_DIR"
echo ""

# 2. payload 파일 위치 확인
if [ ! -f "$PAYLOAD/zz-anr-rule.md" ]; then
    echo "[오류] payload 폴더에서 룰 파일을 찾을 수 없습니다."
    echo "       경로: $PAYLOAD"
    exit 1
fi

# 3. 파일 복사
echo "[2/3] 글로벌 룰 복사  (v${RULE_VER})"
cp "$PAYLOAD/zz-anr-rule.md" "$RULES_DIR/zz-anr-rule.md"
echo "      OK"
echo ""

echo "[3/3] 파서 스크립트 복사  (v${PARSER_VER})"
cp "$PAYLOAD/anr_parse.py" "$TOOL_DIR/anr_parse.py"
chmod +x "$TOOL_DIR/anr_parse.py"
echo "      OK"
echo ""

# 4. 완료 메시지
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
