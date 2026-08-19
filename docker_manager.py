import secrets
from pathlib import Path

import docker

from config import CONTAINER_PREFIX, OLCRTC_IMAGE

client = docker.from_env()
CONFIG_ROOT = Path("/var/lib/xfi-olcrtc")


def _config_path(name: str) -> Path:
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    path = CONFIG_ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    return path / "server.yaml"


def create_container(room_url: str, port: int, user_id: int) -> str:
    name = f"{CONTAINER_PREFIX}{user_id}_{port}"
    config_path = _config_path(name)
    config_path.write_text(
        f'''mode: srv\nauth:\n  provider: jitsi\nroom:\n  id: "{room_url}"\ncrypto:\n  key: "{secrets.token_hex(32)}"\nnet:\n  transport: datachannel\n  dns: "8.8.8.8:53"\ndata: data\n''',
        encoding="utf-8",
    )
    try:
        container = client.containers.run(
            OLCRTC_IMAGE,
            command=["server.yaml"],
            name=name,
            detach=True,
            ports={f"{port}/tcp": port, f"{port}/udp": port},
            volumes={str(config_path): {"bind": "/opt/olcrtc/server.yaml", "mode": "ro"}},
            labels={"app": "xfi-olcrtc", "user_id": str(user_id), "port": str(port)},
            restart_policy={"Name": "unless-stopped"},
        )
        return container.id
    except Exception:
        try:
            config_path.unlink(missing_ok=True)
            config_path.parent.rmdir()
        except OSError:
            pass
        raise


def stop_container(container_id: str) -> None:
    container = None
    try:
        container = client.containers.get(container_id)
        container.stop(timeout=10)
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass
            try:
                config_dir = CONFIG_ROOT / container.name
                config_dir.rmdir()
            except OSError:
                pass
