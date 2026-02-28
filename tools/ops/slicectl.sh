#!/usr/bin/env bash
set -euo pipefail

SERVICE="slice.service"
DEFAULT_FILE="/etc/default/slice"
DOMAIN="dudda.cloud"

usage() {
  cat <<'EOF'
slicectl.sh - helper for frequent Slice service ops

Usage:
  ./tools/ops/slicectl.sh status
  ./tools/ops/slicectl.sh restart
  ./tools/ops/slicectl.sh logs [N]
  ./tools/ops/slicectl.sh test
  ./tools/ops/slicectl.sh env-show
  ./tools/ops/slicectl.sh env-edit

Commands:
  status     Show systemd status (first 40 lines)
  restart    daemon-reload + restart + status
  logs [N]   Show last N log lines (default 80)
  test       Curl checks: localhost + HTTPS login endpoint
  env-show   Print /etc/default/slice with values masked
  env-edit   Open /etc/default/slice in nano, then restart service
EOF
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1"; exit 1; }
}

mask_env() {
  if [[ ! -f "$DEFAULT_FILE" ]]; then
    echo "$DEFAULT_FILE not found"
    return 1
  fi

  awk -F= '
    BEGIN{OFS="="}
    /^\s*#/ {print; next}
    /^\s*$/ {print; next}
    {
      k=$1; v=$2
      if (k ~ /GOOGLE_CLIENT_SECRET/) {
        if (length(v) <= 8) v="********"
        else v=substr(v,1,4) "..." substr(v,length(v)-3,4)
      }
      print k,v
    }
  ' "$DEFAULT_FILE"
}

cmd_status() {
  sudo systemctl status --no-pager "$SERVICE" | sed -n '1,40p'
}

cmd_restart() {
  sudo systemctl daemon-reload
  sudo systemctl restart "$SERVICE"
  cmd_status
}

cmd_logs() {
  local n="${1:-80}"
  sudo journalctl -u "$SERVICE" -n "$n" --no-pager
}

cmd_test() {
  echo "[localhost]"
  curl -s -I http://127.0.0.1:8787 | head -n 1 || true
  echo "[public root]"
  curl -s -I "https://$DOMAIN" | head -n 1 || true
  echo "[public login]"
  curl -s -I "https://$DOMAIN/login" | head -n 1 || true
}

cmd_env_show() {
  mask_env
}

cmd_env_edit() {
  sudo nano "$DEFAULT_FILE"
  cmd_restart
}

main() {
  need_cmd sudo
  need_cmd systemctl

  local sub="${1:-}"
  case "$sub" in
    status) cmd_status ;;
    restart) cmd_restart ;;
    logs) shift || true; cmd_logs "${1:-80}" ;;
    test) cmd_test ;;
    env-show) cmd_env_show ;;
    env-edit) cmd_env_edit ;;
    -h|--help|help|"") usage ;;
    *) echo "Unknown command: $sub"; usage; exit 1 ;;
  esac
}

main "$@"
