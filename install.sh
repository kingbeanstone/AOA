#!/bin/bash
# ANR 분석 도구 설치 (Linux / macOS / WSL)
# Cline / Cursor / Claude Code 공용.
#   - 파서(anr_parse.py)    → ~/.anr-tool/ (공용)
#   - Cline 룰              → ~/Documents/Cline/Rules/ (파일 복사, 미설치여도 미리 배치)
#   - Claude Code 룰        → ~/.claude/CLAUDE.md 에 import 한 줄 (미설치여도 미리 배치)
#   - Cursor 전역 룰        → Cursor state.vscdb SQLite DB 에 직접 기록
#                             (Python 내장 sqlite3 사용 — 추가 의존성 없음)
#                             Cursor 미설치면 건너뛰고 나중에 재실행 시 자동 등록
# GitHub에서 최신 파일 자동 다운로드 (실패 시 로컬 payload/ 폴백)

REPO="kingbeanstone/AOA"
BRANCH="main"
DL_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip"
TMP_ZIP="/tmp/anr-tool-latest.zip"
TMP_DIR="/tmp/anr-tool-latest"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

TOOL_DIR="$HOME/.anr-tool"
CLINE_RULES="$HOME/Documents/Cline/Rules"
CLAUDE_DIR="$HOME/.claude"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
CLAUDE_IMPORT="@~/.anr-tool/zz-anr-rule.md"

SKIP_DL=0
[ "$1" = "skip" ] && SKIP_DL=1

if [ "$SKIP_DL" -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "  ANR 분석 도구 설치 (Cline / Cursor / Claude Code)"
    echo "============================================================"
    echo ""
fi

# 0. GitHub 최신 버전 다운로드
echo "[0/5] GitHub에서 최신 버전 다운로드 중..."
if [ "$SKIP_DL" -eq 1 ]; then
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
        PAYLOAD_SRC=$(ls -d "$TMP_DIR"/AOA-*/payload 2>/dev/null | head -1)
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
echo "[1/5] Python 확인 중..."
PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON="python3"
    echo "      OK: python3 사용 가능"
elif command -v python &>/dev/null; then
    PYTHON="python"
    echo "      OK: python 사용 가능"
else
    echo "      경고: Python이 설치되지 않은 것 같습니다."
    echo "            sudo apt install python3  또는  brew install python3"
    echo "            설치 후 다시 실행하세요. (설치 자체는 계속 진행됩니다)"
fi
echo ""

# payload 파일 위치 확인
if [ ! -f "$PAYLOAD_SRC/zz-anr-rule.md" ]; then
    echo "[오류] payload 폴더에서 룰 파일을 찾을 수 없습니다."
    echo "       경로: $PAYLOAD_SRC"
    if [ "$SKIP_DL" -eq 0 ]; then
        rm -f "$TMP_ZIP" 2>/dev/null
        rm -rf "$TMP_DIR" 2>/dev/null
    fi
    exit 1
fi

# payload 파일에서 버전 추출 (하드코딩 방지)
PARSER_VER=$(grep -m1 '^__version__' "$PAYLOAD_SRC/anr_parse.py" 2>/dev/null | sed -E 's/.*"([^"]+)".*/\1/')
RULE_VER=$(grep -m1 '^<!-- 버전:' "$PAYLOAD_SRC/zz-anr-rule.md" 2>/dev/null | sed -E 's/.*버전:[[:space:]]*([^ ]+)[[:space:]]*-->.*/\1/')
[ -z "$PARSER_VER" ] && PARSER_VER="?"
[ -z "$RULE_VER" ] && RULE_VER="?"

# 2. 공용 파일 배치 (파서 + 룰 정본)
echo "[2/5] 공용 파일 배치  (파서 v${PARSER_VER} / 룰 v${RULE_VER})"
echo "      위치: $TOOL_DIR"
mkdir -p "$TOOL_DIR"
cp "$PAYLOAD_SRC/anr_parse.py" "$TOOL_DIR/anr_parse.py"
chmod +x "$TOOL_DIR/anr_parse.py"
cp "$PAYLOAD_SRC/zz-anr-rule.md" "$TOOL_DIR/zz-anr-rule.md"
UNINSTALL_SRC="$(dirname "$PAYLOAD_SRC")/uninstall.sh"
if [ -f "$UNINSTALL_SRC" ]; then
    cp "$UNINSTALL_SRC" "$TOOL_DIR/uninstall.sh"
    chmod +x "$TOOL_DIR/uninstall.sh"
fi
echo "      OK"
echo ""

# 3. Cline — 글로벌 룰 폴더에 복사 (툴 미설치여도 미리 배치)
echo "[3/5] Cline 룰 배치"
echo "      위치: $CLINE_RULES"
mkdir -p "$CLINE_RULES"
cp "$TOOL_DIR/zz-anr-rule.md" "$CLINE_RULES/zz-anr-rule.md"
echo "      OK"
echo ""

# 4. Claude Code — ~/.claude/CLAUDE.md 에 import 한 줄 멱등 추가
echo "[4/5] Claude Code 룰 연결"
echo "      위치: $CLAUDE_MD"
mkdir -p "$CLAUDE_DIR"
if [ -f "$CLAUDE_MD" ] && grep -qF "$CLAUDE_IMPORT" "$CLAUDE_MD"; then
    echo "      이미 등록됨 — 건너뜀"
else
    printf '\n%s\n' "$CLAUDE_IMPORT" >> "$CLAUDE_MD"
    echo "      OK (CLAUDE.md 에 import 추가 — 기존 내용은 보존)"
fi
echo ""

# 5. Cursor — state.vscdb 에 전역 룰 직접 기록 (Python 내장 sqlite3)
#    Cursor User Rules 는 Settings → Rules → User Rules 와 동일한 위치에 저장된다.
#    DB 키: aicontext.personalContext
#    ANR 룰은 <!-- ANR-TOOL-START/END --> 마커로 감싸 멱등 삽입/갱신한다.
echo "[5/5] Cursor 전역 룰 등록"
if [ -z "$PYTHON" ]; then
    echo "      건너뜀: Python 없음 (Python 설치 후 재실행하면 자동 등록)"
else
    $PYTHON - "$TOOL_DIR/zz-anr-rule.md" <<'PYEOF'
import sys, os, sqlite3

rule_path = sys.argv[1]
with open(rule_path, 'r', encoding='utf-8') as f:
    rule_content = f.read()

home = os.path.expanduser('~')
db_candidates = [
    os.path.join(home, '.config', 'Cursor', 'User', 'globalStorage', 'state.vscdb'),
    os.path.join(home, 'Library', 'Application Support', 'Cursor', 'User', 'globalStorage', 'state.vscdb'),
]

db_path = next((c for c in db_candidates if os.path.isfile(c)), None)
if db_path is None:
    print('      Cursor 미설치 — 나중에 설치 후 anr-install 을 재실행하면 자동 등록됩니다.')
    sys.exit(0)

START = '<!-- ANR-TOOL-START -->'
END   = '<!-- ANR-TOOL-END -->'
block = f'{START}\n{rule_content}\n{END}'

conn = sqlite3.connect(db_path)
cur  = conn.cursor()
cur.execute("SELECT value FROM ItemTable WHERE key='aicontext.personalContext'")
row = cur.fetchone()
existing = row[0] if row else ''

import re
pattern = re.compile(re.escape(START) + '.*?' + re.escape(END), re.DOTALL)

if pattern.search(existing):
    # 이미 있으면 최신 룰로 교체 (업데이트)
    new_content = pattern.sub(block, existing)
    action = '업데이트'
else:
    # 없으면 기존 내용 뒤에 추가
    new_content = (existing.rstrip() + '\n\n' + block).lstrip() if existing.strip() else block
    action = '추가'

cur.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES ('aicontext.personalContext', ?)", (new_content,))
conn.commit()
conn.close()
print(f'      OK ({action} 완료 — Cursor 재시작 후 Settings→Rules→User Rules 에서 확인 가능)')
PYEOF
fi
echo ""

# 임시 파일 정리 (직접 실행 시만)
if [ "$SKIP_DL" -eq 0 ]; then
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
echo "사용 방법 (공통):"
echo "  AI 어시스턴트 채팅에 덤프 경로 + \"anr\" 를 입력하고 Enter:"
echo "     예) /path/to/dumpstate.txt anr"
echo "     예) ~/Downloads/bugreport.txt anr"
echo ""
echo "  - Cline      : VSCode 재시작 후 Cline 채팅에 입력"
echo "  - Claude Code: 새 세션에서 바로 입력 (CLAUDE.md 자동 로드)"
echo "  - Cursor     : Cursor 재시작 후 채팅(Ctrl/Cmd+L)에 입력"
echo ""
echo "설치된 위치:"
echo "  파서/룰 정본 : $TOOL_DIR/"
echo "  Cline 룰     : $CLINE_RULES/zz-anr-rule.md"
echo "  Claude Code  : $CLAUDE_MD  (import 한 줄)"
echo "  Cursor 룰    : Cursor User Rules (state.vscdb)"
echo ""
echo "제거하려면: bash $TOOL_DIR/uninstall.sh"
echo ""
