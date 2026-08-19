import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "database.sqlite")
PORT_RANGE_START = int(os.getenv("PORT_RANGE_START", "20000"))
PORT_RANGE_END = int(os.getenv("PORT_RANGE_END", "21000"))
TUNNEL_COST = float(os.getenv("TUNNEL_COST", "150.0"))
TRAFFIC_LIMIT_GB = float(os.getenv("TRAFFIC_LIMIT_GB", "10"))
SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))
SERVER_IP = os.getenv("SERVER_IP", "").strip()

XUI_HOST = os.getenv("XUI_HOST", "http://127.0.0.1:2053").rstrip("/")
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD = os.getenv("XUI_PASSWORD", "")
XUI_INBOUND_ID = int(os.getenv("XUI_INBOUND_ID", "1"))
XUI_SERVER_PORT = int(os.getenv("XUI_SERVER_PORT", "443"))
XUI_PUBLIC_KEY = os.getenv("XUI_PUBLIC_KEY", "").strip()
XUI_SHORT_ID = os.getenv("XUI_SHORT_ID", "").strip()
XUI_SNI = os.getenv("XUI_SNI", "yahoo.com").strip()
XUI_FINGERPRINT = os.getenv("XUI_FINGERPRINT", "chrome").strip()
OLCRTC_IMAGE = os.getenv("OLCRTC_IMAGE", "olcrtc/srv:latest").strip()

if PORT_RANGE_START > PORT_RANGE_END:
    raise ValueError("PORT_RANGE_START не может быть больше PORT_RANGE_END")
if TUNNEL_COST < 0:
    raise ValueError("TUNNEL_COST не может быть отрицательным")
if TRAFFIC_LIMIT_GB <= 0:
    raise ValueError("TRAFFIC_LIMIT_GB должен быть больше нуля")
if SUBSCRIPTION_DAYS <= 0:
    raise ValueError("SUBSCRIPTION_DAYS должен быть больше нуля")
