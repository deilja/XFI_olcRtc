import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from config import (
    TRAFFIC_LIMIT_GB, XUI_HOST, XUI_INBOUND_ID, XUI_PASSWORD, XUI_USERNAME,
)


async def api_request(method: str, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        login = await client.post(f"{XUI_HOST}/login", data={"username": XUI_USERNAME, "password": XUI_PASSWORD})
        login.raise_for_status()
        data = login.json()
        if not data.get("success"):
            raise RuntimeError(f"3X-UI авторизация: {data.get('msg', 'ошибка')}")
        url = f"{XUI_HOST}/panel/api/{endpoint.lstrip('/')}"
        response = await client.request(method.upper(), url, json=json_data)
        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            raise RuntimeError(f"3X-UI API: {result.get('msg', 'ошибка')}")
        return result


def _bytes(gb: float) -> int:
    return int(gb * 1024**3)


async def check_xui_health() -> bool:
    try:
        await api_request("GET", f"inbounds/get/{XUI_INBOUND_ID}")
        return True
    except Exception:
        return False


async def create_vless_client(user_id: int, traffic_limit_gb: float | None = None, expiry: datetime | None = None) -> tuple[str, str]:
    client_uuid = str(uuid.uuid4())
    email = f"xfi_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    limit = _bytes(traffic_limit_gb if traffic_limit_gb is not None else TRAFFIC_LIMIT_GB)
    expiry_ms = 0 if expiry is None else int(expiry.replace(tzinfo=timezone.utc).timestamp() * 1000)
    settings = {"clients": [{
        "id": client_uuid, "alterId": 0, "email": email, "limitIp": 0,
        "totalGB": limit, "expiryTime": expiry_ms, "enable": True,
        "tgId": str(user_id), "flow": "xtls-rprx-vision",
    }]}
    await api_request("POST", "inbounds/addClient", {"id": XUI_INBOUND_ID, "settings": json.dumps(settings)})
    return client_uuid, email


async def update_vless_client(client_uuid: str, email: str, expiry: datetime, traffic_limit_gb: float | None = None) -> None:
    limit = _bytes(traffic_limit_gb if traffic_limit_gb is not None else TRAFFIC_LIMIT_GB)
    expiry_ms = int(expiry.replace(tzinfo=timezone.utc).timestamp() * 1000)
    settings = json.dumps({
        "clients": [{
            "id": client_uuid, "alterId": 0, "email": email, "limitIp": 0,
            "totalGB": limit, "expiryTime": expiry_ms, "enable": True,
            "flow": "xtls-rprx-vision",
        }]
    })
    await api_request("POST", f"inbounds/updateClient/{client_uuid}", {"id": XUI_INBOUND_ID, "settings": settings})


async def delete_vless_client(client_uuid: str) -> None:
    await api_request("POST", f"inbounds/{XUI_INBOUND_ID}/delClient/{client_uuid}")


async def reset_client_traffic(email: str) -> None:
    await api_request("POST", f"inbounds/{XUI_INBOUND_ID}/resetClientTraffic/{email}")


async def get_inbound_client_stats() -> list[dict[str, Any]]:
    result = await api_request("GET", f"inbounds/get/{XUI_INBOUND_ID}")
    obj = result.get("obj") or {}
    raw = obj.get("settings", "{}")
    settings = json.loads(raw) if isinstance(raw, str) else raw
    clients = settings.get("clients", []) if isinstance(settings, dict) else []
    stats = {x.get("email"): x for x in (obj.get("clientStats") or [])}
    return [{
        "email": c.get("email"), "id": c.get("id"), "enable": c.get("enable", True),
        "up": int(stats.get(c.get("email"), {}).get("up", 0)),
        "down": int(stats.get(c.get("email"), {}).get("down", 0)),
        "total": int(stats.get(c.get("email"), {}).get("total", 0)),
    } for c in clients]
