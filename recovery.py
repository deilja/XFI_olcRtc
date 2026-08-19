import asyncio
from datetime import datetime

from sqlalchemy import select

from database import Tunnel, async_session
from docker_manager import client as docker_client, create_olcrtc_container, stop_container
from xui_manager import create_vless_client_with_identity, delete_vless_client, get_inbound_client_stats


def now() -> datetime:
    return datetime.utcnow()


async def reconcile_state() -> dict[str, int]:
    """Сверяет БД с 3X-UI и Docker и восстанавливает потерянные backend."""
    restored = 0
    deactivated = 0
    failed = 0
    orphaned = 0

    try:
        xui_clients = {x["id"]: x for x in await get_inbound_client_stats()}
    except Exception:
        xui_clients = None

    async with async_session() as session:
        tunnels = (await session.scalars(select(Tunnel).where(Tunnel.is_active.is_(True)))).all()

        for tunnel in tunnels:
            if tunnel.expires_at <= now():
                try:
                    if tunnel.sub_type == "vless":
                        await delete_vless_client(tunnel.backend_id)
                    else:
                        await asyncio.to_thread(stop_container, tunnel.backend_id)
                except Exception:
                    pass
                tunnel.is_active = False
                deactivated += 1
                continue

            if tunnel.sub_type == "vless":
                if xui_clients is None:
                    failed += 1
                    continue
                if tunnel.backend_id in xui_clients:
                    continue
                try:
                    await create_vless_client_with_identity(
                        client_uuid=tunnel.backend_id,
                        email=tunnel.meta_info,
                        traffic_limit_bytes=tunnel.traffic_limit_bytes,
                        expiry=tunnel.expires_at,
                    )
                    restored += 1
                except Exception:
                    failed += 1

            elif tunnel.sub_type == "olcrtc":
                try:
                    await asyncio.to_thread(docker_client.containers.get, tunnel.backend_id)
                    continue
                except Exception:
                    pass
                try:
                    container_id = await asyncio.to_thread(
                        create_olcrtc_container, tunnel.meta_info, tunnel.port, tunnel.user_id
                    )
                    tunnel.backend_id = container_id
                    restored += 1
                except Exception:
                    tunnel.is_active = False
                    deactivated += 1
                    failed += 1

        await session.flush()

        # Формируем актуальный список после восстановления. Иначе только что
        # созданный контейнер ошибочно считался бы orphan и удалялся.
        active_tunnels = (await session.scalars(select(Tunnel).where(Tunnel.is_active.is_(True)))).all()
        active_container_ids = {t.backend_id for t in active_tunnels if t.sub_type == "olcrtc"}
        active_vless_ids = {t.backend_id for t in active_tunnels if t.sub_type == "vless"}

        try:
            containers = await asyncio.to_thread(
                docker_client.containers.list, all=True, filters={"name": "olcrtc_"}
            )
            for container in containers:
                if container.id in active_container_ids:
                    continue
                try:
                    await asyncio.to_thread(container.remove, force=True)
                    orphaned += 1
                except Exception:
                    failed += 1
        except Exception:
            failed += 1

        # Удаляем только XFI-клиентов, которых нет среди активных туннелей.
        if xui_clients is not None:
            for client_data in xui_clients.values():
                email = client_data.get("email") or ""
                client_id = client_data.get("id")
                if not email.startswith("xfi_") or client_id in active_vless_ids:
                    continue
                try:
                    await delete_vless_client(client_id)
                    orphaned += 1
                except Exception:
                    failed += 1

        await session.commit()

    return {
        "restored": restored,
        "deactivated": deactivated,
        "failed": failed,
        "orphaned": orphaned,
    }
