import logging
import sys
from logging.handlers import TimedRotatingFileHandler

from nonebot import get_driver, on_command, logger
from nonebot.log import logger_id, default_format
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER

from nonebot_plugin_htmlrender import md_to_pic, html_to_pic

from .rdb import init_db, close_db
from .redis_helper import redis_client, redis_pool
from .bf1rsp import (
    httpx_client, httpx_client_proxy, httpx_client_btr_proxy
)

from .utils import (
    PREFIX, BF1_PLAYERS_DATA, BFV_PLAYERS_DATA, BF2042_PLAYERS_DATA, 
    CODE_FOLDER, ASSETS_FOLDER, LOGGING_FOLDER, main_log_filter, httpx_gt_client
)

from . import bf1helper, bfv, bf2042
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
        LOGGING_FOLDER/'admin.log',
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
    logger.add(LOGGING_FOLDER/"error.log", 
               level="ERROR",
               format=default_format,
               backtrace=True,
               rotation="1 week")
    # DB setup
    await init_db()
    # Bot scheduled jobs initial runs
    await bf1helper.token_helper()
    await bf1helper.session_helper()
    await bf1helper.load_alarm_session_from_db()

@driver.on_shutdown
async def close_on_bot_shutdown():
    await close_db()
    await redis_client.aclose()
    await redis_pool.aclose()
    await httpx_client.aclose()
    await httpx_client_proxy.aclose()
    await httpx_client_btr_proxy.aclose()
    await httpx_gt_client.aclose()


BF_INIT = on_command(f'{PREFIX}bf init', block=True, priority=1, permission=GROUP_OWNER | GROUP_ADMIN | SUPERUSER)
BF_HELP = on_command(f"{PREFIX}bf help", block=True, priority=1)

@BF_INIT.handle()
async def bf_init(event:MessageEvent, state:T_State):
    if isinstance(event,GroupMessageEvent):
        session = event.group_id
        try:
            (BFV_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
            (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
            (BF2042_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
            await BF_INIT.send(f'初始化本群绑定功能成功！\n\n群员使用 {PREFIX}bf1 bind [玩家id] 可绑定战地一账号到本群。\n群员使用 {PREFIX}bfv bind [玩家id] 可绑定战地五账号到本群。\n群员使用 {PREFIX}bf2042 bind [玩家id] 可绑定战地2042账号到本群。（测试中）\n绑定后使用{PREFIX}bf1 me 或 {PREFIX}bfv me 或 {PREFIX}bf2042 me 可查询战绩')
        except FileExistsError:
            await BF_INIT.send(f'本群已初始化绑定功能。\n\n群员使用 {PREFIX}bf1 bind [玩家id] 可绑定战地一账号到本群。\n群员使用 {PREFIX}bfv bind [玩家id] 可绑定战地五账号到本群。\n群员使用 {PREFIX}bf2042 bind [玩家id] 可绑定战地2042账号到本群。（测试中）\n绑定后使用{PREFIX}bf1 me 或 {PREFIX}bfv me 或 {PREFIX}bf2042 me 可查询战绩')

@BF_HELP.handle()
async def bf_help(event:MessageEvent, state:T_State):
    with open(ASSETS_FOLDER/'help.md',encoding='utf-8') as f:
        md_help = f.read()
    
    md_help = md_help.format(p=PREFIX)

    pic = await md_to_pic(md_help, css_path=ASSETS_FOLDER/"github-markdown-dark.css",width=1200)

    await BF_HELP.send(MessageSegment.image(pic))
