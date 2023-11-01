import json,asyncio,datetime
import requests,httpx
import sqlite3
import redis
import uuid,time,os,re
from pathlib import Path
from typing import *
from PIL import Image
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BFCHAT_DATA_FOLDER = Path('../bfchat_data').resolve()


def db_op(conn: sqlite3.Connection, sql: str, params: list):
    cur = conn.cursor()
    res = conn.execute(sql, params).fetchall()
    cur.connection.commit()
    cur.close()
    return res    

def db_op_many(conn: sqlite3.Connection, sql: str, params: list):
    cur = conn.cursor()
    res = conn.executemany(sql, params).fetchall()
    cur.connection.commit()
    cur.close()
    return res    

def upd_remid_sid(res: httpx.Response, remid, sid):
    res_cookies = httpx.Cookies.extract_cookies(res.cookies,res)
    res_cookies = json.dumps(res_cookies)
    if 'sid' in res_cookies:
        sid = res_cookies['sid']
    if 'remid' in res_cookies:
        remid = res_cookies['remid']
    return remid, sid

async def upd_token(remid, sid):
    async with httpx.AsyncClient() as client:
        res_access_token = await client.get(
            url="https://accounts.ea.com/connect/auth",
            params= {
                'client_id': 'ORIGIN_JS_SDK',
                'response_type': 'token',
                'redirect_uri': 'nucleus:rest',
                'prompt': 'none',
                'release_type': 'prod'
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36',
                'content-type': 'application/json'
            }
        )

    access_token = res_access_token.json()['access_token']
    remid, sid = upd_remid_sid(res_access_token, remid, sid)
    return remid, sid, access_token

async def upd_sessionId(remid, sid):
    async with httpx.AsyncClient() as client:
        res_authcode = await client.get(       
            url="https://accounts.ea.com/connect/auth",
            params= {
                'client_id': 'sparta-backend-as-user-pc',
                'response_type': 'code',
                'release_type': 'none'
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}'
            },
            follow_redirects=False
        )
    # 这个请求默认会重定向，所以要禁用重定向，并且重定向地址里的code参数就是我们想要的authcode
    authcode = str.split(res_authcode.headers.get("location"), "=")[1]
    remid, sid = upd_remid_sid(res_authcode, remid, sid)

    async with httpx.AsyncClient() as client:
        res_session = await client.post( 
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json= {
                'jsonrpc': '2.0',
                'method': 'Authentication.getEnvIdViaAuthCode',
                'params': {
                    'authCode': authcode,
                    "locale": "zh-tw",
                },
                "id": str(uuid.uuid4())
            }
        )
    sessionID = res_session.json()['result']['sessionId']
    return remid,sid,sessionID

async def init_sessionid():
    conn = sqlite3.connect(BFCHAT_DATA_FOLDER/'bot.db')
    admins = [{'pid': r[0], 'remid': r[1], 'sid': r[2]} for r in db_op(conn, "SELECT pid, remid, sid FROM bf1admins;", [])]
    tasks_token = [asyncio.create_task(upd_token(admin['remid'], admin['sid'])) for admin in admins]
    list_cookies_tokens = await asyncio.gather(*tasks_token) # Update tokens
    for i in range(len(admins)):
        admins[i]['remid'] = list_cookies_tokens[i][0]
        admins[i]['sid'] = list_cookies_tokens[i][1]
        admins[i]['token'] = list_cookies_tokens[i][2]
    print('Token updates complete')

    tasks_session = [
        asyncio.create_task(upd_sessionId(admin['remid'], admin['sid'])) for admin in admins
    ]
    list_cookies_sessionIDs = await asyncio.gather(*tasks_session)
    for i in range(len(admins)):
        admins[i]['remid'] = list_cookies_sessionIDs[i][0]
        admins[i]['sid'] = list_cookies_sessionIDs[i][1]
        admins[i]['sessionid'] = list_cookies_sessionIDs[i][2]
    db_op_many(conn, 'UPDATE bf1admins SET remid=:remid, sid=:sid, token=:token, sessionid=:sessionid WHERE pid=:pid', admins)
    print('SessionID updates complete')
    conn.close()


async def upd_servers(remid, sid, sessionID):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "GameServer.searchServers",
	            "params": {
		        "filterJson": "{\"serverType\":{\"OFFICIAL\": \"off\"}}",
                "game": "tunguska",
                "limit": 200,
                "protocolVersion": "3779779"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=None
        )
    return response.json()

async def upd_detailedServer(remid, sid, sessionID, gameId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "GameServer.getFullServerDetails",
	            "params": {
		        "game": "tunguska",
                "gameId": f"{gameId}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=None
        )

    return response.json()

async def upd_gameId():
    conn = sqlite3.connect(BFCHAT_DATA_FOLDER/'bot.db')
    time_start = time.time()
    print(datetime.datetime.now())
    gameIdList = []
    tasks = []
    remid, sid, sessionID = db_op(conn, "SELECT remid, sid, sessionid FROM bf1admins ORDER BY RANDOM() LIMIT 1;", [])[0]
    for _ in range(30):
        tasks.append(upd_servers(remid, sid, sessionID))
    results = await asyncio.gather(*tasks)
    for result in results:
        if isinstance(result, str):
            continue
        result: list = result["result"]
        server_list = result['gameservers']
        for server in server_list:
            if server["gameId"] not in gameIdList:
                gameIdList.append(server["gameId"])
    print(f"共获取{len(gameIdList)}个私服")
    
    tasks = []
    results = []
    progress = 0
    for game_id in gameIdList:
        tasks.append(upd_detailedServer(remid, sid, sessionID, game_id))
        if len(tasks) == 250:
            print(f"开始获取私服详细信息，共{len(tasks)}个，总进度{progress}/{len(gameIdList)}")
            temp = await asyncio.gather(*tasks)
            results.extend(temp)
            progress += len(tasks)
            tasks = []
    if tasks:
        print(f"开始获取私服详细信息，共{len(tasks)}个，总进度{progress}/{len(gameIdList)}")
        temp = await asyncio.gather(*tasks)
        results.extend(temp)

    results = [result for result in results if not isinstance(result, str)]
    print(f"共获取{len(results)}个私服详细信息")

    serverId_list = []
    server_dict = {}
    vip_dict = {}
    ban_dict = {}
    admin_dict = {}
    owner_dict = {}
    for result in results:
        server = result["result"]
        rspInfo = server.get("rspInfo", {})
        Info = server["serverInfo"]
        if not rspInfo:
            continue
        server_name = Info["name"]
        server_server_id = rspInfo.get("server", {}).get("serverId")
        server_guid = Info["guid"]
        server_game_id = Info["gameId"]
        serverBookmarkCount = Info["serverBookmarkCount"]

        #   将其转换为datetime
        createdDate = rspInfo.get("server", {}).get("createdDate")
        createdDate = datetime.datetime.fromtimestamp(int(createdDate) / 1000)
        expirationDate = rspInfo.get("server", {}).get("expirationDate")
        expirationDate = datetime.datetime.fromtimestamp(int(expirationDate) / 1000)
        updatedDate = rspInfo.get("server", {}).get("updatedDate")
        updatedDate = datetime.datetime.fromtimestamp(int(updatedDate) / 1000)

        serverInfo = {
            "server_name": f"{server_name}",
            "server_server_id": f"{server_server_id}",
            "server_guid": f"{server_guid}",
            "server_game_id": f"{server_game_id}",
            "serverBookmarkCount": f"{serverBookmarkCount}",
            "createdDate": f"{createdDate}",
            "expirationDate": f"{expirationDate}",
            "updatedDate": f"{updatedDate}"
        }

        serverId_list.append(server_server_id)
        server_dict[server_server_id] = serverInfo
        vip_dict[server_server_id] = rspInfo.get("vipList", [])
        ban_dict[server_server_id] = rspInfo.get("bannedList", [])
        admin_dict[server_server_id] = rspInfo.get("adminList", [])
        if owner := rspInfo.get("owner"):
            owner_dict[server_server_id] = [owner]

    with open(BFCHAT_DATA_FOLDER/'bf1_servers'/'info.json','w',encoding='UTF-8') as f:
        json.dump(server_dict,f,ensure_ascii=False,indent=4)
    print(f"更新服务器信息完成")

    with open(BFCHAT_DATA_FOLDER/'bf1_servers'/'vip.json','w',encoding='UTF-8') as f:
        json.dump(vip_dict,f,ensure_ascii=False,indent=4)
    print(f"更新服务器VIP完成")

    with open(BFCHAT_DATA_FOLDER/'bf1_servers'/'ban.json','w',encoding='UTF-8') as f:
        json.dump(ban_dict,f,ensure_ascii=False,indent=4)
    print(f"更新服务器封禁完成")

    with open(BFCHAT_DATA_FOLDER/'bf1_servers'/'admin.json','w',encoding='UTF-8') as f:
        json.dump(admin_dict,f,ensure_ascii=False,indent=4)
    print(f"更新服务器管理员完成")

    with open(BFCHAT_DATA_FOLDER/'bf1_servers'/'owner.json','w',encoding='UTF-8') as f:
        json.dump(owner_dict,f,ensure_ascii=False,indent=4)
    print(f"更新服务器所有者完成")

    print(f"共更新{len(serverId_list)}个私服详细信息，耗时{round(time.time() - time_start, 2)}秒")
    print('---------------------------------------')

    db_admin_pids = [r[0] for r in db_op(conn, 'SELECT pid FROM bf1admins', [])]
    server_bf1admins = []

    for serverid, adlist in admin_dict.items():
        pids = list(set(int(ad["personaId"]) for ad in adlist).intersection(db_admin_pids))
        for pid in pids:
            server_bf1admins.append((int(serverid), pid))
    db_op(conn, 'DELETE FROM serverbf1admins;', [])
    db_op_many(conn, 'INSERT INTO serverbf1admins (serverid, pid) VALUES(?, ?);', 
               server_bf1admins)
    conn.close()

def upd_ping():
        response = requests.get(url=f'https://mag1catz.vip.cpolar.cn/web1/ping',timeout=10)
        return response
def upd_ping1():
        response1 = requests.get(url=f'https://mag1catz.vip.cpolar.cn/web2/ping',timeout=10)
        return response1
def upd_ping2():
        response1 = requests.get(url=f'https://mag1catz.vip.cpolar.cn/web3/ping',timeout=10)
        return response1

def renew():
    redis_client = redis.Redis()
    conn = sqlite3.connect(BFCHAT_DATA_FOLDER/'bot.db')
    with open(BFCHAT_DATA_FOLDER/'bf1_servers/info.json','r') as f:
        info = json.load(f)

    gsbinds = db_op(conn, 'SELECT groupqq, ind, serverid FROM groupservers;', [])

    server_dict = {}
    for groupqq, server_ind, serverid in gsbinds:
        if not groupqq in server_dict:
            server_dict[groupqq] = {}
        server_dict[groupqq][server_ind] = serverid
    
    for serverid in info.keys():
            redis_client.set(f'gameid:{int(serverid)}', int(info[serverid]["server_game_id"]))
    
    with open(BFCHAT_DATA_FOLDER/'bind.json',"w") as f:
        json.dump(server_dict,f,indent=4)
    redis_client.close()
    conn.close()

async def start_job():
    scheduler = AsyncIOScheduler()
    global sessionID,remid,sid

    scheduler.add_job(upd_gameId, 'interval', minutes=30)
    scheduler.add_job(upd_ping, 'interval', seconds=30)
    scheduler.add_job(upd_ping1, 'interval', seconds=30)
    scheduler.add_job(upd_ping2, 'interval', seconds=30)
    scheduler.add_job(renew, 'interval', minutes=5)

    scheduler.start()
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == '__main__':
    # asyncio.run(init_sessionid()) # Run this command when doing setup for a new production environment.
    asyncio.run(upd_gameId())
    renew()
    asyncio.run(start_job())