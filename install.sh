#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/deilja/XFI_olcRtc.git"
DIR="${XFI_OLCRTC_DIR:-$PWD/XFI_olcRtc}"

need_cmd() { command -v "$1" >/dev/null 2>&1; }

if ! need_cmd git; then
  if need_cmd apt-get; then sudo apt-get update && sudo apt-get install -y git; else echo "Установите git"; exit 1; fi
fi

if ! need_cmd docker; then
  if need_cmd curl && need_cmd sudo; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo systemctl enable --now docker || true
  else
    echo "Docker не найден. Установите Docker и повторите."; exit 1
  fi
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 не найден."; exit 1
fi

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone "$REPO" "$DIR"
fi
cd "$DIR"

[ -f .env ] || cp .env.example .env

set_env() {
  local key="$1" value="$2"
  python3 - "$key" "$value" <<'PY'
import pathlib, sys
key, value = sys.argv[1], sys.argv[2]
p = pathlib.Path('.env')
lines = p.read_text().splitlines() if p.exists() else []
found = False
out = []
for line in lines:
    if line.startswith(key + '='):
        out.append(f'{key}={value}'); found = True
    else: out.append(line)
if not found: out.append(f'{key}={value}')
p.write_text('\n'.join(out) + '\n')
PY
}

read -r -p "Telegram BOT_TOKEN: " BOT_TOKEN
read -r -p "Telegram ADMIN_ID: " ADMIN_ID
read -r -p "Публичный IP/домен сервера: " SERVER_IP
read -r -p "3X-UI host [http://127.0.0.1:2053]: " XUI_HOST
XUI_HOST=${XUI_HOST:-http://127.0.0.1:2053}
read -r -p "3X-UI username [admin]: " XUI_USERNAME
XUI_USERNAME=${XUI_USERNAME:-admin}
read -r -s -p "3X-UI password: " XUI_PASSWORD; echo
read -r -p "3X-UI inbound ID [1]: " XUI_INBOUND_ID
XUI_INBOUND_ID=${XUI_INBOUND_ID:-1}
read -r -p "Reality public key: " XUI_PUBLIC_KEY
read -r -p "Reality short ID: " XUI_SHORT_ID

set_env BOT_TOKEN "$BOT_TOKEN"
set_env ADMIN_ID "$ADMIN_ID"
set_env SERVER_IP "$SERVER_IP"
set_env XUI_HOST "$XUI_HOST"
set_env XUI_USERNAME "$XUI_USERNAME"
set_env XUI_PASSWORD "$XUI_PASSWORD"
set_env XUI_INBOUND_ID "$XUI_INBOUND_ID"
set_env XUI_PUBLIC_KEY "$XUI_PUBLIC_KEY"
set_env XUI_SHORT_ID "$XUI_SHORT_ID"

mkdir -p data
docker compose up -d --build

echo
echo "XFI_olcRTC запущен."
docker compose ps
echo "Логи: cd '$DIR' && docker compose logs -f olcrtc-bot"
