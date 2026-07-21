#!/bin/bash
# Shortform Auto Uploader의 LaunchAgent를 설치/재설치한다.
#   데몬(업로드 처리) + 대시보드(Streamlit) 두 개를 모두 등록한다.
#
# 사용:
#   bash deploy/install_launchagent.sh            # 둘 다 설치
#   bash deploy/install_launchagent.sh daemon     # 데몬만
#   bash deploy/install_launchagent.sh dashboard  # 대시보드만
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"

case "${1:-all}" in
    daemon)    LABELS=("com.shortformauto.daemon") ;;
    dashboard) LABELS=("com.shortformauto.dashboard") ;;
    all)       LABELS=("com.shortformauto.daemon" "com.shortformauto.dashboard") ;;
    *) echo "사용법: $0 [all|daemon|dashboard]"; exit 1 ;;
esac

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

for LABEL in "${LABELS[@]}"; do
    SRC_PLIST="$SCRIPT_DIR/$LABEL.plist"
    DEST_PLIST="$DEST_DIR/$LABEL.plist"

    cp "$SRC_PLIST" "$DEST_PLIST"

    # 기존에 로드되어 있으면 내린다 (idempotent).
    launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
    # bootout은 비동기라, 프로세스가 완전히 내려가기 전에 bootstrap하면 I/O 오류가 난다.
    for _ in $(seq 1 20); do
        launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 || break
        sleep 0.5
    done

    launchctl bootstrap "gui/$UID_NUM" "$DEST_PLIST"
    echo "설치 완료: $LABEL"
done

echo
echo "상태 확인: launchctl list | grep shortformauto"
echo "데몬 로그:     ~/Library/Logs/shortformauto.err.log"
echo "대시보드 로그: ~/Library/Logs/shortformauto.dashboard.err.log"
