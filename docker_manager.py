import asyncio
import socket

import docker
from sqlalchemy import select

from config import OLCRTC_IMAGE, PORT_RANGE_END, PORT_RANGE_START
from database import Tunnel

client = docker.from_env()


async def get_free_port(session) -> int:
    used = set((await session.scalars(select(Tunnel.port).where(Tunnel.is_active.is_(True)))).all())
    for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        if port in used:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
            except OSError:
                continue
        return port
    raise RuntimeError("Нет свободного TCP-порта в заданном диапазоне")


def docker_health() -> tuple[bool, int]:
    client.ping()
    count = len(client.containers.list(filters={"name": "olcrtc_"}))
    return True, count


def create_olcrtc_container(room_url: str, port: int, user_id: int) -> str:
    name = f"olcrtc_{user_id}_{port}"
    try:
        old = client.containers.get(name)
        old.remove(force=True)
    except docker.errors.NotFound:
        pass
    container = client.containers.run(
        OLCRTC_IMAGE,
        detach=True,
        restart_policy={"Name": "unless-stopped"},
        ports={f"{port}/tcp": port},
        environment={"ROOM_URL": room_url, "PORT": str(port)},
        name=name,
    )
    return container.id


def stop_container(container_id: str) -> None:
    try:
        client.containers.get(container_id).remove(force=True)
    except docker.errors.NotFound:
        pass


def container_traffic(container_id: str) -> int:
    stats = client.containers.get(container_id).stats(stream=False)
    total = 0
    for item in (stats.get("networks") or {}).values():
        total += int(item.get("rx_bytes", 0)) + int(item.get("tx_bytes", 0))
    return total
