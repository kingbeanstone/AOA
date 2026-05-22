#!/bin/bash
# ANR 분석 도구 설치 스터브 (Linux / macOS / WSL)
# 이 파일 하나만 받아서 실행하면 됩니다

REPO="kingbeanstone/aoa2"
BRANCH="claude/anr-analysis-tool-rz6Rv"
DL_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip"
TMP_ZIP="/tmp/anr-tool-latest.zip"
TMP_DIR="/tmp/anr-tool-latest"

echo ""
echo "============================================================"
echo "  ANR 분석 도구 설치 준비 중..."
echo "============================================================"
echo ""

echo "GitHub에서 최신 버전 다운로드 중... (잠시 기다려주세요)"
DOWNLOADED=0
if curl -fsSL "$DL_URL" -o "$TMP_ZIP" 2>/dev/null; then
    DOWNLOADED=1
elif wget -q "$DL_URL" -O "$TMP_ZIP" 2>/dev/null; then
    DOWNLOADED=1
fi

if [ "$DOWNLOADED" -eq 0 ]; then
    echo ""
    echo "[오류] GitHub 연결에 실패했습니다."
    echo "       네트워크 상태를 확인하거나 관리자에게 문의하세요."
    echo ""
    exit 1
fi

echo "파일 준비 중..."
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
unzip -oq "$TMP_ZIP" -d "$TMP_DIR" 2>/dev/null
rm -f "$TMP_ZIP"

EXTRACTED=$(ls -d "$TMP_DIR"/aoa2-*/ 2>/dev/null | head -1)
if [ -z "$EXTRACTED" ]; then
    echo ""
    echo "[오류] 파일 준비에 실패했습니다. 관리자에게 문의하세요."
    echo ""
    exit 1
fi

echo ""
bash "${EXTRACTED}install.sh" skip

rm -rf "$TMP_DIR"
