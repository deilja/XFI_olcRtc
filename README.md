# XFI_olcRTC

Telegram-бот для управления персональными туннелями olcRTC.

## Возможности

- создание туннеля через Telegram;
- выделение свободного порта `20000–21000`;
- баланс пользователя и списание стоимости туннеля;
- срок действия 30 дней;
- выдача клиентского URI `olcrtc://...`;
- удаление собственного туннеля;
- административная статистика;
- просмотр активных туннелей;
- автоматический контроль срока действия и трафика.

Исходная конфигурация проекта задаёт диапазон портов 20000–21000, стоимость 150 и адрес сервера через `SERVER_IP`. fileciteturn3file0L10-L18

## Структура

```text
XFI_olcRtc/
├── bot.py
├── config.py
├── database.py
├── docker_manager.py
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile.bot
├── docker-compose.yml
├── docker/olcrtc/Dockerfile
└── .github/workflows/ci.yml
```

## Быстрый запуск на Ubuntu

```bash
git clone https://github.com/deilja/XFI_olcRtc.git
cd XFI_olcRtc
cp .env.example .env
mkdir -p /var/lib/xfi-olcrtc data
```

Соберите собственный образ olcRTC из официального исходного репозитория:

```bash
docker build -t xfi-olcrtc:latest ./docker/olcrtc
```

Установите Python-зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Заполните `.env` и запустите:

```bash
python bot.py
```

Для Docker-варианта:

```bash
docker compose --profile build build olcrtc-image
docker compose up -d bot
```

При контейнерном запуске каталог `/var/lib/xfi-olcrtc` должен быть доступен и контейнеру бота, и Docker daemon, поскольку конфигурации отдельных туннелей монтируются в контейнеры olcRTC.

## Переменные окружения

`BOT_TOKEN` — токен Telegram-бота.

`ADMIN_ID` — Telegram ID администратора.

`SERVER_IP` — публичный IP или DNS сервера.

`TUNNEL_COST` — стоимость туннеля.

`OLCRTC_IMAGE` — Docker-образ olcRTC.

`TRAFFIC_LIMIT_GB` — лимит трафика одного туннеля.

## Безопасность

Секреты хранятся только в `.env`; файл исключён из Git. Не добавляйте токен Telegram или другие ключи в исходный код.

Создание туннеля выполняется после проверки баланса. Если запуск контейнера завершается ошибкой, транзакция БД откатывается и средства пользователя не списываются.

## Архитектура

Telegram → aiogram → SQLite/SQLAlchemy → Docker → olcRTC.

Исходный серверный конфиг olcRTC использует режим `srv`, Jitsi provider, DataChannel transport и отдельный crypto key; это соответствует ранее использовавшемуся серверному скрипту проекта. fileciteturn6file0L41-L65
