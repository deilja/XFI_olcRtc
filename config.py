import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "database.sqlite")
PORT_RANGE_START = int(os.getenv("PORT_RANGE_START", "20000"))
PORT_RANGE_END = int(os.getenv("PORT_RANGE_END", "21000"))
TUNNEL_COST = float(os.getenv("TUNNEL_COST", "150"))
SERVER_IP = os.getenv("SERVER_IP", "")
TRAFFIC_LIMIT_GB = float(os.getenv("TRAFFIC_LIMIT_GB", "100"))
OLCRTC_IMAGE = os.getenv("OLCRTC_IMAGE", "openlibrecommunity/olcrtc:latest")
CONTAINER_PREFIX = os.getenv("CONTAINER_PREFIX", "olcrtc_")
