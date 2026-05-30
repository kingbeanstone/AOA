#!/bin/bash
# ANR 분석 도구 제거 (Linux / macOS / WSL)
# Cline 룰 복사본, Claude Code import 한 줄, 공용 도구 폴더를 모두 정리한다.

TOOL_DIR="$HOME/.anr-tool"
CLINE_RULES="$HOME/Documents/Cline/Rules"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
CLAUDE_IMPORT="@~/.anr-tool/zz-anr-rule.md"

echo "ANR 분석 도구 제거"
echo ""

# 1. Cline 룰 복사본
[ -f "$CLINE_RULES/zz-anr-rule.md" ] && rm -f "$CLINE_RULES/zz-anr-rule.md" && echo "  Cline 룰 삭제 완료"

# 2. Claude Code import 한 줄만 제거 (CLAUDE.md 의 나머지 내용은 보존)
if [ -f "$CLAUDE_MD" ] && grep -qF "$CLAUDE_IMPORT" "$CLAUDE_MD"; then
    grep -vF "$CLAUDE_IMPORT" "$CLAUDE_MD" > "$CLAUDE_MD.tmp" && mv "$CLAUDE_MD.tmp" "$CLAUDE_MD"
    echo "  Claude Code import 제거 완료 (CLAUDE.md 의 나머지는 유지)"
fi

# 3. 공용 도구 폴더 (파서 + 룰 정본 + Cursor mdc)
[ -f "$TOOL_DIR/anr_parse.py" ]      && rm -f "$TOOL_DIR/anr_parse.py"      && echo "  파서 삭제 완료"
[ -f "$TOOL_DIR/zz-anr-rule.md" ]    && rm -f "$TOOL_DIR/zz-anr-rule.md"
[ -f "$TOOL_DIR/anr-analysis.mdc" ]  && rm -f "$TOOL_DIR/anr-analysis.mdc"
[ -f "$TOOL_DIR/uninstall.sh" ]      && rm -f "$TOOL_DIR/uninstall.sh"
[ -d "$TOOL_DIR" ]                   && rmdir "$TOOL_DIR" 2>/dev/null && echo "  도구 폴더 삭제 완료"

echo ""
echo "제거 완료."
echo "(Cursor 프로젝트에 .cursor/rules/anr-analysis.mdc 를 복사했다면 그건 수동으로 지워주세요.)"
