#!/bin/bash
# Shortform Auto Uploader 데몬을 LaunchAgent로 설치/재설치한다.
# 사용: bash deploy/install_launchagent.sh
set -euo pipefail

LABEL="com.shortformauto.daemon"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_PLIST="$SCRIPT_DIR/$LABEL.plist"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST_PLIST="$DEST_DIR/$LABEL.plist"
UID_NUM="$(id -u)"

mkdir -p "$HOME/Library/Logs"

# ~/Library/LaunchAgents 가 없거나 쓰기 불가(root 소유 등)면 안내 후 중단.
if [ ! -d "$DEST_DIR" ]; then
    mkdir -p "$DEST_DIR" 2>/dev/null || true
fi
if [ ! -w "$DEST_DIR" ]; then
    echo "[오류] $DEST_DIR 에 쓸 수 없습니다 (소유자: $(stat -f '%Su' "$DEST_DIR" 2>/dev/null))."
    echo "       아래 한 줄을 먼저 실행해 소유권을 사용자로 되돌리세요:"
    echo "       sudo chown $(whoami):staff \"$DEST_DIR\" && chmod 755 \"$DEST_DIR\""
    exit 1
fi

cp "$SRC_PLIST" "$DEST_PLIST"

# 기존에 로드되어 있으면 내린다 (idempotent).
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true

# 로드 후 즉시 기동.
launchctl bootstrap "gui/$UID_NUM" "$DEST_PLIST"
launchctl kickstart -k "gui/$UID_NUM/$LABEL"

echo "설치 완료: $DEST_PLIST"
echo "상태 확인: launchctl print gui/$UID_NUM/$LABEL | grep state"
echo "로그: ~/Library/Logs/shortformauto.out.log"
