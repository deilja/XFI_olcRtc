import docker
from config import PORT_RANGE_START, PORT_RANGE_END
from sqlalchemy import select
from database import Tunnel

client = docker.from_env()


async def get_free_port(session):
    result = await session.execute(select(Tunnel.port))
    used_ports = {row[0] for row in result.all() if row[0] is not None}

    for port in range(PORT_RANGE_START, PORT_RANGE_END):
        if port not in used_ports:
            return port
    raise RuntimeError("Нет свободных портов в заданном диапазоне!")


def create_olcrtc_container(room_url: str, port: int, user_id: int) -> str:
    """Создаёт контейнер olcRTC и возвращает его Docker container ID."""
    container_name = f"olcrtc_{user_id}_{port}"

    try:
        old = client.containers.get(container_name)
        if old.status == "running":
            raise RuntimeError(f"Контейнер {container_name} уже запущен")
        old.remove(force=True)
    except docker.errors.NotFound:
        pass

    container = client.containers.run(
        image="olcrtc/srv:latest",
        detach=True,
        restart_policy={"Name": "unless-stopped"},
        ports={f"{port}/tcp": port},
        environment={"ROOM_URL": room_url, "PORT": str(port)},
        name=container_name,
    )
    return container.id


def stop_container(container_id: str) -> None:
    """Останавливает и удаляет контейнер olcRTC."""
    try:
        container = client.containers.get(container_id)
        container.remove(force=True)
    except docker.errors.NotFound:
        pass
    except Exception as exc:
        print(f"Ошибка удаления контейнера {container_id}: {exc}")
