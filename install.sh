#!/bin/bash
# ANR 분석 도구 설치 (Linux / macOS / WSL)
# Cline / Cursor / Claude Code 공용.
#   - 파서(anr_parse.py)는 공용이라 ~/.anr-tool 에 한 번만 배치한다.
#   - 룰(zz-anr-rule.md)은 툴마다 읽는 위치가 달라 각 위치에 배치한다.
#   - Cline / Claude Code 는 고정 전역 경로를 쓰므로 해당 툴이 아직 없어도
#     미리 배치해 둔다(무해). 나중에 그 툴을 설치하면 바로 인식된다.
#   - Cursor 는 전역 룰 파일이 없어 ~/.anr-tool/anr-analysis.mdc 를 준비하고
#     사용 방법을 안내한다.
# GitHub에서 최신 파일 자동 다운로드 (실패 시 로컬 payload/ 폴백)

REPO="kingbeanstone/AOA"
BRANCH="main"
DL_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip"
TMP_ZIP="/tmp/anr-tool-latest.zip"
TMP_DIR="/tmp/anr-tool-latest"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 공용 도구 폴더 (파서 + 룰 정본 + Cursor용 mdc)
TOOL_DIR="$HOME/.anr-tool"
# Cline 글로벌 룰 폴더 (고정 전역 경로)
CLINE_RULES="$HOME/Documents/Cline/Rules"
# Claude Code 글로벌 메모리 파일 (고정 전역 경로)
CLAUDE_DIR="$HOME/.claude"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
# Claude Code 가 룰 정본을 불러오도록 추가하는 import 한 줄
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

# payload 파일 위치 확인
if [ ! -f "$PAYLOAD_SRC/zz-anr-rule.md" ]; then
    echo "[오류] payload 폴더에서 룰 파일을 찾을 수 없습니다."
    echo "       경로: $PAYLOAD_SRC"
    echo "       GitHub 연결에 실패한 경우 payload/ 폴더가 install.sh와 같은 위치에 있는지 확인하세요."
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

# 2. 공용 파일 배치 (파서 + 룰 정본 + Cursor용 mdc)
echo "[2/5] 공용 파일 배치  (파서 v${PARSER_VER} / 룰 v${RULE_VER})"
echo "      위치: $TOOL_DIR"
mkdir -p "$TOOL_DIR"
cp "$PAYLOAD_SRC/anr_parse.py" "$TOOL_DIR/anr_parse.py"
chmod +x "$TOOL_DIR/anr_parse.py"
cp "$PAYLOAD_SRC/zz-anr-rule.md" "$TOOL_DIR/zz-anr-rule.md"
# Cursor 프로젝트 룰(.cursor/rules)용 .mdc 정본 생성 (frontmatter + 룰 본문)
CURSOR_MDC="$TOOL_DIR/anr-analysis.mdc"
{
    echo "---"
    echo "description: Android ANR dumpstate analysis. Apply when an ANR/dumpstate file path is given with an analysis request (path + \"anr\")."
    echo "alwaysApply: false"
    echo "---"
    echo ""
    cat "$TOOL_DIR/zz-anr-rule.md"
} > "$CURSOR_MDC"
# uninstall.sh 도 함께 보관
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

# 5. Cursor — 전역 룰 파일이 없어 안내만 (mdc 정본은 위에서 준비됨)
echo "[5/5] Cursor 안내"
echo "      Cursor 는 전역 룰 파일이 없어 자동 배치가 안 됩니다. 둘 중 하나:"
echo "      (A) 전역: Cursor 설정 → Rules → User Rules 에 아래 파일 내용을 붙여넣기 (1회)"
echo "          $TOOL_DIR/zz-anr-rule.md"
echo "      (B) 프로젝트별: 분석할 프로젝트에서"
echo "          mkdir -p .cursor/rules && cp \"$CURSOR_MDC\" .cursor/rules/"
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
echo "  - Cursor     : 위 [5/5] 안내대로 룰 등록 후 채팅(Ctrl/Cmd+L)에 입력"
echo ""
echo "설치된 위치:"
echo "  파서/룰 정본 : $TOOL_DIR/"
echo "  Cline 룰     : $CLINE_RULES/zz-anr-rule.md"
echo "  Claude Code  : $CLAUDE_MD  (import 한 줄)"
echo "  Cursor mdc   : $CURSOR_MDC"
echo ""
echo "제거하려면: bash $TOOL_DIR/uninstall.sh"
echo ""
