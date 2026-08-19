import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from config import (
    ADMIN_ID,
    BOT_TOKEN,
    PORT_RANGE_END,
    PORT_RANGE_START,
    SERVER_IP,
    TUNNEL_COST,
    TRAFFIC_LIMIT_GB,
    XUI_FINGERPRINT,
    XUI_INBOUND_ID,
    XUI_PUBLIC_KEY,
    XUI_SERVER_PORT,
    XUI_SHORT_ID,
    XUI_SNI,
)
from database import Tunnel, User, async_session, get_free_port, get_or_create_user, init_db
from xui_manager import (
    create_vless_client,
    delete_vless_client,
    get_inbound_client_stats,
    reset_client_traffic,
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID не задан")
if not SERVER_IP:
    raise RuntimeError("SERVER_IP не задан")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class TunnelCreation(StatesGroup):
    waiting = State()


def vless_uri(client_uuid: str, email: str) -> str:
    return (
        f"vless://{client_uuid}@{SERVER_IP}:{XUI_SERVER_PORT}"
        f"?encryption=none&flow=xtls-rprx-vision&security=reality"
        f"&sni={XUI_SNI}&fp={XUI_FINGERPRINT}&pbk={XUI_PUBLIC_KEY}"
        f"&sid={XUI_SHORT_ID}&type=tcp&headerType=none#{email}"
    )


def main_keyboard() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Создать подписку VLESS")],
            [types.KeyboardButton(text="📋 Мои подписки")],
            [types.KeyboardButton(text="💰 Баланс")],
        ],
        resize_keyboard=True,
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Бот управления персональными VLESS-подписками через 3X-UI.\n"
        "Выберите действие ниже.",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("balance"))
@dp.message(F.text == "💰 Баланс")
async def cmd_balance(message: types.Message):
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        await session.commit()
        await message.answer(f"Ваш баланс: {user.balance:.2f} ₽")


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
        await message.answer("Использование: /give <user_id> <сумма>")
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
            f"Баланс пользователя {target_user_id} пополнен на {amount:.2f} ₽.\n"
            f"Текущий баланс: {user.balance:.2f} ₽"
        )


@dp.message(F.text == "➕ Создать подписку VLESS")
async def start_creation(message: types.Message, state: FSMContext):
    await state.set_state(TunnelCreation.waiting)
    await message.answer("Подтвердите создание VLESS-подписки стоимостью " f"{TUNNEL_COST:.2f} ₽.\n/cancel — отмена.")


@dp.message(TunnelCreation.waiting)
async def process_creation(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    client_uuid = None
    client_email = None

    async with async_session() as session:
        user = await get_or_create_user(session, user_id)
        if user.balance < TUNNEL_COST:
            await message.answer(
                f"Недостаточно средств. Требуется {TUNNEL_COST:.2f} ₽, "
                f"доступно {user.balance:.2f} ₽."
            )
            await state.clear()
            return

        try:
            port = await get_free_port(session)
            client_uuid, client_email = await create_vless_client(
                user_id, traffic_limit_gb=TRAFFIC_LIMIT_GB
            )
            expires_at = datetime.now() + timedelta(days=30)
            user.balance -= TUNNEL_COST
            tunnel = Tunnel(
                user_id=user_id,
                container_id=client_uuid,
                room_url=client_email,
                port=port,
                is_active=True,
                expires_at=expires_at,
                traffic_limit_bytes=int(TRAFFIC_LIMIT_GB * 1024**3),
                traffic_used_bytes=0,
            )
            session.add(tunnel)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            if client_uuid:
                try:
                    await delete_vless_client(client_uuid)
                except Exception:
                    pass
            await message.answer(
                f"Не удалось создать подписку: {type(exc).__name__}.\n"
                "Средства не списаны."
            )
            await state.clear()
            return

    await state.clear()
    await message.answer(
        "Подписка создана.\n\n"
        f"Срок: {expires_at:%Y-%m-%d %H:%M}\n"
        f"Трафик: {TRAFFIC_LIMIT_GB:g} ГБ\n"
        f"Списано: {TUNNEL_COST:.2f} ₽\n\n"
        f"Ключ подключения:\n{vless_uri(client_uuid, client_email)}"
    )


@dp.message(F.text == "📋 Мои подписки")
async def list_user_tunnels(message: types.Message):
    async with async_session() as session:
        tunnels = (
            await session.scalars(
                select(Tunnel).where(
                    Tunnel.user_id == message.from_user.id,
                    Tunnel.is_active.is_(True),
                )
            )
        ).all()

    if not tunnels:
        await message.answer("Активных подписок нет.")
        return

    for tunnel in tunnels:
        traffic_gb = tunnel.traffic_used_bytes / 1024**3
        limit_gb = tunnel.traffic_limit_bytes / 1024**3
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=f"🔄 Продлить (+30 дней / {TUNNEL_COST:.0f} ₽)",
                    callback_data=f"renew:{tunnel.id}",
                )],
                [types.InlineKeyboardButton(
                    text="🗑 Удалить подписку",
                    callback_data=f"delete:{tunnel.id}",
                )],
            ]
        )
        await message.answer(
            f"VLESS: {tunnel.room_url}\n"
            f"Трафик: {traffic_gb:.2f} / {limit_gb:.2f} ГБ\n"
            f"До: {tunnel.expires_at:%Y-%m-%d %H:%M}\n\n"
            f"Ключ:\n{vless_uri(tunnel.container_id, tunnel.room_url)}",
            reply_markup=keyboard,
        )


@dp.callback_query(F.data.startswith("renew:"))
async def renew_tunnel(callback: types.CallbackQuery):
    try:
        tunnel_id = int(callback.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Некорректный запрос.", show_alert=True)
        return

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == callback.from_user.id))
        tunnel = await session.scalar(
            select(Tunnel).where(
                Tunnel.id == tunnel_id,
                Tunnel.user_id == callback.from_user.id,
                Tunnel.is_active.is_(True),
            )
        )
        if not tunnel:
            await callback.answer("Подписка не найдена.", show_alert=True)
            return
        if not user or user.balance < TUNNEL_COST:
            await callback.answer(
                f"Недостаточно средств. Требуется {TUNNEL_COST:.2f} ₽.",
                show_alert=True,
            )
            return

        try:
            await reset_client_traffic(tunnel.room_url)
            user.balance -= TUNNEL_COST
            tunnel.expires_at = max(tunnel.expires_at, datetime.now()) + timedelta(days=30)
            tunnel.traffic_used_bytes = 0
            await session.commit()
        except Exception:
            await session.rollback()
            await callback.answer("Не удалось продлить подписку.", show_alert=True)
            return

    await callback.answer("Подписка продлена на 30 дней.", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=None)


@dp.callback_query(F.data.startswith("delete:"))
async def delete_tunnel(callback: types.CallbackQuery):
    try:
        tunnel_id = int(callback.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await callback.answer("Некорректный запрос.", show_alert=True)
        return

    async with async_session() as session:
        tunnel = await session.scalar(
            select(Tunnel).where(
                Tunnel.id == tunnel_id,
                Tunnel.user_id == callback.from_user.id,
            )
        )
        if not tunnel or not tunnel.is_active:
            await callback.answer("Подписка не найдена.", show_alert=True)
            return
        try:
            await delete_vless_client(tunnel.container_id)
        except Exception:
            await callback.answer("Не удалось удалить клиента из 3X-UI.", show_alert=True)
            return
        tunnel.is_active = False
        await session.commit()

    await callback.message.edit_text("Подписка удалена.")
    await callback.answer()


@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [types.InlineKeyboardButton(text="🌐 Все подписки", callback_data="admin:list:0")],
            [types.InlineKeyboardButton(text="💰 Пополнение", callback_data="admin:give")],
        ]
    )
    await message.answer("👑 Панель администратора", reply_markup=keyboard)


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    async with async_session() as session:
        users = await session.scalar(select(func.count(User.id)))
        tunnels = await session.scalar(
            select(func.count(Tunnel.id)).where(Tunnel.is_active.is_(True))
        )
    await callback.message.edit_text(
        f"📊 Статистика\n\n"
        f"Пользователей: {users}\n"
        f"Активных подписок: {tunnels}\n"
        f"Inbound ID: {XUI_INBOUND_ID}\n"
        f"Диапазон портов: {PORT_RANGE_START}–{PORT_RANGE_END}\n"
        f"Стоимость: {TUNNEL_COST:.2f} ₽"
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:give")
async def admin_give_help(callback: types.CallbackQuery):
    if callback.from_user.id == ADMIN_ID:
        await callback.message.edit_text("Пополнение: /give <user_id> <сумма>")
    await callback.answer()


@dp.callback_query(F.data.startswith("admin:list:"))
async def admin_list(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    page = max(0, int(callback.data.rsplit(":", 1)[1]))
    per_page = 5
    async with async_session() as session:
        tunnels = (
            await session.scalars(select(Tunnel).where(Tunnel.is_active.is_(True)))
        ).all()

    if not tunnels:
        await callback.message.edit_text("Активных подписок нет.")
        await callback.answer()
        return

    total_pages = (len(tunnels) + per_page - 1) // per_page
    page = min(page, total_pages - 1)
    items = tunnels[page * per_page:(page + 1) * per_page]
    text = f"🌐 Подписки — страница {page + 1}/{total_pages}\n\n"
    for tunnel in items:
        text += (
            f"#{tunnel.id} | user={tunnel.user_id}\n"
            f"{tunnel.room_url} | до {tunnel.expires_at:%Y-%m-%d %H:%M}\n\n"
        )

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"admin:list:{page - 1}"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton(text="➡️", callback_data=f"admin:list:{page + 1}"))
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[nav] if nav else [])
    await callback.message.edit_text(text[:4000], reply_markup=keyboard)
    await callback.answer()


async def background_monitoring():
    async with async_session() as session:
        tunnels = (
            await session.scalars(select(Tunnel).where(Tunnel.is_active.is_(True)))
        ).all()
        if not tunnels:
            return

        try:
            clients = {item["id"]: item for item in await get_inbound_client_stats()}
        except Exception:
            return

        changed = False
        for tunnel in tunnels:
            should_close = datetime.now() >= tunnel.expires_at
            client_data = clients.get(tunnel.container_id)

            if client_data:
                tunnel.traffic_used_bytes = int(client_data.get("up", 0)) + int(client_data.get("down", 0))
                if tunnel.traffic_used_bytes >= tunnel.traffic_limit_bytes:
                    should_close = True
                if not client_data.get("enable", True):
                    should_close = True
            else:
                should_close = True

            if should_close:
                try:
                    await delete_vless_client(tunnel.container_id)
                except Exception:
                    pass
                tunnel.is_active = False
                changed = True
                try:
                    await bot.send_message(
                        tunnel.user_id,
                        f"Подписка {tunnel.room_url} остановлена: срок действия или лимит трафика исчерпан.",
                    )
                except Exception:
                    pass

        if changed:
            await session.commit()


async def main():
    await init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        background_monitoring,
        "interval",
        minutes=5,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
