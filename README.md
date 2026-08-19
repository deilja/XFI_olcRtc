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
- просмотр и принудительная остановка активных туннелей;
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
└── README.md
```

## Установка

```bash
git clone https://github.com/deilja/XFI_olcRtc.git
cd XFI_olcRtc
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`, затем:

```bash
python bot.py
```

Docker должен быть установлен, а пользователь процесса бота должен иметь доступ к Docker socket.

## Переменные окружения

`BOT_TOKEN` — токен Telegram-бота.

`ADMIN_ID` — Telegram ID администратора.

`SERVER_IP` — публичный IP или DNS сервера.

`TUNNEL_COST` — стоимость туннеля.

`OLCRTC_IMAGE` — Docker-образ olcRTC; по умолчанию используется значение из `.env.example`.

`TRAFFIC_LIMIT_GB` — лимит трафика одного туннеля.

## Архитектура

Telegram → aiogram → SQLite/SQLAlchemy → Docker → olcRTC.

Создание туннеля выполняется только после проверки баланса. При ошибке запуска контейнера транзакция пользователя откатывается.
