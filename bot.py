import nonebot
import argparse
from nonebot.config import Config
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter

parser = argparse.ArgumentParser(prog='bf3090bot', description='Entrance file to launch bf3090bot')
parser.add_argument('-p', '--port', default=16000, type=int)  

args = parser.parse_args()

nonebot.init(port=args.port, _env_file=".env.prod")

driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)

nonebot.load_from_toml("pyproject.toml")

if __name__ == "__main__":
    nonebot.run()