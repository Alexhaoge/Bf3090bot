import psycopg
import redis
from typing import Tuple

def redis_connection_helper():
    return redis.Redis(decode_responses=True)

def db_op(conn: psycopg.Connection, sql: str, params: list):
    cur = conn.cursor()
    res = cur.execute(sql, params).fetchall()
    cur.connection.commit()
    cur.close()
    return res    

def db_op_many(conn: psycopg.Connection, sql: str, params: list):
    cur = conn.cursor()
    cur.executemany(sql, params)
    cur.connection.commit()
    cur.close()

def get_one_random_bf1admin(conn) -> Tuple[str, str, str]:
    return db_op(conn, "SELECT remid, sid, sessionid FROM bf1admins ORDER BY RANDOM() LIMIT 1;", [])[0]

def get_bf1admin_by_serverid(conn: psycopg.Connection, serverid: int):
    pid_r = db_op(conn, "SELECT pid FROM serverbf1admins WHERE serverid=%s LIMIT 1;", [serverid])
    if len(pid_r):
        pid = pid_r[0][0]
    else:
        return None, None, None, None
    return db_op(conn, 'SELECT remid, sid, sessionid, token FROM bf1admins WHERE pid=%s;', [pid])[0]

def get_gameid_from_serverid(redis_client, serverid):
    gameid = redis_client.get(f'gameid:{serverid}')
    if gameid:
        return int(gameid)
    else:
        print(f'gameid for {serverid} not found')
        return None

def batch_get_gameids(redis_client, serverids):
    pipe = redis_client.pipeline()
    
    for serverid in serverids:
        key = f'gameid:{serverid}'
        pipe.get(key)
    
    responses = pipe.execute()
    
    serverid_gameIds = []
    for i in range(len(responses)):
        if responses[i]:
            gameid = int(responses[i])
            serverid_gameIds.append((serverids[i], gameid))
        else:
            continue
        
    return serverid_gameIds

def batch_get_draw_dict(redis_client, gameids):
    pipe = redis_client.pipeline()
    
    for gameId in gameids:
        key = f'draw_dict:{gameId}'
        pipe.hgetall(key)
    
    responses = pipe.execute()
    draw_dict = {}
    for i in range(len(responses)):
        if responses[i]:
            draw_dict[str(gameids[i])] = responses[i]
        else:
            continue
    
    return draw_dict

__all__ = [
    'redis_connection_helper',
    'db_op', 'db_op_many',
    'get_one_random_bf1admin', 'get_bf1admin_by_serverid',
    'get_gameid_from_serverid', 'batch_get_gameids',
    'batch_get_draw_dict'
]