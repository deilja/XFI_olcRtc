import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения!")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
if not ADMIN_ID:
    raise ValueError("Не задан ADMIN_ID в переменных окружения!")

DB_PATH = os.getenv("DB_PATH", "database.sqlite")
PORT_RANGE_START = int(os.getenv("PORT_RANGE_START", "20000"))
PORT_RANGE_END = int(os.getenv("PORT_RANGE_END", "21000"))
TUNNEL_COST = float(os.getenv("TUNNEL_COST", "150.0"))
SERVER_IP = os.getenv("SERVER_IP", "")
TRAFFIC_LIMIT_GB = float(os.getenv("TRAFFIC_LIMIT_GB", "10"))

XUI_HOST = os.getenv("XUI_HOST", "http://127.0.0.1:2053").rstrip("/")
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD = os.getenv("XUI_PASSWORD", "")
XUI_INBOUND_ID = int(os.getenv("XUI_INBOUND_ID", "1"))
XUI_SERVER_PORT = int(os.getenv("XUI_SERVER_PORT", "443"))
XUI_PUBLIC_KEY = os.getenv("XUI_PUBLIC_KEY", "")
XUI_SHORT_ID = os.getenv("XUI_SHORT_ID", "")
XUI_SNI = os.getenv("XUI_SNI", "yahoo.com")
XUI_FINGERPRINT = os.getenv("XUI_FINGERPRINT", "chrome")
