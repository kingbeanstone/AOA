#!/bin/bash
# ANR 분석 도구 제거 (Linux / macOS / WSL)

RULES_DIR="$HOME/Documents/Cline/Rules"
TOOL_DIR="$HOME/.anr-tool"

echo "ANR 분석 도구 제거"
echo ""

[ -f "$RULES_DIR/zz-anr-rule.md" ] && rm "$RULES_DIR/zz-anr-rule.md" && echo "  룰 파일 삭제 완료"
[ -f "$TOOL_DIR/anr_parse.py" ]    && rm "$TOOL_DIR/anr_parse.py"    && echo "  파서 파일 삭제 완료"
[ -d "$TOOL_DIR" ]                 && rmdir "$TOOL_DIR" 2>/dev/null  && echo "  도구 폴더 삭제 완료"

echo ""
echo "제거 완료."
