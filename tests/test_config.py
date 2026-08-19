import os
import subprocess
import sys


def test_config_defaults_load_without_secrets():
    env = os.environ.copy()
    env.pop("BOT_TOKEN", None)
    env.pop("ADMIN_ID", None)
    env.pop("SERVER_IP", None)
    code = "import config; assert config.PORT_RANGE_START == 20000; assert config.PORT_RANGE_END == 21000"
    subprocess.run([sys.executable, "-c", code], env=env, check=True)


def test_config_accepts_environment_values():
    env = os.environ.copy()
    env.update({"PORT_RANGE_START": "30000", "PORT_RANGE_END": "30100", "TUNNEL_COST": "25"})
    code = "import config; assert config.PORT_RANGE_START == 30000; assert config.PORT_RANGE_END == 30100; assert config.TUNNEL_COST == 25.0"
    subprocess.run([sys.executable, "-c", code], env=env, check=True)
