#!/bin/bash
# Shortform Auto Uploader 데몬 LaunchAgent를 제거한다.
# 사용: bash deploy/uninstall_launchagent.sh
set -euo pipefail

LABEL="com.shortformauto.daemon"
DEST_PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"

launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
rm -f "$DEST_PLIST"
echo "제거 완료: $LABEL"
