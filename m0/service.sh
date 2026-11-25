#!/usr/bin/env bash
set -euo pipefail
M0_ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
M0_UNIT=paper-in-m0
case "${1:-status}" in
  start)
    if systemctl --user is-active --quiet "$M0_UNIT"; then
      systemctl --user status "$M0_UNIT" --no-pager
      exit 0
    fi
    mkdir -p "$M0_ROOT_DIR/logs"
    systemctl --user reset-failed "$M0_UNIT" 2>/dev/null || true
    systemd-run --user --unit="$M0_UNIT" \
      --property="WorkingDirectory=$M0_ROOT_DIR" \
      --property="StandardOutput=append:$M0_ROOT_DIR/logs/m0_server_systemd.log" \
      --property="StandardError=append:$M0_ROOT_DIR/logs/m0_server_systemd.log" \
      --setenv="M0_GPU=${M0_GPU:-3}" --setenv="M0_PORT=${M0_PORT:-28760}" \
      /bin/bash "$M0_ROOT_DIR/m0/start.sh"
    ;;
  stop) systemctl --user stop "$M0_UNIT" ;;
  status) systemctl --user status "$M0_UNIT" --no-pager ;;
  *) echo 'Usage: bash m0/service.sh start|status|stop'; exit 2 ;;
esac
