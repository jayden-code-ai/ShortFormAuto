#!/bin/bash
# Shortform Auto Uploader의 LaunchAgent를 제거한다.
#
# 사용:
#   bash deploy/uninstall_launchagent.sh            # 둘 다 제거
#   bash deploy/uninstall_launchagent.sh daemon     # 데몬만
#   bash deploy/uninstall_launchagent.sh dashboard  # 대시보드만
set -euo pipefail

DEST_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"

case "${1:-all}" in
    daemon)    LABELS=("com.shortformauto.daemon") ;;
    dashboard) LABELS=("com.shortformauto.dashboard") ;;
    all)       LABELS=("com.shortformauto.daemon" "com.shortformauto.dashboard") ;;
    *) echo "사용법: $0 [all|daemon|dashboard]"; exit 1 ;;
esac

for LABEL in "${LABELS[@]}"; do
    launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
    rm -f "$DEST_DIR/$LABEL.plist"
    echo "제거 완료: $LABEL"
done
