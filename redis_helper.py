from redis import asyncio as redis
from .utils import REDIS_URL

redis_pool = redis.ConnectionPool.from_url(REDIS_URL, charset="utf-8", decode_responses=True)
redis_client = redis.Redis.from_pool(redis_pool)

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