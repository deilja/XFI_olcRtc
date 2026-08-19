import docker

from config import CONTAINER_PREFIX, OLCRTC_IMAGE

client = docker.from_env()


def create_container(room_url: str, port: int, user_id: int) -> str:
    name = f"{CONTAINER_PREFIX}{user_id}_{port}"
    config = f'''mode: srv
auth:
  provider: jitsi
room:
  id: "{room_url}"
crypto:
  key: "{__import__('secrets').token_hex(32)}"
net:
  transport: datachannel
  dns: "8.8.8.8:53"
data: data
'''

    container = client.containers.run(
        OLCRTC_IMAGE,
        command=["server.yaml"],
        name=name,
        detach=True,
        ports={f"{port}/tcp": port, f"{port}/udp": port},
        environment={"OLCRTC_CONFIG": config},
        labels={"app": "xfi-olcrtc", "user_id": str(user_id), "port": str(port)},
        restart_policy={"Name": "unless-stopped"},
    )
    return container.id


def stop_container(container_id: str) -> None:
    try:
        container = client.containers.get(container_id)
        container.stop(timeout=10)
    finally:
        try:
            container.remove(force=True)
        except Exception:
            pass
