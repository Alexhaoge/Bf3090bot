import json, asyncio, datetime, requests
import psycopg
import redis
import multiprocessing
import time
import logging
import traceback
from dotenv import dotenv_values
from pathlib import Path
from PIL import Image
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from cronlib.db import *
from cronlib.api import *
from cronlib.cron_secret import *
from cronlib.utils import str_to_bool

config = dotenv_values('.env.prod')
BFCHAT_DATA_FOLDER = Path(config['BFCHAT_DIR']).resolve()
BLAZE_HOST = config['BLAZE_HOST']
PROXY_HOST = config['PROXY_HOST']
db_url = config['psycopg_database']

EAC_SERVER_BLACKLIST = []
for serverid in config['EAC_SERVER_BLACKLIST'].split(","):
    if serverid.isdigit():
        EAC_SERVER_BLACKLIST.append(int(serverid))
VBAN_EAC_ENABLE = str_to_bool(config['VBAN_EAC_ENABLE'])

with open(BFCHAT_DATA_FOLDER/'bf1_servers/zh-cn.json','r', encoding='utf-8') as f:
    zh_cn_mapname = json.load(f)

##################################  Cookies  ##################################
async def refresh_cookie_and_sessionid():
    conn = psycopg.connect(db_url)
    admins = [{'pid': r[0], 'remid': r[1], 'sid': r[2]} for r in db_op(conn, "SELECT pid, remid, sid FROM bf1admins;", [])]
    tasks_token = [asyncio.create_task(upd_token(admin['remid'], admin['sid'], PROXY_HOST)) for admin in admins]
    list_cookies_tokens = await asyncio.gather(*tasks_token, return_exceptions=True) # Update tokens
    for i in range(len(admins)):
        if isinstance(list_cookies_tokens[i], tuple):
            admins[i]['remid'] = list_cookies_tokens[i][0]
            admins[i]['sid'] = list_cookies_tokens[i][1]
            admins[i]['token'] = list_cookies_tokens[i][2]
        else:
            print(f"token update failed for {admins[i]['pid']}")
    print('Token updates complete')

    tasks_session = [
        asyncio.create_task(upd_sessionId(admin['remid'], admin['sid'], PROXY_HOST)) for admin in admins
    ]
    list_cookies_sessionIDs = await asyncio.gather(*tasks_session, return_exceptions=True)
    for i in range(len(admins)):
        if isinstance(list_cookies_sessionIDs[i], tuple):
            admins[i]['remid'] = list_cookies_sessionIDs[i][0]
            admins[i]['sid'] = list_cookies_sessionIDs[i][1]
            admins[i]['sessionid'] = list_cookies_sessionIDs[i][2]
        else:
            print(f"sessionID update failed for {admins[i]['pid']}")
    db_op_many(conn, 'UPDATE bf1admins SET remid=%(remid)s, sid=%(sid)s, token=%(token)s, sessionid=%(sessionid)s WHERE pid=%(pid)s', 
               filter(lambda d: ('sessionid' in d) and ('token' in d), admins))
    print('SessionID updates complete')
    conn.close()


################################## owner/admin/ban/vip ##################################
async def refresh_serverInfo():
    time_start = time.time()
    conn = psycopg.connect(db_url)
    redis_client = redis_connection_helper()
    print(datetime.datetime.now())
    gameIdList = []
    tasks = []
    for _ in range(30):
        remid, sid, sessionID = get_one_random_bf1admin(conn)
        tasks.append(upd_servers(remid, sid, sessionID, PROXY_HOST))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, (Exception, str)):
            print(result)
            continue
        result: list = result["result"]
        server_list = result['gameservers']
        for server in server_list:
            if server["gameId"] not in gameIdList:
                gameIdList.append(server["gameId"])
    print(f"共获取{len(gameIdList)}个私服")
    
    tasks = []
    results = []
    for game_id in gameIdList:
        remid, sid, sessionID = get_one_random_bf1admin(conn)
        tasks.append(upd_detailedServer(remid, sid, sessionID, game_id, PROXY_HOST))
        if len(tasks) == 50:
            print(f"开始获取私服详细信息，共{len(tasks)}个，总进度{len(results)}/{len(gameIdList)}")
            temp = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(filter(lambda x: isinstance(x, dict), temp))
            tasks = []
            await asyncio.sleep(1)
    if tasks:
        print(f"开始获取私服详细信息，共{len(tasks)}个，总进度{len(results)}/{len(gameIdList)}")
        temp = await asyncio.gather(*tasks, return_exceptions=True)
        results.extend(filter(lambda x: isinstance(x, dict), temp))
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

    print(f"共更新{len(serverId_list)}个私服详细信息")

    db_admin_pids = set(r[0] for r in db_op(conn, 'SELECT pid FROM bf1admins', []))
    
    server_bf1admins_add = []
    server_bf1admins_del = []

    for serverid, ownlist in owner_dict.items():
        pid = int(ownlist[0]["personaId"])
        if pid in db_admin_pids:
            server_bf1admins_exist = db_op(conn, "SELECT pid FROM serverbf1admins WHERE serverid=%s AND pid=%s;", [int(serverid), int(pid)])
            if not len(server_bf1admins_exist):
                server_bf1admins_add.append((int(serverid), pid))
            admin_dict[serverid].append(ownlist[0])

    for serverid, adlist in admin_dict.items():
        server_bf1admins_exist = set(int(r[0]) for r in db_op(conn, 'SELECT pid FROM serverbf1admins WHERE serverid=%s;', [int(serverid)]))
        real_bf1admins_esist = set(int(ad["personaId"]) for ad in adlist).intersection(db_admin_pids)
        server_bf1admins_del.extend(
           ((int(serverid), pid) for pid in list(server_bf1admins_exist.difference(real_bf1admins_esist)))
        )
        server_bf1admins_add.extend(
            ((int(serverid), pid) for pid in list(real_bf1admins_esist.difference(server_bf1admins_exist)))
        )
    
    with_bf1admin_servers_in_db = db_op(conn, "SELECT DISTINCT serverid from serverbf1admins;", [])
    bf1admins_del_serverid = [(int(r[0]), ) for r in with_bf1admin_servers_in_db if str(r[0]) not in admin_dict]

    print(bf1admins_del_serverid)
    db_op_many(conn, 'DELETE FROM serverbf1admins WHERE serverid=%s;', bf1admins_del_serverid)

    print(server_bf1admins_del)
    print(server_bf1admins_add)
    db_op_many(conn, 'DELETE FROM serverbf1admins WHERE serverid=%s AND pid=%s;', server_bf1admins_del)
    db_op_many(conn, 'INSERT INTO serverbf1admins (serverid, pid) VALUES(%s, %s) ON CONFLICT (serverid, pid) DO NOTHING;', server_bf1admins_add)

    for serverid in server_dict.keys():
        redis_client.set(f'gameid:{int(serverid)}', int(server_dict[serverid]["server_game_id"]))

    conn.close()
    redis_client.close()
    print(f'数据库更新完成, 耗时{round(time.time() - time_start, 2)}秒')
    print('---------------------------------------')


##################################  BLAZE  ##################################
def upd_ping():
        response = requests.get(url=f'http://{BLAZE_HOST}/web1/ping',timeout=10)
        return response
def upd_ping1():
        response1 = requests.get(url=f'http://{BLAZE_HOST}/web2/ping',timeout=10)
        return response1
def upd_ping2():
        response1 = requests.get(url=f'http://{BLAZE_HOST}/web3/ping',timeout=10)
        return response1


################################## Alarm reset ##################################
def bf1_reset_alarm_session():
    redis_client = redis_connection_helper()
    conn = psycopg.connect(db_url)
    alarm_sessions = db_op(conn, 'SELECT groupqq FROM groups WHERE alarm=true;', [])
    alarm_groupqqs = [r[0] for r in alarm_sessions]
    if len(alarm_groupqqs):
        redis_client.sadd("alarmsession", *alarm_groupqqs)
    keys_to_del = [f"alarmamount:{groupqq}" for groupqq in alarm_groupqqs]
    if len(keys_to_del):
        redis_client.delete(*keys_to_del)
    print('Alarm session reset')
    redis_client.close()
    conn.close()


################################## draw and alarm ##################################
draw_lock = asyncio.Lock()
async def upd_draw():
    redis_client = redis_connection_helper()
    conn = psycopg.connect(db_url)
    logging.info(datetime.datetime.now())

    tasks = []
    remid, sid, sessionID = get_one_random_bf1admin(conn)
    conn.close()
    for _ in range(30):
        tasks.append(upd_servers(remid, sid, sessionID, PROXY_HOST))
    results = await asyncio.gather(*tasks, return_exceptions=True)

    draw_dict = {}
    for result in results:
        if not isinstance(result, dict):
            continue
        result = result["result"]
        server_list = result['gameservers']
        for i, server in enumerate(server_list):
            gameid = str(server["gameId"])
            if gameid not in draw_dict and int(server["slots"]["Soldier"]["current"])!=0:
                draw_dict[gameid] = {
                    "server_name": server["name"],
                    "serverMax":server["slots"]["Soldier"]["max"],
                    "serverAmount": server["slots"]["Soldier"]["current"],
                    "map": server["mapName"]
                }
                redis_client.hset(f'draw_dict:{gameid}', mapping=draw_dict[gameid])
                redis_client.expire(f'draw_dict:{gameid}', time=180+(i%20))

    print(f"draw_dict:共获取{len(draw_dict)}个私服")
    redis_client.close()

    try:
        with open(BFCHAT_DATA_FOLDER/'bf1_servers/draw.json','r',encoding='UTF-8') as f:
            data = json.load(f)
    except:
        data = {}
    data[f"{datetime.datetime.now().isoformat()}"] = draw_dict 
    data_keys = list(data.keys())
    for i in data_keys:
        try:    
            if (datetime.datetime.now() - datetime.datetime.fromisoformat(i)).days >= 1:
                data.pop(i)
        except:
            continue
    
    async with draw_lock:
        with open(BFCHAT_DATA_FOLDER/'bf1_servers/draw.json','w',encoding='UTF-8') as f:
            json.dump(data,f,indent=4,ensure_ascii=False)

def get_server_status(groupqq: int, ind: str, status: dict, redis_client: redis.Redis): 
    try:
        playerAmount = int(status['serverAmount'])
        maxPlayers = int(status['serverMax'])
        mapName = zh_cn_mapname[str(status['map'])]
    except:
        # print(f'No data for gameId:{gameId}')
        return
    else:
        try:
            #if groupqq == 875349777: # Test
            if max(maxPlayers-34,maxPlayers/3) < playerAmount < maxPlayers-10:
                alarm_amount = redis_client.hincrby(f'alarmamount:{groupqq}', ind)
                print(groupqq, ind, playerAmount, mapName, alarm_amount)
                redis_client.xadd("alarmstream", {'groupqq': groupqq, 'ind': ind, 'player': playerAmount, 'map': mapName, 'alarm': alarm_amount},
                                  maxlen=500)
        except:
            print(traceback.format_exc(2))

def trigger_alarm():
    start_time = datetime.datetime.now()
    redis_client = redis_connection_helper()
    conn = psycopg.connect(db_url)
    alarm_session_set = redis_client.smembers('alarmsession')

    servers = db_op(conn, 'SELECT serverid FROM servers;', [])
    serverids = list(r[0] for r in servers)
    serverid_gameIds = batch_get_gameids(redis_client, serverids)

    sgid_dict = {}
    gameids = []
    for serverid, gameid in serverid_gameIds:
        sgid_dict[str(serverid)] = gameid
        gameids.append(gameid)

    draw_dict = batch_get_draw_dict(redis_client, gameids)

    for groupqq_b in alarm_session_set:
        groupqq = int(groupqq_b)
        main_groupqq = db_op(conn, 'SELECT bind_to_group FROM groups WHERE groupqq=%s;', [groupqq])
        if not len(main_groupqq):
            continue
        servers = db_op(conn, 'SELECT ind, serverid FROM groupservers WHERE groupqq=%s;', [main_groupqq[0][0]])
        for ind, serverid in servers:
            try:
                gameid = sgid_dict[str(serverid)]
                status = draw_dict[str(gameid)]
            except Exception as e:
                #print(f'gameid for {e} not found')
                continue

            alarm_amount = redis_client.hget(f'alarmamount:{groupqq}', ind)
            if (not alarm_amount) or (int(alarm_amount) < 3):
                get_server_status(groupqq, ind, status, redis_client)
    redis_client.close()
    conn.close()
    end_time = datetime.datetime.now()
    thr_time = (end_time - start_time).total_seconds()
    print(f"预警生产用时：{thr_time}秒")


################################## Vban ##################################
async def kick_vbanPlayer(conn: psycopg.Connection, redis_client: redis.Redis, pljson: dict, sgids: list, vbans: dict):
    tasks = []
    report_list = []
    personaIds = []
    
    kick_rows = db_op(conn, "SELECT serverid, bfeac, bfban FROM serverautokicks;", [])

    kick_status = {}
    for r in kick_rows:
        kick_status[str(r[0])] = {"bfeac": r[1],"bfban": r[2]}
    
    with open(BFCHAT_DATA_FOLDER/'bfeac_ban.json',"r",encoding="utf-8") as f:
        bfeac_ids = json.load(f)["data"]

    with open(BFCHAT_DATA_FOLDER/'bfban_ban.json',"r",encoding="utf-8") as f:
        bfban_ids = json.load(f)["data"]

    for serverid, gameId in sgids:
        pl = pljson[str(gameId)]
        try:
            vban_ids = vbans[serverid]['pid']
            vban_reasons = vbans[serverid]['reason']
            vban_groupqqs = vbans[serverid]['groupqq']
        except Exception as e:
            print(e)
            continue

        remid, sid, sessionID, _  = get_bf1admin_by_serverid(conn, serverid)
        if not remid:
            continue
        try:
            pl_ids = [int(s['id']) for s in pl['1']] + [int(s['id']) for s in pl['2']]
        except:
            pl_ids = pl

        try:
            EAC = kick_status[str(serverid)]["bfeac"]
            BAN = kick_status[str(serverid)]["bfban"]
        except:
            EAC = BAN = False
        
        if EAC and (not serverid in EAC_SERVER_BLACKLIST):
            reason = "Banned by bfeac.com"
            for personaId in pl_ids:
                if personaId in bfeac_ids:
                    report_list.append({"eac": True})
                    tasks.append(upd_kickPlayer(remid,sid,sessionID,gameId,personaId,reason, PROXY_HOST))
        
        if BAN and not EAC:
            reason = "Banned by bfban.com"
            for personaId in pl_ids:
                if personaId in bfban_ids:
                    report_list.append({"eac": True})
                    tasks.append(upd_kickPlayer(remid,sid,sessionID,gameId,personaId,reason, PROXY_HOST))            

        for personaId in pl_ids:
            if personaId in vban_ids:
                index = vban_ids.index(personaId)
                reason = vban_reasons[index]
                groupqq = vban_groupqqs[index]
                personaIds.append(personaId)
                report_list.append(
                    {
                        "gameId": gameId,
                        "personaId": personaId,
                        "reason": reason, 
                        "groupqq": groupqq,
                        "eac": False
                    }
                )
                tasks.append(upd_kickPlayer(remid,sid,sessionID,gameId,personaId,reason, PROXY_HOST))

    res = await asyncio.gather(*tasks, return_exceptions=True)
    logging.debug(res)
    try:
        res_pid = await upd_getPersonasByIds(remid,sid,sessionID,personaIds, PROXY_HOST)
    except:
        res_pid = None

    if res != []:
        for r, report_dict in zip(res, report_list):
            if not isinstance(r, Exception) and not report_dict["eac"]:
                try:
                    gameId = report_dict["gameId"]
                    reason = report_dict["reason"]
                    personaId = report_dict["personaId"]
                    groupqq = report_dict["groupqq"]
                    if not groupqq:
                        continue
                    name = redis_client.hget(f'draw_dict:{gameId}', "server_name")
                    if not name:
                        name = f'gameid:{gameId}'
                    if res_pid and str(personaId) in res_pid['result']:
                        eaid = res_pid['result'][str(personaId)]['displayName']
                    else:
                        eaid = f'pid:{personaId}'
                    report_msg = f"Vban提示: 在{name}踢出{eaid}, 理由: {reason}"
                    redis_client.xadd("vbanstream", {'groupqq': groupqq, 'msg': report_msg}, maxlen=500)
                    print(report_msg)
                except Exception as e:
                    print(traceback.format_exc())
                    continue


async def start_vban(conn: psycopg.Connection, redis_client: redis.Redis, sgids: list, vbans: dict):
    try:
        #pljson = await upd_blazeplforvban([t[1] for t in sgids])
        pljson = await Blaze2788Pro([t[1] for t in sgids])
    except:
        print(traceback.format_exc())
        print('Vban Blaze error for ' + ','.join([str(t[1]) for t in sgids]))
    else:
        try:
            await kick_vbanPlayer(conn, redis_client, pljson, sgids, vbans) 
        except Exception as e:
            print(traceback.format_exc())
            print('Vban exception during execution: ' + traceback.format_exception_only(e)[0] + \
                           '\n' + ','.join([str(t[1]) for t in sgids]))

async def start_vban_by_snapshot(conn: psycopg.Connection, redis_client: redis.Redis, sgids: list, vbans: dict, snapshot:dict):
    try:
        await kick_vbanPlayer(conn, redis_client, snapshot, sgids, vbans) 
    except Exception as e:
        print(traceback.format_exc())
        print('Vban exception during execution: ' + traceback.format_exception_only(e)[0] + \
                        '\n' + ','.join([str(t[1]) for t in sgids]))
        
async def upd_vbanPlayer():
    start_time = datetime.datetime.now()
    redis_client = redis_connection_helper()
    conn = psycopg.connect(db_url)

    vbans = {}
    vban_rows = db_op(conn, "SELECT serverid, pid, reason, notify_group FROM servervbans;", [])
    vban_servers = set(r[0] for r in vban_rows)
    
    serverid_gameIds = batch_get_gameids(redis_client, list(vban_servers))
    
    for vban_row in vban_rows:
        serverid = vban_row[0]
        vbans[serverid] = {'pid':[], 'groupqq': [], 'reason': []}
        vbans[serverid]['pid'].append(vban_row[1])
        vbans[serverid]['groupqq'].append(vban_row[3])
        vbans[serverid]['reason'].append(vban_row[2])
    try:
        snapshot = await get_snapshot()
        snapshot_gameids = list(snapshot.keys())
    except:
        print(traceback.format_exc())
        print('Vban Blaze error for snapshot')
    
    if len(serverid_gameIds):
        sgids = []
        sgids_snap = []
        for i in range(len(serverid_gameIds)):
            (serverid, gameId) = serverid_gameIds[i]
            if str(gameId) in snapshot_gameids:
                sgids_snap.append(serverid_gameIds[i])

        await start_vban_by_snapshot(conn, redis_client, sgids_snap,vbans,snapshot)
        
    conn.close()
    redis_client.close()
    end_time = datetime.datetime.now()
    thr_time = (end_time - start_time).total_seconds()
    print(f"Vban生产用时：{thr_time}秒")

################################## Bfban Token ##################################
async def BFBAN_renew_token():
    res = await BFBAN_signin()
    try:
        token = res["data"]["token"]
        with open(BFCHAT_DATA_FOLDER/'bfban_token.txt','w', encoding='utf-8') as f:
            f.write(token)
    except Exception as e:
        print(e)

################################## Bfeac & BFBAN DB ##################################
async def BFEAC_db():
    res = await bfeac_checkBanAll()
    try:
        with open(BFCHAT_DATA_FOLDER/'bfeac_ban.json',"w",encoding="utf-8") as f:
            json.dump(res,f,indent=4,ensure_ascii=False)
        print('BFEAC banlist renewed')
    except:
        print('BFEAC banlist renew failed')

async def BFBAN_db(init: bool = False):
    with open(BFCHAT_DATA_FOLDER/'bfban_token.txt','r') as f:
        token = f.read()
    
    if init:
        banlist = {}
        res = await bfban_checkBanAll(token,1000000)
    else:    
        with open(BFCHAT_DATA_FOLDER/'bfban_db.json',"r",encoding="utf-8") as f:
            banlist = json.load(f)
        res = await bfban_checkBanAll(token,200)

    cheaters = []
    try:
        new_banlist = list(res)
        for data in new_banlist:
            id = data["id"]
            pid = data["originPersonaId"]
            status = data["status"]

            banlist[str(id)] = {
                "pid": int(pid),
                "status": status
            }

        with open(BFCHAT_DATA_FOLDER/'bfban_db.json',"w",encoding="utf-8") as f:
            json.dump(banlist,f,indent=4,ensure_ascii=False)
        
        for data in list(banlist.values()):
            if data["status"] == 1:
                cheaters.append(int(data["pid"]))

        cheaters = {
            "data": cheaters
        }
        with open(BFCHAT_DATA_FOLDER/'bfban_ban.json',"w",encoding="utf-8") as f:
            json.dump(cheaters,f,indent=4,ensure_ascii=False)
        print('BFBAN banlist renewed')
    except Exception as e:
        print(f'BFBAN banlist renew failed:{e}' )
    

################################## Multiprocess Asyncio Scheduler ##################################
def start_job0():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        scheduler = AsyncIOScheduler(event_loop=loop)
        scheduler.add_job(refresh_cookie_and_sessionid, 'interval', hours=2)
        scheduler.add_job(BFBAN_renew_token, 'interval', hours=6)
        scheduler.add_job(refresh_serverInfo, 'interval', minutes=30)
        scheduler.add_job(upd_ping, 'interval', seconds=30)
        scheduler.add_job(upd_ping1, 'interval', seconds=30)
        scheduler.add_job(upd_ping2, 'interval', seconds=30)
        scheduler.start()
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.stop()
        loop.close()

def start_job1():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        scheduler = AsyncIOScheduler(event_loop=loop)
        scheduler.add_job(bf1_reset_alarm_session, 'interval', minutes=15)
        scheduler.add_job(upd_draw, 'interval', minutes=2, misfire_grace_time=60)
        scheduler.add_job(trigger_alarm, 'interval', minutes=2, misfire_grace_time=60)
        scheduler.start()
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.stop()
        loop.close()

def start_job2():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        scheduler = AsyncIOScheduler(event_loop=loop)
        scheduler.add_job(upd_vbanPlayer, 'interval', seconds=10, misfire_grace_time=10)
        scheduler.start()
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.stop()
        loop.close()

def start_job3():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        scheduler = AsyncIOScheduler(event_loop=loop)
        scheduler.add_job(BFEAC_db, 'interval', minutes=10)
        scheduler.add_job(BFBAN_db, 'interval', minutes=10)
        scheduler.start()
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.stop()
        loop.close()

def run_process(job):
    process = multiprocessing.Process(target=job)
    process.start()
    return process

if __name__ == '__main__':
    asyncio.run(refresh_cookie_and_sessionid()) # Run this command when doing setup for a new production environment.
    asyncio.run(BFBAN_renew_token())
    asyncio.run(BFEAC_db())
    asyncio.run(BFBAN_db(init=True))
    asyncio.run(refresh_serverInfo())
    bf1_reset_alarm_session()
    asyncio.run(upd_draw())
    
    processes = []
    try:
        processes.append(run_process(start_job0))
        processes.append(run_process(start_job1))
        processes.append(run_process(start_job2))
        processes.append(run_process(start_job3))
        for process in processes:
            process.join()
    except (KeyboardInterrupt, SystemExit):
        for process in processes:
            process.terminate()
            process.join()