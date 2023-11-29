from redis import asyncio as redis
from .utils import REDIS_URL

redis_pool = redis.ConnectionPool.from_url(REDIS_URL)
redis_client = redis.Redis.from_pool(redis_pool)

# Redis storage description
# 'gameid:{serverid}': {gameid}