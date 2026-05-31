#!/bin/bash
# ANR 분석 도구 제거 (Linux / macOS / WSL)
# 신버전(슬래시 커맨드/워크플로우/스킬) + 구버전(글로벌 룰) 모두 정리

TOOL_DIR="$HOME/.anr-tool"
CLAUDE_CMD="$HOME/.claude/commands/anr.md"
CLINE_WORKFLOW="$HOME/Documents/Cline/Workflows/anr.md"
CURSOR_SKILL_DIR="$HOME/.cursor/skills/anr"

# 구버전
OLD_CLAUDE_MD="$HOME/.claude/CLAUDE.md"
OLD_CLAUDE_IMPORT="@~/.anr-tool/zz-anr-rule.md"
OLD_CLINE_RULE="$HOME/Documents/Cline/Rules/zz-anr-rule.md"
OLD_CLINE_SKILL="$HOME/.cline/skills/anr"

echo "ANR 분석 도구 제거"
echo ""

# 1. Claude Code 슬래시 커맨드
[ -f "$CLAUDE_CMD" ] && rm -f "$CLAUDE_CMD" && echo "  Claude Code /anr 커맨드 제거"

# 2. Cline 워크플로우
[ -f "$CLINE_WORKFLOW" ] && rm -f "$CLINE_WORKFLOW" && echo "  Cline /anr 워크플로우 제거"

# 3. Cursor 스킬
if [ -d "$CURSOR_SKILL_DIR" ]; then
    rm -rf "$CURSOR_SKILL_DIR"
    echo "  Cursor /anr 스킬 제거"
fi

# 4. 구버전 — Cline 글로벌 룰 / 스킬 폴더
[ -f "$OLD_CLINE_RULE" ] && rm -f "$OLD_CLINE_RULE" && echo "  옛 Cline 글로벌 룰 제거"
[ -d "$OLD_CLINE_SKILL" ] && rm -rf "$OLD_CLINE_SKILL" && echo "  옛 Cline 스킬 폴더 제거"

# 5. 구버전 — Claude Code import 한 줄
if [ -f "$OLD_CLAUDE_MD" ] && grep -qF "$OLD_CLAUDE_IMPORT" "$OLD_CLAUDE_MD"; then
    grep -vF "$OLD_CLAUDE_IMPORT" "$OLD_CLAUDE_MD" > "$OLD_CLAUDE_MD.tmp" && mv "$OLD_CLAUDE_MD.tmp" "$OLD_CLAUDE_MD"
    echo "  옛 Claude Code import 제거 (CLAUDE.md 의 나머지는 유지)"
fi

# 6. 구버전 — Cursor state.vscdb 마커 블록
PYTHON=""
command -v python3 &>/dev/null && PYTHON="python3"
[ -z "$PYTHON" ] && command -v python &>/dev/null && PYTHON="python"
if [ -n "$PYTHON" ]; then
    $PYTHON - <<'PYEOF'
import os, sys, sqlite3, re

home = os.path.expanduser('~')
db_candidates = [
    os.path.join(home, '.config', 'Cursor', 'User', 'globalStorage', 'state.vscdb'),
    os.path.join(home, 'Library', 'Application Support', 'Cursor', 'User', 'globalStorage', 'state.vscdb'),
]
db_path = next((c for c in db_candidates if os.path.isfile(c)), None)
if db_path is None:
    sys.exit(0)

START = '<!-- ANR-TOOL-START -->'
END   = '<!-- ANR-TOOL-END -->'
try:
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute("SELECT value FROM ItemTable WHERE key='aicontext.personalContext'")
    row = cur.fetchone()
    if not row:
        conn.close()
        sys.exit(0)
    pattern = re.compile(re.escape(START) + '.*?' + re.escape(END), re.DOTALL)
    if pattern.search(row[0]):
        new_content = pattern.sub('', row[0]).strip()
        cur.execute("UPDATE ItemTable SET value=? WHERE key='aicontext.personalContext'", (new_content,))
        conn.commit()
        print('  옛 Cursor 전역 룰 블록 제거 (state.vscdb)')
    conn.close()
except Exception:
    pass
PYEOF
fi

# 7. 공용 도구 폴더
[ -f "$TOOL_DIR/anr_parse.py" ]    && rm -f "$TOOL_DIR/anr_parse.py"    && echo "  파서 제거"
[ -f "$TOOL_DIR/zz-anr-rule.md" ]  && rm -f "$TOOL_DIR/zz-anr-rule.md"
[ -f "$TOOL_DIR/anr-rule.md" ]     && rm -f "$TOOL_DIR/anr-rule.md"
[ -f "$TOOL_DIR/uninstall.sh" ]    && rm -f "$TOOL_DIR/uninstall.sh"
[ -d "$TOOL_DIR" ]                 && rmdir "$TOOL_DIR" 2>/dev/null && echo "  도구 폴더 제거"

echo ""
echo "제거 완료."
