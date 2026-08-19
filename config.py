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
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin").strip()
XUI_PASSWORD = os.getenv("XUI_PASSWORD", "").strip()
XUI_INBOUND_ID = int(os.getenv("XUI_INBOUND_ID", "1"))
XUI_SERVER_PORT = int(os.getenv("XUI_SERVER_PORT", "443"))
XUI_PUBLIC_KEY = os.getenv("XUI_PUBLIC_KEY", "").strip()
XUI_SHORT_ID = os.getenv("XUI_SHORT_ID", "").strip()
XUI_SNI = os.getenv("XUI_SNI", "yahoo.com").strip()
XUI_FINGERPRINT = os.getenv("XUI_FINGERPRINT", "chrome").strip()
OLCRTC_IMAGE = os.getenv("OLCRTC_IMAGE", "olcrtc/srv:latest").strip()

if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token_here":
    raise ValueError("Не задан BOT_TOKEN в .env")
if ADMIN_ID <= 0:
    raise ValueError("ADMIN_ID должен быть положительным Telegram user ID")
if not SERVER_IP or SERVER_IP == "your_public_ip_or_domain":
    raise ValueError("Не задан SERVER_IP в .env")
if not XUI_PASSWORD or XUI_PASSWORD == "your_secure_password":
    raise ValueError("Не задан XUI_PASSWORD в .env")
if not XUI_PUBLIC_KEY or XUI_PUBLIC_KEY == "your_reality_public_key":
    raise ValueError("Не задан XUI_PUBLIC_KEY в .env")
if not XUI_SHORT_ID or XUI_SHORT_ID == "your_reality_short_id":
    raise ValueError("Не задан XUI_SHORT_ID в .env")
if PORT_RANGE_START >= PORT_RANGE_END:
    raise ValueError("PORT_RANGE_START должен быть меньше PORT_RANGE_END")
if TUNNEL_COST < 0:
    raise ValueError("TUNNEL_COST не может быть отрицательным")
if TRAFFIC_LIMIT_GB <= 0:
    raise ValueError("TRAFFIC_LIMIT_GB должен быть больше нуля")
if SUBSCRIPTION_DAYS <= 0:
    raise ValueError("SUBSCRIPTION_DAYS должен быть больше нуля")
if not 1 <= XUI_SERVER_PORT <= 65535:
    raise ValueError("XUI_SERVER_PORT должен быть в диапазоне 1..65535")
