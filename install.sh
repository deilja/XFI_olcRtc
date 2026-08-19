#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/deilja/XFI_olcRtc.git"
DIR="${XFI_OLCRTC_DIR:-$PWD/XFI_olcRtc}"

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

need_cmd() { command -v "$1" >/dev/null 2>&1; }

if ! need_cmd git || ! need_cmd curl || ! need_cmd python3; then
  if ! need_cmd apt-get; then
    echo "Ошибка: требуется apt-get для автоматической установки зависимостей."
    exit 1
  fi
  as_root apt-get update
  packages=()
  need_cmd git || packages+=(git)
  need_cmd curl || packages+=(curl)
  need_cmd python3 || packages+=(python3)
  if [ "${#packages[@]}" -gt 0 ]; then
    as_root apt-get install -y "${packages[@]}"
  fi
fi

if ! need_cmd docker; then
  curl -fsSL https://get.docker.com | as_root sh
  as_root systemctl enable --now docker || true
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Ошибка: Docker Compose v2 не найден."
  exit 1
fi

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch origin main
  git -C "$DIR" reset --hard origin/main
else
  git clone --branch main --single-branch "$REPO" "$DIR"
fi
cd "$DIR"

[ -f .env ] || cp .env.example .env
mkdir -p data
chmod 700 data

set_env() {
  local key="$1" value="$2"
  KEY="$key" VALUE="$value" python3 - <<'PY'
import os
from pathlib import Path

key = os.environ["KEY"]
value = os.environ["VALUE"]
p = Path(".env")
lines = p.read_text().splitlines() if p.exists() else []
out = []
found = False
for line in lines:
    if line.startswith(key + "="):
        out.append(f"{key}={value}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"{key}={value}")
p.write_text("\n".join(out) + "\n")
PY
}

read -r -p "Telegram BOT_TOKEN: " BOT_TOKEN
read -r -p "Telegram ADMIN_ID: " ADMIN_ID
read -r -p "Публичный IP/домен сервера: " SERVER_IP
read -r -p "3X-UI host [http://host.docker.internal:2053]: " XUI_HOST
XUI_HOST=${XUI_HOST:-http://host.docker.internal:2053}
read -r -p "3X-UI username [admin]: " XUI_USERNAME
XUI_USERNAME=${XUI_USERNAME:-admin}
read -r -s -p "3X-UI password: " XUI_PASSWORD
printf '\n'
read -r -p "3X-UI inbound ID [1]: " XUI_INBOUND_ID
XUI_INBOUND_ID=${XUI_INBOUND_ID:-1}
read -r -p "Reality public key: " XUI_PUBLIC_KEY
read -r -p "Reality short ID: " XUI_SHORT_ID
read -r -p "Reality SNI [yahoo.com]: " XUI_SNI
XUI_SNI=${XUI_SNI:-yahoo.com}
read -r -p "VLESS server port [443]: " XUI_SERVER_PORT
XUI_SERVER_PORT=${XUI_SERVER_PORT:-443}

set_env BOT_TOKEN "$BOT_TOKEN"
set_env ADMIN_ID "$ADMIN_ID"
set_env SERVER_IP "$SERVER_IP"
set_env XUI_HOST "$XUI_HOST"
set_env XUI_USERNAME "$XUI_USERNAME"
set_env XUI_PASSWORD "$XUI_PASSWORD"
set_env XUI_INBOUND_ID "$XUI_INBOUND_ID"
set_env XUI_PUBLIC_KEY "$XUI_PUBLIC_KEY"
set_env XUI_SHORT_ID "$XUI_SHORT_ID"
set_env XUI_SNI "$XUI_SNI"
set_env XUI_SERVER_PORT "$XUI_SERVER_PORT"

chmod 600 .env

docker compose config >/dev/null
docker compose build --pull
docker compose up -d

echo
echo "XFI_olcRTC установлен и запущен."
docker compose ps

echo "Проверка логов: cd '$DIR' && docker compose logs --tail=100 olcrtc-bot"
echo "Онлайн-логи: cd '$DIR' && docker compose logs -f olcrtc-bot"
