#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/deilja/XFI_olcRtc.git"
DIR="${XFI_OLCRTC_DIR:-XFI_olcRtc}"

if ! command -v git >/dev/null 2>&1; then
  echo "Ошибка: git не установлен."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Ошибка: Docker не установлен. Установите Docker и повторите запуск."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Ошибка: Docker Compose v2 не найден."
  exit 1
fi

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone "$REPO" "$DIR"
fi

cd "$DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Создан .env из .env.example. Заполните BOT_TOKEN, ADMIN_ID, SERVER_IP и параметры 3X-UI."
fi

docker compose build
docker compose up -d

echo
echo "XFI_olcRtc установлен и запущен."
echo "Проверка: docker compose ps"
echo "Логи:     docker compose logs -f olcrtc-bot"
