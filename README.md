# XFI_olcRTC

Универсальный Telegram-бот для управления VLESS через 3X-UI и olcRTC-туннелями через Docker.

## Возможности

- создание VLESS-клиента через 3X-UI;
- создание olcRTC-туннеля через Docker;
- SQLite + SQLAlchemy;
- баланс пользователя и списание стоимости;
- подписка с настраиваемым сроком;
- лимит трафика;
- VLESS Reality и olcRTC URI;
- продление и удаление подписок;
- административная статистика;
- фоновый контроль срока, трафика и состояния backend;
- восстановление backend после перезапуска VPS или контейнера;
- очистка осиротевших XFI Docker-контейнеров и VLESS-клиентов;
- CI-проверка Python и Docker Compose;
- автоматическая установка и запуск через Docker Compose.

## Архитектура

```text
Telegram
   ↓
aiogram
   ↓
XFI_olcRtc bot
   ├── SQLite / SQLAlchemy
   ├── Recovery / Reconciliation
   ├── VLESS → 3X-UI → Xray
   └── olcRTC → Docker → olcRTC server
```

## Восстановление после перезапуска

При старте бот выполняет сверку БД с backend:

1. активный VLESS отсутствует в 3X-UI → клиент восстанавливается с тем же UUID и email;
2. активный olcRTC-контейнер отсутствует → контейнер пересоздаётся на сохранённом порту;
3. истёкшие записи закрываются;
4. осиротевшие контейнеры с префиксом `olcrtc_` удаляются;
5. осиротевшие VLESS-клиенты с префиксом `xfi_` удаляются;
6. сверка повторяется каждые 5 минут.

Если backend временно недоступен, записи не удаляются только из-за ошибки связи; следующая сверка повторит восстановление.

## Установка одной командой

Для Ubuntu/Debian скрипт может установить Docker автоматически, если его нет:

```bash
curl -fsSL https://raw.githubusercontent.com/deilja/XFI_olcRtc/main/install.sh | bash
```

Во время установки скрипт запросит:

- Telegram BOT_TOKEN;
- ADMIN_ID;
- публичный IP/домен сервера;
- адрес 3X-UI;
- логин и пароль 3X-UI;
- ID inbound;
- Reality public key;
- Reality short ID.

Если 3X-UI работает на том же сервере, рекомендуется оставить предложенный адрес:

```env
XUI_HOST=http://host.docker.internal:2053
```

Docker Compose связывает `host.docker.internal` с хостом через `host-gateway`.

## Настройки

Основные параметры находятся в `.env`:

```env
BOT_TOKEN=ваш_telegram_bot_token
ADMIN_ID=123456789
SERVER_IP=ваш_публичный_ip_или_домен
DB_PATH=/app/data/database.sqlite
PORT_RANGE_START=20000
PORT_RANGE_END=21000
TUNNEL_COST=150.0
TRAFFIC_LIMIT_GB=10
SUBSCRIPTION_DAYS=30

XUI_HOST=http://host.docker.internal:2053
XUI_USERNAME=admin
XUI_PASSWORD=ваш_пароль
XUI_INBOUND_ID=1
XUI_SERVER_PORT=443
XUI_PUBLIC_KEY=ваш_reality_public_key
XUI_SHORT_ID=ваш_reality_short_id
XUI_SNI=yahoo.com
XUI_FINGERPRINT=chrome

OLCRTC_IMAGE=olcrtc/srv:latest
```

## Управление

```bash
docker compose ps
docker compose logs -f olcrtc-bot
docker compose restart
docker compose down
docker compose up -d --build
```

## Telegram

Пользователь:

- `/start` — главное меню;
- `/balance` — баланс;
- `➕ Создать VLESS` — создать VLESS;
- `📞 Создать olcRTC` — создать olcRTC;
- `📋 Мои подписки` — активные подписки;
- `/cancel` — отменить ввод URL.

Администратор:

- `/admin` — состояние системы;
- `/give <user_id> <сумма>` — пополнить баланс;
- `/transactions` — последние финансовые операции.

## Docker и безопасность

Бот использует `/var/run/docker.sock`, потому что должен создавать и удалять olcRTC-контейнеры динамически. Доступ к Docker socket фактически даёт контейнеру высокий уровень контроля над Docker-хостом. Используйте проект только на доверенном сервере и не открывайте Telegram-бота для недоверенных администраторов.

## Безопасность конфигурации

Не публикуйте `.env` и реальные секреты. В репозитории должны оставаться только шаблон `.env.example` и тестовые значения.

## Структура

```text
XFI_olcRtc/
├── bot.py
├── config.py
├── database.py
├── recovery.py
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
