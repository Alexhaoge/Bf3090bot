from redis import asyncio as redis
from redis.exceptions import ResponseError
from .utils import REDIS_URL

redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
redis_client = redis.Redis(connection_pool=redis_pool, decode_responses=True)

async def registrate_consumer_group(redis_client, group_name):
    try:
        await redis_client.xgroup_create('alarmstream', group_name, '$', mkstream=True)
        await redis_client.xgroup_create('vbanstream', group_name, '$', mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP Consumer Group name already exists" not in str(e):
            raise e

############## Redis storage description ################

# 'gameid:{serverid}': {gameid}

# 'pl:{groupqq}': {reply_message_id(event)}

# (set) 'alarmsession': [serverids]  

# (hash) 'alarmamount{groupqq}': {server_inds: alarm amounts within 15 mins}

# 'pstats:{pid}': {'win': , 'loss': , 'acc': , 'hs': , 'kd': , 'k': , 'kpm': , 'spm': , 'secondsPlayed': }

# 'draw_dict:str(gameid)': {
#     "server_name": server["name"],
#     "serverMax":server["slots"]["Soldier"]["max"],
#     "serverAmount": server["slots"]["Soldier"]["current"],
#     "map": server["mapName"]
# }

# 'alarmstream' Stream for alarms
# 'vbanstream' Stream for vbans
# Each nonebot backend instance has its own consumer group for both initialized at startup
# with the group name cg{NONEBOT_PORT}