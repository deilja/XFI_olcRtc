# XFI_olcRTC

Универсальный Telegram-бот для управления VLESS через 3X-UI и olcRTC-туннелями через Docker.

## Возможности

- создание VLESS-клиента через 3X-UI;
- создание olcRTC-туннеля через Docker;
- единая SQLite/SQLAlchemy база пользователей и подписок;
- баланс пользователя и списание стоимости подписки;
- срок действия подписки 30 дней;
- лимит трафика;
- выдача VLESS Reality и olcRTC конфигурации;
- продление и удаление подписок;
- административная статистика;
- фоновый контроль срока, трафика и состояния backend.

## Архитектура

```text
Telegram
   ↓
aiogram
   ↓
XFI_olcRtc bot
   ├── SQLite / SQLAlchemy
   ├── VLESS → 3X-UI → Xray
   └── olcRTC → Docker → olcrtc/srv
```

## Установка одной командой

Требуются Docker и Docker Compose v2.

```bash
curl -fsSL https://raw.githubusercontent.com/deilja/XFI_olcRtc/main/install.sh | bash
```

Скрипт клонирует или обновляет репозиторий, создаёт `.env` из `.env.example`, собирает Docker-образ и запускает `olcrtc-bot`.

После первого запуска заполните `.env`:

```env
BOT_TOKEN=ваш_telegram_bot_token
ADMIN_ID=123456789
SERVER_IP=ваш_публичный_ip_или_домен
PORT_RANGE_START=20000
PORT_RANGE_END=21000
TUNNEL_COST=150.0
TRAFFIC_LIMIT_GB=10

XUI_HOST=http://127.0.0.1:2053
XUI_USERNAME=admin
XUI_PASSWORD=ваш_пароль
XUI_INBOUND_ID=1
XUI_SERVER_PORT=443
XUI_PUBLIC_KEY=ваш_reality_public_key
XUI_SHORT_ID=ваш_reality_short_id
XUI_SNI=yahoo.com
XUI_FINGERPRINT=chrome
```

Затем примените настройки:

```bash
docker compose up -d --build
```

## Управление

```bash
docker compose ps
docker compose logs -f olcrtc-bot
docker compose restart
docker compose down
```

## Docker и olcRTC

Бот получает `/var/run/docker.sock`, поскольку должен создавать, останавливать и удалять olcRTC-контейнеры динамически. Это предоставляет контейнеру бота высокий уровень контроля над Docker-хостом. Используйте такой режим только на доверенном сервере.

## Безопасность

`.env` и `database.sqlite` не должны публиковаться в GitHub. Реальные `BOT_TOKEN`, пароль 3X-UI, Reality public key и short ID должны храниться только в `.env`.

## Структура

```text
XFI_olcRtc/
├── bot.py
├── config.py
├── database.py
├── xui_manager.py
├── docker_manager.py
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── install.sh
└── .github/workflows/ci.yml
```
