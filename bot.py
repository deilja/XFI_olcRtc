import asyncio
from datetime import datetime, timedelta
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from config import (
    ADMIN_ID, BOT_TOKEN, PORT_RANGE_END, PORT_RANGE_START, SERVER_IP,
    SUBSCRIPTION_DAYS, TRAFFIC_LIMIT_GB, TUNNEL_COST, XUI_FINGERPRINT,
    XUI_PUBLIC_KEY, XUI_SERVER_PORT, XUI_SHORT_ID, XUI_SNI,
)
from database import (
    BalanceTransaction, Tunnel, User, async_session, charge_balance,
    credit_balance, get_or_create_user, init_db,
)
from docker_manager import (
    client as docker_client, container_traffic, create_olcrtc_container,
    docker_health, stop_container,
)
from docker_manager import get_free_port as docker_free_port
from recovery import reconcile_state
from xui_manager import (
    check_xui_health, create_vless_client, delete_vless_client,
    get_inbound_client_stats, reset_client_traffic, update_vless_client,
)

if not BOT_TOKEN or not ADMIN_ID or not SERVER_IP:
    raise RuntimeError("Заполните BOT_TOKEN, ADMIN_ID и SERVER_IP в .env")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
_user_locks: dict[int, asyncio.Lock] = {}


class OlcRtcCreation(StatesGroup):
    waiting_for_room_url = State()


def user_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = _user_locks[user_id] = asyncio.Lock()
    return lock


def now() -> datetime:
    return datetime.utcnow()


def vless_uri(client_uuid: str, email: str) -> str:
    if not XUI_PUBLIC_KEY or not XUI_SHORT_ID:
        raise RuntimeError("Не заданы XUI_PUBLIC_KEY и XUI_SHORT_ID")
    return (
        f"vless://{client_uuid}@{SERVER_IP}:{XUI_SERVER_PORT}"
        f"?encryption=none&flow=xtls-rprx-vision&security=reality"
        f"&sni={quote(XUI_SNI, safe='')}&fp={quote(XUI_FINGERPRINT, safe='')}"
        f"&pbk={quote(XUI_PUBLIC_KEY, safe='')}&sid={quote(XUI_SHORT_ID, safe='')}"
        f"&type=tcp&headerType=none#{quote(email, safe='')}"
    )


def main_keyboard():
    return types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="➕ Создать VLESS"), types.KeyboardButton(text="📞 Создать olcRTC")],
        [types.KeyboardButton(text="📋 Мои подписки"), types.KeyboardButton(text="💰 Баланс")],
    ], resize_keyboard=True)


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("XFI_olcRTC: управление VLESS и olcRTC.", reply_markup=main_keyboard())


@dp.message(Command("balance"))
@dp.message(F.text == "💰 Баланс")
async def balance(message: types.Message):
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        await session.commit()
        await message.answer(f"Баланс: {user.balance:.2f} ₽")


@dp.message(Command("cancel"))
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Операция отменена.", reply_markup=main_keyboard())


@dp.message(Command("give"))
async def give(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = (message.text or "").split()
    if len(args) != 3:
        await message.answer("Использование: /give <user_id> <сумма>")
        return
    try:
        uid, amount = int(args[1]), float(args[2])
    except ValueError:
        await message.answer("Некорректные user_id или сумма.")
        return
    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return
    async with user_lock(uid):
        async with async_session() as session:
            new_balance = await credit_balance(session, uid, amount, "admin_credit", f"Админ {ADMIN_ID}")
            await session.commit()
    await message.answer(f"Баланс {uid}: {new_balance:.2f} ₽")


@dp.message(F.text == "➕ Создать VLESS")
async def create_vless(message: types.Message):
    user_id = message.from_user.id
    client_uuid = None
    async with user_lock(user_id):
        try:
            async with async_session() as session:
                user = await get_or_create_user(session, user_id)
                if user.balance < TUNNEL_COST:
                    await message.answer(f"Недостаточно средств: нужно {TUNNEL_COST:.2f} ₽, доступно {user.balance:.2f} ₽")
                    return
                expiry = now() + timedelta(days=SUBSCRIPTION_DAYS)
                client_uuid, email = await create_vless_client(user_id, TRAFFIC_LIMIT_GB, expiry)
                await charge_balance(session, user_id, TUNNEL_COST, "vless_create", f"VLESS {email}")
                session.add(Tunnel(
                    user_id=user_id, sub_type="vless", backend_id=client_uuid,
                    meta_info=email, port=0, is_active=True, expires_at=expiry,
                    traffic_limit_bytes=int(TRAFFIC_LIMIT_GB * 1024**3), traffic_used_bytes=0,
                ))
                await session.commit()
        except Exception as exc:
            if client_uuid:
                try:
                    await delete_vless_client(client_uuid)
                except Exception:
                    pass
            await message.answer(f"Ошибка создания VLESS: {type(exc).__name__}. Средства не списаны.")
            return
    await message.answer(f"VLESS создан.\nДо: {expiry:%Y-%m-%d %H:%M} UTC\nТрафик: {TRAFFIC_LIMIT_GB:g} ГБ\nСписано: {TUNNEL_COST:.2f} ₽\n\n{vless_uri(client_uuid, email)}")


@dp.message(F.text == "📞 Создать olcRTC")
async def start_olcrtc(message: types.Message, state: FSMContext):
    await state.set_state(OlcRtcCreation.waiting_for_room_url)
    await message.answer("Отправьте URL комнаты (http:// или https://). /cancel — отмена.")


@dp.message(OlcRtcCreation.waiting_for_room_url)
async def create_olcrtc(message: types.Message, state: FSMContext):
    room_url = (message.text or "").strip()
    if not (room_url.startswith("http://") or room_url.startswith("https://")):
        await message.answer("Нужна корректная ссылка http:// или https://")
        return
    user_id = message.from_user.id
    container_id = None
    async with user_lock(user_id):
        async with async_session() as session:
            try:
                user = await get_or_create_user(session, user_id)
                if user.balance < TUNNEL_COST:
                    await message.answer(f"Недостаточно средств: нужно {TUNNEL_COST:.2f} ₽")
                    await state.clear(); return
                port = await docker_free_port(session)
                container_id = await asyncio.to_thread(create_olcrtc_container, room_url, port, user_id)
                expiry = now() + timedelta(days=SUBSCRIPTION_DAYS)
                await charge_balance(session, user_id, TUNNEL_COST, "olcrtc_create", f"olcRTC {port}")
                session.add(Tunnel(
                    user_id=user_id, sub_type="olcrtc", backend_id=container_id,
                    meta_info=room_url, port=port, is_active=True, expires_at=expiry,
                    traffic_limit_bytes=int(TRAFFIC_LIMIT_GB * 1024**3), traffic_used_bytes=0,
                ))
                await session.commit()
            except Exception as exc:
                await session.rollback()
                if container_id:
                    await asyncio.to_thread(stop_container, container_id)
                await message.answer(f"Ошибка запуска olcRTC: {type(exc).__name__}. Средства не списаны.")
                await state.clear(); return
    await state.clear()
    await message.answer(f"olcRTC создан.\nПорт: {port}\nДо: {expiry:%Y-%m-%d %H:%M} UTC\n\nolcrtc://{SERVER_IP}:{port}?room={quote(room_url, safe='')}")


@dp.message(F.text == "📋 Мои подписки")
async def subscriptions(message: types.Message):
    async with async_session() as session:
        tunnels = (await session.scalars(select(Tunnel).where(Tunnel.user_id == message.from_user.id, Tunnel.is_active.is_(True)))).all()
    if not tunnels:
        await message.answer("Активных подписок нет."); return
    for t in tunnels:
        limit = t.traffic_limit_bytes / 1024**3
        used = t.traffic_used_bytes / 1024**3
        key = vless_uri(t.backend_id, t.meta_info) if t.sub_type == "vless" else f"olcrtc://{SERVER_IP}:{t.port}?room={quote(t.meta_info, safe='')}"
        title = "🌐 VLESS" if t.sub_type == "vless" else "📞 olcRTC"
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"🔄 Продлить {TUNNEL_COST:.0f} ₽", callback_data=f"renew:{t.id}")],
            [types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{t.id}")],
        ])
        await message.answer(f"{title}\nТрафик: {used:.2f}/{limit:.2f} ГБ\nДо: {t.expires_at:%Y-%m-%d %H:%M} UTC\n\n{key}", reply_markup=kb)


@dp.callback_query(F.data.startswith("delete:"))
async def delete_subscription(callback: types.CallbackQuery):
    tid = int(callback.data.split(":", 1)[1])
    async with user_lock(callback.from_user.id):
        async with async_session() as session:
            t = await session.scalar(select(Tunnel).where(Tunnel.id == tid, Tunnel.user_id == callback.from_user.id, Tunnel.is_active.is_(True)))
            if not t:
                await callback.answer("Подписка не найдена", show_alert=True); return
            try:
                if t.sub_type == "vless": await delete_vless_client(t.backend_id)
                else: await asyncio.to_thread(stop_container, t.backend_id)
            except Exception:
                await callback.answer("Backend не удалось удалить", show_alert=True); return
            t.is_active = False
            await session.commit()
    await callback.message.edit_text("Подписка удалена."); await callback.answer()


@dp.callback_query(F.data.startswith("renew:"))
async def renew(callback: types.CallbackQuery):
    tid = int(callback.data.split(":", 1)[1])
    async with user_lock(callback.from_user.id):
        async with async_session() as session:
            user = await session.scalar(select(User).where(User.id == callback.from_user.id))
            t = await session.scalar(select(Tunnel).where(Tunnel.id == tid, Tunnel.user_id == callback.from_user.id, Tunnel.is_active.is_(True)))
            if not t or not user:
                await callback.answer("Подписка не найдена", show_alert=True); return
            if user.balance < TUNNEL_COST:
                await callback.answer(f"Нужно {TUNNEL_COST:.2f} ₽", show_alert=True); return
            new_expiry = max(t.expires_at, now()) + timedelta(days=SUBSCRIPTION_DAYS)
            try:
                if t.sub_type == "vless":
                    await reset_client_traffic(t.meta_info)
                    await update_vless_client(t.backend_id, t.meta_info, new_expiry, TRAFFIC_LIMIT_GB)
                else:
                    await asyncio.to_thread(docker_client.containers.get, t.backend_id)
                await charge_balance(session, callback.from_user.id, TUNNEL_COST, "subscription_renew", f"Tunnel {t.id}")
                t.expires_at = new_expiry
                t.traffic_used_bytes = 0
                await session.commit()
            except Exception as exc:
                await session.rollback()
                await callback.answer(f"Продление не выполнено: {type(exc).__name__}", show_alert=True); return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Продлено на 30 дней", show_alert=True)


@dp.message(Command("admin"))
async def admin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    async with async_session() as session:
        users = await session.scalar(select(func.count(User.id)))
        vless = await session.scalar(select(func.count(Tunnel.id)).where(Tunnel.is_active.is_(True), Tunnel.sub_type == "vless"))
        rtc = await session.scalar(select(func.count(Tunnel.id)).where(Tunnel.is_active.is_(True), Tunnel.sub_type == "olcrtc"))
        revenue = await session.scalar(select(func.coalesce(func.sum(-BalanceTransaction.amount), 0)).where(BalanceTransaction.amount < 0))
        tx_count = await session.scalar(select(func.count(BalanceTransaction.id)))
    xui = await check_xui_health()
    try: _, dc = await asyncio.to_thread(docker_health)
    except Exception: dc = -1
    await message.answer(f"👑 XFI_olcRTC\n\nПользователей: {users}\nVLESS: {vless}\nolcRTC: {rtc}\nОпераций баланса: {tx_count}\nСписано всего: {float(revenue or 0):.2f} ₽\n3X-UI: {'🟢' if xui else '🔴'}\nDocker: {'🟢' if dc >= 0 else '🔴'} ({max(dc,0)})\nПорты: {PORT_RANGE_START}-{PORT_RANGE_END}")


@dp.message(Command("transactions"))
async def transactions(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    async with async_session() as session:
        rows = (await session.scalars(select(BalanceTransaction).order_by(BalanceTransaction.id.desc()).limit(20))).all()
    if not rows:
        await message.answer("Операций нет."); return
    text = "📒 Последние операции:\n\n" + "\n".join(
        f"#{r.id} user={r.user_id} {'+' if r.amount >= 0 else ''}{r.amount:.2f} ₽ | {r.kind} | {r.created_at:%Y-%m-%d %H:%M}"
        for r in rows
    )
    await message.answer(text[:4000])


async def monitoring():
    try: xui_clients = {x["id"]: x for x in await get_inbound_client_stats()}
    except Exception: xui_clients = None
    async with async_session() as session:
        tunnels = (await session.scalars(select(Tunnel).where(Tunnel.is_active.is_(True)))).all()
        changed = False
        for t in tunnels:
            close = now() >= t.expires_at; reason = "истёк срок"
            if t.sub_type == "vless":
                if xui_clients is None: continue
                c = xui_clients.get(t.backend_id)
                if not c: close, reason = True, "клиент отсутствует в 3X-UI"
                else:
                    t.traffic_used_bytes = int(c.get("up", 0)) + int(c.get("down", 0))
                    if t.traffic_used_bytes >= t.traffic_limit_bytes: close, reason = True, "лимит трафика"
                    elif not c.get("enable", True): close, reason = True, "клиент отключён"
            else:
                try:
                    t.traffic_used_bytes = await asyncio.to_thread(container_traffic, t.backend_id)
                    if t.traffic_used_bytes >= t.traffic_limit_bytes: close, reason = True, "лимит трафика"
                except Exception: close, reason = True, "контейнер отсутствует"
            if close:
                try:
                    if t.sub_type == "vless": await delete_vless_client(t.backend_id)
                    else: await asyncio.to_thread(stop_container, t.backend_id)
                except Exception: pass
                t.is_active = False; changed = True
                try: await bot.send_message(t.user_id, f"Подписка {t.meta_info} остановлена: {reason}.")
                except Exception: pass
        if changed: await session.commit()


async def main():
    await init_db()
    try:
        recovery = await reconcile_state()
        print(
            "[Recovery] restored=%s deactivated=%s failed=%s",
            recovery["restored"], recovery["deactivated"], recovery["failed"],
        )
        if recovery["failed"]:
            print("[Recovery] Часть туннелей не удалось восстановить; они будут повторно проверены мониторингом.")
    except Exception as exc:
        print(f"[Recovery] Ошибка синхронизации backend: {type(exc).__name__}: {exc}")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(monitoring, "interval", minutes=5, max_instances=1, coalesce=True)
    scheduler.add_job(reconcile_state, "interval", minutes=5, max_instances=1, coalesce=True)
    scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
