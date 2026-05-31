#!/bin/bash
# ANR 분석 도구 설치 (Linux / macOS / WSL)
# Cline / Cursor / Claude Code 공용 — 슬래시 커맨드 / 스킬 방식.
#   - 파서(anr_parse.py)    → ~/.anr-tool/ (공용)
#   - Claude Code 슬래시    → ~/.claude/commands/anr.md
#   - Cline 스킬            → ~/.cline/skills/anr/SKILL.md
#   - Cursor 스킬           → ~/.cursor/skills/anr/SKILL.md
# 글로벌 룰 주입 방식이 아니라 사용자가 명시적으로 /anr 호출할 때만 동작.
# GitHub에서 최신 파일 자동 다운로드 (실패 시 로컬 payload/ 폴백)

REPO="kingbeanstone/AOA"
BRANCH="main"
DL_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip"
TMP_ZIP="/tmp/anr-tool-latest.zip"
TMP_DIR="/tmp/anr-tool-latest"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

TOOL_DIR="$HOME/.anr-tool"
CLAUDE_CMDS="$HOME/.claude/commands"
CLINE_SKILL_DIR="$HOME/.cline/skills/anr"
CURSOR_SKILL_DIR="$HOME/.cursor/skills/anr"

# 구버전(글로벌 룰 / 워크플로우) 정리 대상
OLD_CLAUDE_MD="$HOME/.claude/CLAUDE.md"
OLD_CLAUDE_IMPORT="@~/.anr-tool/zz-anr-rule.md"
OLD_CLINE_RULE="$HOME/Documents/Cline/Rules/zz-anr-rule.md"
OLD_CLINE_WORKFLOW="$HOME/Documents/Cline/Workflows/anr.md"
OLD_TOOL_RULE="$HOME/.anr-tool/zz-anr-rule.md"

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
echo "[0/6] GitHub에서 최신 버전 다운로드 중..."
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

# 1. Python 확인 (파서 실행용)
echo "[1/6] Python 확인 중..."
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
if [ ! -f "$PAYLOAD_SRC/anr-rule.md" ] || [ ! -f "$PAYLOAD_SRC/anr_parse.py" ]; then
    echo "[오류] payload 폴더에서 필수 파일을 찾을 수 없습니다."
    echo "       경로: $PAYLOAD_SRC"
    [ "$SKIP_DL" -eq 0 ] && rm -f "$TMP_ZIP" 2>/dev/null && rm -rf "$TMP_DIR" 2>/dev/null
    exit 1
fi

# payload 파일에서 버전 추출
PARSER_VER=$(grep -m1 '^__version__' "$PAYLOAD_SRC/anr_parse.py" 2>/dev/null | sed -E 's/.*"([^"]+)".*/\1/')
RULE_VER=$(grep -m1 '^<!-- 버전:' "$PAYLOAD_SRC/anr-rule.md" 2>/dev/null | sed -E 's/.*버전:[[:space:]]*([^ ]+)[[:space:]]*-->.*/\1/')
[ -z "$PARSER_VER" ] && PARSER_VER="?"
[ -z "$RULE_VER" ] && RULE_VER="?"

# 2. 구버전(글로벌 룰) 정리 — 신·구 동시 트리거 방지
echo "[2/6] 구버전(글로벌 룰) 정리"
CLEANED=0
if [ -f "$OLD_CLINE_RULE" ]; then
    rm -f "$OLD_CLINE_RULE"
    echo "      - 옛 Cline 글로벌 룰 제거: $OLD_CLINE_RULE"
    CLEANED=1
fi
if [ -f "$OLD_CLINE_WORKFLOW" ]; then
    rm -f "$OLD_CLINE_WORKFLOW"
    echo "      - 옛 Cline 워크플로우 제거: $OLD_CLINE_WORKFLOW"
    CLEANED=1
fi
if [ -f "$OLD_CLAUDE_MD" ] && grep -qF "$OLD_CLAUDE_IMPORT" "$OLD_CLAUDE_MD"; then
    grep -vF "$OLD_CLAUDE_IMPORT" "$OLD_CLAUDE_MD" > "$OLD_CLAUDE_MD.tmp" && mv "$OLD_CLAUDE_MD.tmp" "$OLD_CLAUDE_MD"
    echo "      - 옛 Claude Code import 제거: CLAUDE.md (나머지 보존)"
    CLEANED=1
fi
if [ -f "$OLD_TOOL_RULE" ]; then
    rm -f "$OLD_TOOL_RULE"
    echo "      - 옛 룰 정본 제거: $OLD_TOOL_RULE"
    CLEANED=1
fi
# 옛 Cursor state.vscdb 마커 블록 제거 (Python 있을 때만)
if [ -n "$PYTHON" ]; then
    if $PYTHON - <<'PYEOF'
import os, sys, sqlite3, re

home = os.path.expanduser('~')
db_candidates = [
    os.path.join(home, '.config', 'Cursor', 'User', 'globalStorage', 'state.vscdb'),
    os.path.join(home, 'Library', 'Application Support', 'Cursor', 'User', 'globalStorage', 'state.vscdb'),
]
db_path = next((c for c in db_candidates if os.path.isfile(c)), None)
if db_path is None:
    sys.exit(1)

START = '<!-- ANR-TOOL-START -->'
END   = '<!-- ANR-TOOL-END -->'
try:
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute("SELECT value FROM ItemTable WHERE key='aicontext.personalContext'")
    row = cur.fetchone()
    if not row:
        conn.close(); sys.exit(1)
    pattern = re.compile(re.escape(START) + '.*?' + re.escape(END), re.DOTALL)
    if pattern.search(row[0]):
        new_content = pattern.sub('', row[0]).strip()
        cur.execute("UPDATE ItemTable SET value=? WHERE key='aicontext.personalContext'", (new_content,))
        conn.commit()
        conn.close()
        sys.exit(0)
    conn.close()
    sys.exit(1)
except Exception:
    sys.exit(1)
PYEOF
    then
        echo "      - 옛 Cursor 전역 룰 블록 제거 (state.vscdb)"
        CLEANED=1
    fi
fi
[ "$CLEANED" -eq 0 ] && echo "      OK: 정리할 구버전 없음"
echo ""

# 3. 공용 파서 배치
echo "[3/6] 파서 배치  (anr_parse.py v${PARSER_VER})"
echo "      위치: $TOOL_DIR/anr_parse.py"
mkdir -p "$TOOL_DIR"
cp "$PAYLOAD_SRC/anr_parse.py" "$TOOL_DIR/anr_parse.py"
chmod +x "$TOOL_DIR/anr_parse.py"
UNINSTALL_SRC="$(dirname "$PAYLOAD_SRC")/uninstall.sh"
if [ -f "$UNINSTALL_SRC" ]; then
    cp "$UNINSTALL_SRC" "$TOOL_DIR/uninstall.sh"
    chmod +x "$TOOL_DIR/uninstall.sh"
fi
echo "      OK"
echo ""

# 4. Claude Code — ~/.claude/commands/anr.md 배치 (슬래시 커맨드)
echo "[4/6] Claude Code /anr 슬래시 커맨드 배치  (룰 v${RULE_VER})"
echo "      위치: $CLAUDE_CMDS/anr.md"
mkdir -p "$CLAUDE_CMDS"
cp "$PAYLOAD_SRC/anr-rule.md" "$CLAUDE_CMDS/anr.md"
echo "      OK"
echo ""

# 5. Cline — ~/.cline/skills/anr/SKILL.md 배치 (스킬)
echo "[5/6] Cline /anr 스킬 배치  (룰 v${RULE_VER})"
echo "      위치: $CLINE_SKILL_DIR/SKILL.md"
mkdir -p "$CLINE_SKILL_DIR"
cp "$PAYLOAD_SRC/anr-rule.md" "$CLINE_SKILL_DIR/SKILL.md"
echo "      OK"
echo ""

# 6. Cursor — ~/.cursor/skills/anr/SKILL.md 배치 (스킬)
echo "[6/6] Cursor /anr 스킬 배치  (룰 v${RULE_VER})"
echo "      위치: $CURSOR_SKILL_DIR/SKILL.md"
mkdir -p "$CURSOR_SKILL_DIR"
cp "$PAYLOAD_SRC/anr-rule.md" "$CURSOR_SKILL_DIR/SKILL.md"
echo "      OK"
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
echo "  파서  : anr_parse.py    v${PARSER_VER}"
echo "  룰    : anr-rule.md     v${RULE_VER}"
echo ""
echo "사용 방법 (공통 — 모든 툴에서 동일):"
echo "  AI 어시스턴트 채팅에서 슬래시 커맨드로 호출:"
echo "     /anr /path/to/dumpstate.txt"
echo "     /anr ~/Downloads/bugreport.txt"
echo ""
echo "  - Claude Code: 새 세션부터 즉시 사용 가능"
echo "  - Cline      : VSCode 재시작 후 사용"
echo "  - Cursor     : Cursor 재시작 후 사용"
echo ""
echo "설치된 위치:"
echo "  파서        : $TOOL_DIR/anr_parse.py"
echo "  Claude Code : $CLAUDE_CMDS/anr.md"
echo "  Cline       : $CLINE_SKILL_DIR/SKILL.md"
echo "  Cursor      : $CURSOR_SKILL_DIR/SKILL.md"
echo ""
echo "제거하려면: bash $TOOL_DIR/uninstall.sh"
echo ""
