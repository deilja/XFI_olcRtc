import json
import time
import uuid
from typing import Any

import httpx

from config import (
    TRAFFIC_LIMIT_GB,
    XUI_HOST,
    XUI_INBOUND_ID,
    XUI_PASSWORD,
    XUI_USERNAME,
)


async def api_request(method: str, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        login = await client.post(
            f"{XUI_HOST}/login",
            data={"username": XUI_USERNAME, "password": XUI_PASSWORD},
        )
        login.raise_for_status()
        login_data = login.json()
        if not login_data.get("success"):
            raise RuntimeError(f"Не удалось авторизоваться в 3X-UI: {login_data.get('msg', 'unknown')}")

        url = f"{XUI_HOST}/panel/api/{endpoint.lstrip('/')}"
        if method.upper() == "POST":
            response = await client.post(url, json=json_data)
        elif method.upper() == "GET":
            response = await client.get(url)
        else:
            raise ValueError(f"Неподдерживаемый HTTP метод: {method}")

        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            raise RuntimeError(f"Ошибка API 3X-UI: {result.get('msg', 'Неизвестная ошибка')}")
        return result


def _limit_bytes() -> int:
    return int(TRAFFIC_LIMIT_GB * 1024**3)


async def create_vless_client(user_id: int, traffic_limit_gb: float | None = None) -> tuple[str, str]:
    client_uuid = str(uuid.uuid4())
    client_email = f"xfi_{user_id}_{int(time.time())}"
    limit_bytes = int((traffic_limit_gb if traffic_limit_gb is not None else TRAFFIC_LIMIT_GB) * 1024**3)

    settings = {
        "clients": [
            {
                "id": client_uuid,
                "alterId": 0,
                "email": client_email,
                "limitIp": 0,
                "totalGB": limit_bytes,
                "expiryTime": 0,
                "enable": True,
                "tgId": str(user_id),
                "flow": "xtls-rprx-vision",
            }
        ]
    }
    await api_request(
        "POST",
        "inbounds/addClient",
        {"id": XUI_INBOUND_ID, "settings": json.dumps(settings)},
    )
    return client_uuid, client_email


async def delete_vless_client(client_uuid: str) -> None:
    await api_request("POST", f"inbounds/{XUI_INBOUND_ID}/delClient/{client_uuid}")


async def reset_client_traffic(client_email: str) -> None:
    await api_request("POST", f"inbounds/{XUI_INBOUND_ID}/resetClientTraffic/{client_email}")


async def get_inbound_client_stats() -> list[dict[str, Any]]:
    result = await api_request("GET", f"inbounds/get/{XUI_INBOUND_ID}")
    obj = result.get("obj") or {}

    settings_raw = obj.get("settings", "{}")
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
    clients = settings.get("clients", []) if isinstance(settings, dict) else []

    stats = obj.get("clientStats") or []
    stats_by_email = {item.get("email"): item for item in stats}

    return [
        {
            "email": client.get("email"),
            "id": client.get("id"),
            "enable": client.get("enable", True),
            "up": int(stats_by_email.get(client.get("email"), {}).get("up", 0)),
            "down": int(stats_by_email.get(client.get("email"), {}).get("down", 0)),
            "total": int(stats_by_email.get(client.get("email"), {}).get("total", 0)),
        }
        for client in clients
    ]
