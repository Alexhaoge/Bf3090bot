import logging
import sys
from logging.handlers import TimedRotatingFileHandler

from nonebot import get_driver, on_command, logger
from nonebot.log import logger_id, default_format
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER

from nonebot_plugin_htmlrender import md_to_pic, html_to_pic

from .rdb import init_db, close_db
from .redis_helper import redis_client, redis_pool, registrate_consumer_group
from .bf1rsp import (
    httpx_client, httpx_client_proxy, httpx_client_btr_proxy
)

from .utils import (
    PREFIX, NONEBOT_PORT, BF1_PLAYERS_DATA, 
    CODE_FOLDER, ASSETS_FOLDER, LOGGING_FOLDER, main_log_filter, httpx_gt_client
)

from .bf1core import matcher

################ Global Bot Hooks ##################
driver = get_driver()

# Write all the bot initialization tasks here
@driver.on_startup
async def init_on_bot_startup():
    # Logging config
    LOGGING_FOLDER.mkdir(exist_ok=True)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
    ## Setup bf1 server admin logger
    admin_logger = logging.getLogger('adminlog')
    admin_logger.setLevel(logging.INFO)
    admin_logger_handler = TimedRotatingFileHandler(
        LOGGING_FOLDER/f'admin_{NONEBOT_PORT}.log',
        when='D', interval=3, backupCount=150
    )
    admin_logger_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    admin_logger.addHandler(admin_logger_handler)
    ## Suppress logging on plugin basis
    logger.remove(logger_id)
    logger.add(sys.stdout, level=0, diagnose=True, format=default_format, filter=main_log_filter)
    ## Redirect error to log file for better tracing
    logger.add(LOGGING_FOLDER/f"error_{NONEBOT_PORT}.log", 
               level="ERROR",
               format=default_format,
               backtrace=True,
               rotation="1 week")
    # DB setup
    await init_db()
    await registrate_consumer_group(redis_client, f'cg{NONEBOT_PORT}')

@driver.on_shutdown
async def close_on_bot_shutdown():
    await close_db()
    await redis_client.aclose()
    await redis_pool.aclose()
    await httpx_client.aclose()
    await httpx_client_proxy.aclose()
    await httpx_client_btr_proxy.aclose()
    await httpx_gt_client.aclose()

