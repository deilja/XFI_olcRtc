# XFI_olcRTC

Telegram-бот для управления персональными VLESS-подписками через 3X-UI.

## Возможности

- создание VLESS-клиента через Telegram;
- автоматическая генерация UUID и email клиента;
- баланс пользователя и списание стоимости подписки;
- срок действия подписки 30 дней;
- лимит трафика на клиента;
- выдача готового VLESS Reality URI;
- продление подписки с очисткой трафика;
- удаление подписки из 3X-UI;
- административная статистика и список подписок;
- фоновый контроль срока действия и трафика.

## Структура

```text
XFI_olcRtc/
├── bot.py
├── config.py
├── database.py
├── xui_manager.py
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Архитектура

```text
Telegram
   ↓
aiogram
   ↓
XFI_olcRtc bot
   ├── SQLite / SQLAlchemy
   └── 3X-UI API
          ↓
        Xray
          ↓
     VLESS Reality
```

## Быстрый запуск

```bash
git clone https://github.com/deilja/XFI_olcRtc.git
cd XFI_olcRtc
cp .env.example .env
mkdir -p data
```

Заполните `.env`:

- `BOT_TOKEN` — токен Telegram-бота;
- `ADMIN_ID` — Telegram ID администратора;
- `SERVER_IP` — публичный IP или DNS сервера Xray;
- `XUI_HOST` — адрес панели 3X-UI;
- `XUI_USERNAME` / `XUI_PASSWORD` — учётные данные панели;
- `XUI_INBOUND_ID` — ID VLESS inbound;
- `XUI_PUBLIC_KEY` — публичный Reality key;
- `XUI_SHORT_ID` — Reality short ID;
- `XUI_SNI` — SNI;
- `XUI_FINGERPRINT` — fingerprint клиента.

### Docker

```bash
docker compose build
docker compose up -d
```

### Запуск без Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## Безопасность

Файл `.env` не должен попадать в Git. Токен Telegram и пароль 3X-UI хранятся только в переменных окружения.

В `.env.example` используются только шаблонные значения. Реальные `BOT_TOKEN`, `XUI_PASSWORD`, `XUI_PUBLIC_KEY` и `XUI_SHORT_ID` в репозиторий добавлять нельзя.

## API 3X-UI

Проект использует стандартные операции 3X-UI для авторизации, добавления VLESS-клиента, удаления клиента и сброса его трафика. API 3X-UI документирует `/login`, `/inbounds/addClient`, `/inbounds/:id/delClient/:clientId`, `/inbounds/updateClient/:clientId` и сброс трафика клиента. citeturn0search2turn0search1
