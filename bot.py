import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from config import BOT_TOKEN, ADMIN_ID, PORT_RANGE_START, PORT_RANGE_END, SERVER_IP, TUNNEL_COST
from database import Tunnel, User, async_session, get_free_port, get_or_create_user, init_db
from docker_manager import client, create_container, stop_container

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID не задан")
if not SERVER_IP:
    raise RuntimeError("SERVER_IP не задан")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class TunnelCreation(StatesGroup):
    waiting_for_room_url = State()


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def valid_room_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def main_keyboard() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Создать туннель")],
            [types.KeyboardButton(text="📋 Мои туннели")],
        ],
        resize_keyboard=True,
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Бот управления персональными туннелями olcRTC.\nВыберите действие ниже.",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        await session.commit()
        await message.answer(f"Ваш баланс: {user.balance:.2f}")


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Операция отменена.", reply_markup=main_keyboard())


@dp.message(Command("give"))
async def cmd_give(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = (message.text or "").split()
    if len(args) != 3:
        await message.answer("Использование: /give <user_id> <amount>")
        return
    try:
        target_user_id = int(args[1])
        amount = float(args[2])
    except ValueError:
        await message.answer("user_id и сумма должны быть числами.")
        return
    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return

    async with async_session() as session:
        user = await get_or_create_user(session, target_user_id)
        user.balance += amount
        await session.commit()
        await message.answer(
            f"Баланс пользователя {target_user_id} пополнен на {amount:.2f}.\n"
            f"Текущий баланс: {user.balance:.2f}"
        )


@dp.message(F.text == "➕ Создать туннель")
async def start_creation(message: types.Message, state: FSMContext):
    await state.set_state(TunnelCreation.waiting_for_room_url)
    await message.answer("Отправьте HTTPS/HTTP-ссылку на вашу видеокомнату.\n/cancel — отмена.")


@dp.message(TunnelCreation.waiting_for_room_url)
async def process_room_url(message: types.Message, state: FSMContext):
    room_url = (message.text or "").strip()
    if not valid_room_url(room_url):
        await message.answer("Некорректная ссылка. Используйте URL вида https://example.com/room.")
        return

    user_id = message.from_user.id
    container_id = None

    async with async_session() as session:
        user = await get_or_create_user(session, user_id)
        if user.balance < TUNNEL_COST:
            await message.answer(
                f"Недостаточно средств. Требуется {TUNNEL_COST:.2f}, доступно {user.balance:.2f}."
            )
            await state.clear()
            return

        port = await get_free_port(session)
        expires_at = now_utc() + timedelta(days=30)
        try:
            container_id = create_container(room_url, port, user_id)
            user.balance -= TUNNEL_COST
            tunnel = Tunnel(
                user_id=user_id,
                container_id=container_id,
                room_url=room_url,
                port=port,
                is_active=True,
                expires_at=expires_at,
            )
            session.add(tunnel)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            if container_id:
                try:
                    stop_container(container_id)
                except Exception:
                    pass
            await message.answer(f"Не удалось создать туннель: {type(exc).__name__}. Средства не списаны.")
            await state.clear()
            return

    await state.clear()
    config_uri = f"olcrtc://{SERVER_IP}:{port}?{urlencode({'room': room_url})}"
    await message.answer(
        f"Туннель создан.\n\n"
        f"Порт: {port}\n"
        f"Комната: {room_url}\n"
        f"Активен до: {expires_at:%Y-%m-%d %H:%M} UTC\n"
        f"Списано: {TUNNEL_COST:.2f}\n\n"
        f"Конфиг:\n{config_uri}"
    )


@dp.message(F.text == "📋 Мои туннели")
async def list_user_tunnels(message: types.Message):
    async with async_session() as session:
        tunnels = (
            await session.scalars(
                select(Tunnel).where(Tunnel.user_id == message.from_user.id, Tunnel.is_active.is_(True))
            )
        ).all()

    if not tunnels:
        await message.answer("У вас нет активных туннелей.")
        return

    for tunnel in tunnels:
        config_uri = f"olcrtc://{SERVER_IP}:{tunnel.port}?{urlencode({'room': tunnel.room_url})}"
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_tunnel:{tunnel.id}")]]
        )
        traffic_gb = tunnel.traffic_used_bytes / 1024**3
        limit_gb = tunnel.traffic_limit_bytes / 1024**3
        await message.answer(
            f"Порт: {tunnel.port}\nКомната: {tunnel.room_url}\n"
            f"Трафик: {traffic_gb:.2f} / {limit_gb:.2f} ГБ\n"
            f"До: {tunnel.expires_at:%Y-%m-%d %H:%M} UTC\n\n"
            f"Конфиг:\n{config_uri}",
            reply_markup=keyboard,
        )


@dp.callback_query(F.data.startswith("del_tunnel:"))
async def delete_tunnel_callback(callback: types.CallbackQuery):
    try:
        tunnel_id = int(callback.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Некорректный запрос.", show_alert=True)
        return

    async with async_session() as session:
        tunnel = await session.scalar(
            select(Tunnel).where(Tunnel.id == tunnel_id, Tunnel.user_id == callback.from_user.id)
        )
        if not tunnel or not tunnel.is_active:
            await callback.answer("Туннель не найден.", show_alert=True)
            return
        try:
            stop_container(tunnel.container_id)
        except Exception:
            pass
        tunnel.is_active = False
        await session.commit()
        port = tunnel.port

    await callback.message.edit_text(f"Туннель на порту {port} удалён.")
    await callback.answer()


async def admin_menu(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [types.InlineKeyboardButton(text="🌐 Активные туннели", callback_data="admin:list")],
            [types.InlineKeyboardButton(text="💰 Пополнение", callback_data="admin:give")],
        ]
    )
    await message.answer("Панель администратора olcRTC", reply_markup=keyboard)


@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await admin_menu(message)


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    async with async_session() as session:
        users = await session.scalar(select(func.count(User.id)))
        tunnels = await session.scalar(select(func.count(Tunnel.id)).where(Tunnel.is_active.is_(True)))
    try:
        running = len(client.containers.list(filters={"label": "app=xfi-olcrtc"}))
    except Exception:
        running = "ошибка Docker"
    await callback.message.edit_text(
        f"Пользователей: {users}\nАктивных туннелей: {tunnels}\n"
        f"Контейнеров: {running}\nПорты: {PORT_RANGE_START}–{PORT_RANGE_END}"
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:give")
async def admin_help_give(callback: types.CallbackQuery):
    if callback.from_user.id == ADMIN_ID:
        await callback.message.edit_text("Пополнение: /give <user_id> <сумма>")
    await callback.answer()


@dp.callback_query(F.data == "admin:list")
async def admin_list_tunnels(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    async with async_session() as session:
        tunnels = (await session.scalars(select(Tunnel).where(Tunnel.is_active.is_(True)))).all()
    if not tunnels:
        await callback.message.edit_text("Активных туннелей нет.")
        await callback.answer()
        return
    text = "\n".join(
        f"#{t.id} | user={t.user_id} | port={t.port} | до={t.expires_at:%Y-%m-%d %H:%M} UTC"
        for t in tunnels
    )
    await callback.message.edit_text(text[:4000])
    await callback.answer()


async def background_monitoring():
    async with async_session() as session:
        tunnels = (await session.scalars(select(Tunnel).where(Tunnel.is_active.is_(True)))).all()
        changed = False
        for tunnel in tunnels:
            should_close = now_utc() >= tunnel.expires_at
            try:
                container = client.containers.get(tunnel.container_id)
                if container.status != "running":
                    should_close = True
                else:
                    stats = container.stats(stream=False)
                    total = sum(
                        int(net.get("rx_bytes", 0)) + int(net.get("tx_bytes", 0))
                        for net in stats.get("networks", {}).values()
                    )
                    tunnel.traffic_used_bytes = total
                    if total >= tunnel.traffic_limit_bytes:
                        should_close = True
            except Exception:
                should_close = True

            if should_close:
                try:
                    stop_container(tunnel.container_id)
                except Exception:
                    pass
                tunnel.is_active = False
                changed = True
                try:
                    await bot.send_message(
                        tunnel.user_id,
                        f"Туннель на порту {tunnel.port} остановлен: срок действия или лимит трафика исчерпан.",
                    )
                except Exception:
                    pass
        if changed:
            await session.commit()


async def main():
    await init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(background_monitoring, "interval", minutes=5, max_instances=1, coalesce=True)
    scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
