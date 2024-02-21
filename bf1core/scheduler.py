import nonebot

from nonebot.log import logger
from nonebot.params import _command_arg
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment, Bot
from nonebot.typing import T_State

import time
import json
import asyncio
import datetime
import traceback

from nonebot_plugin_apscheduler import scheduler

from sqlalchemy.future import select

from ..utils import BF1_SERVERS_DATA
from ..bf1rsp import upd_servers_full, upd_kickPlayer, upd_getPersonasByIds, RSPException
from ..bf1draw import *
from ..secret import *
from ..rdb import *
from ..redis_helper import redis_client
from ..bf1helper import *

from .matcher import BF1_SERVER_ALARM,BF1_SERVER_ALARMOFF

draw_dict = {}

@BF1_SERVER_ALARM.handle()
async def bf1_server_alarm(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    try:
        arg = message.extract_plain_text().split()
        groupqq = int(arg[0])
    except:
        groupqq = event.group_id
    user_id = event.user_id
    groupqq_main = await check_session(groupqq)
    if not groupqq_main:
        await BF1_SERVER_ALARM.finish(MessageSegment.reply(event.message_id) + '本群组未初始化')
    admin_perm = await check_admin(groupqq_main, user_id)
    if admin_perm:
        await redis_client.sadd('alarmsession', groupqq)
        async with async_db_session() as session:
            group_r = (await session.execute(select(ChatGroups).filter_by(groupqq=groupqq))).first()
            if group_r[0].alarm:
                await BF1_SERVER_ALARM.send(f'请不要重复打开')
            else:
                group_r[0].alarm = True
                session.add(group_r[0])
                await session.commit()
                await BF1_SERVER_ALARM.send(f'已打开预警，请注意接收消息')
    else:
        await BF1_SERVER_ALARM.send('你不是本群组的管理员')

@BF1_SERVER_ALARMOFF.handle()
async def bf1_server_alarmoff(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    groupqq = event.group_id
    user_id = event.user_id
    
    groupqq_main = await check_session(groupqq)
    if not groupqq_main:
        await BF1_SERVER_ALARMOFF.finish(MessageSegment.reply(event.message_id) + '本群组未初始化')
    admin_perm = await check_admin(groupqq_main, user_id)
    
    if admin_perm:
        await redis_client.srem('alarmsession', groupqq)
        
        async with async_db_session() as session:
            group_r = (await session.execute(select(ChatGroups).filter_by(groupqq=groupqq))).first()
            if group_r[0].alarm:
                group_r[0].alarm = False
                session.add(group_r[0])
                await session.commit()
                await BF1_SERVER_ALARMOFF.send('已关闭预警')
            else:
                await BF1_SERVER_ALARMOFF.send('本群组未打开预警')
    else:
        await BF1_SERVER_ALARMOFF.send('你不是本群组的管理员')


######################################## Schedule job helper functions #########################################
draw_lock = asyncio.Lock()

async def upd_draw(remid,sid,sessionID, timeout: int = None):
    time_start = time.time()
    print(datetime.datetime.now())

    tasks = []
    for _ in range(30):
        tasks.append(upd_servers_full(remid, sid, sessionID, timeout))
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
                await redis_client.hmset(f'draw_dict:{gameid}', draw_dict[gameid])
                await redis_client.expire(f'draw_dict:{gameid}', time=180+(i%20))

    print(f"共获取{len(draw_dict)}个私服")

    try:
        with open(BF1_SERVERS_DATA/'draw.json','r',encoding='UTF-8') as f:
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
        with open(BF1_SERVERS_DATA/'draw.json','w',encoding='UTF-8') as f:
            json.dump(data,f,indent=4,ensure_ascii=False)


async def get_server_status(groupqq: int, ind: str, serverid: int, bot: Bot): 
    with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
        zh_cn = json.load(f)
    gameId = await get_gameid_from_serverid(serverid)
    try:
        status = (await redis_client.hgetall(f'draw_dict:{gameId}'))
        playerAmount = int(status['serverAmount'])
        maxPlayers = int(status['serverMax'])
        Map = zh_cn[str(status['map'])]
    except:
        logger.debug(f'No data for gameId:{gameId}')
    else:
        #print(playerAmount,maxPlayers,Map)
        #print(f'{bot}{groupqq}群{ind}服人数{playerAmount}')
        try:
            #if True: # Test
            if max(maxPlayers-34,maxPlayers/3) < playerAmount < maxPlayers-10:
                alarm_amount = await redis_client.hincrby(f'alarmamount:{groupqq}', ind)
                try:
                    await bot.send_group_msg(group_id=groupqq, message=f'第{alarm_amount}次警告：{ind}服人数大量下降到{playerAmount}人，请注意。当前地图为：{Map}。')
                    return 1
                except Exception as e:
                    logger.warning(e)
                    return 0
            else:
                return 0
        except:
            logger.error(traceback.format_exc(2))
            return 0

async def kick_vbanPlayer(pljson: dict, sgids: list, vbans: dict):
    tasks = []
    report_list = []
    personaIds = []

    for serverid, gameId in sgids:
        pl = pljson[str(gameId)]
        vban_ids = vbans[serverid]['pid']
        vban_reasons = vbans[serverid]['reason']
        vban_groupqqs = vbans[serverid]['groupqq']

        remid, sid, sessionID, access_token  = await get_bf1admin_by_serverid(serverid)
        if not remid:
            continue

        pl_ids = [int(s['id']) for s in pl['1']] + [int(s['id']) for s in pl['2']]
        try:
            bfeac_ids = await bfeac_checkBanMulti(pl_ids)
        except Exception as e:
            logger.warning(f'Vban for server {serverid, gameId} encounter BFEAC network error: {str(e)}')
            continue
        if bfeac_ids and len(bfeac_ids):
            reason = "Banned by bfeac.com"
            for personaId in bfeac_ids:
                tasks.append(upd_kickPlayer(remid,sid,sessionID,gameId,personaId,reason))

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
                        "groupqq": groupqq
                        }
                    )
                tasks.append(upd_kickPlayer(remid,sid,sessionID,gameId,personaId,reason))

    res = await asyncio.gather(*tasks, return_exceptions=True)
    logger.debug(res)
    remid2, sid2, sessionID2, access_token2  = await get_one_random_bf1admin()
    try:
        res_pid = await upd_getPersonasByIds(remid2,sid2,sessionID2,personaIds)
    except:
        res_pid = None

    if res != []:
        bots = nonebot.get_bots()
        for r, report_dict in zip(res, report_list):
            if not isinstance(r, Exception):
                try:
                    gameId = report_dict["gameId"]
                    reason = report_dict["reason"]
                    personaId = report_dict["personaId"]
                    groupqq = report_dict["groupqq"]
                    if not groupqq:
                        continue
                    name = await redis_client.hget(f'draw_dict:{gameId}', "server_name")
                    if not name:
                        name = f'gameid:{gameId}'
                    if res_pid and str(personaId) in res_pid['result']:
                        eaid = res_pid['result'][str(personaId)]['displayName']
                    else:
                        eaid = f'pid:{personaId}'
                    report_msg = f"Vban提示: 在{name}踢出{eaid}, 理由: {reason}"
                    logger.info(report_msg)
                    bot = await getbotforAps(bots,groupqq)
                    reply = await bot.send_group_msg(group_id=groupqq, message=report_msg.rstrip())
                    logger.info(reply)
                except Exception as e:
                    logger.warning(e)
                    continue


async def start_vban(sgids: list, vbans: dict):
    try:
        #pljson = await upd_blazeplforvban([t[1] for t in sgids])
        pljson = await Blaze2788Pro([t[1] for t in sgids])
    except:
        logger.warning(traceback.format_exc(1))
        logger.warning('Vban Blaze error for ' + ','.join([str(t[1]) for t in sgids]))
    else:
        try:
            await kick_vbanPlayer(pljson, sgids,vbans) 
        except RSPException as rsp_exc:
            logger.warning('Vban RSP exception: ' + rsp_exc.echo() + '\n' + ','.join([str(t[1]) for t in sgids]))
        except Exception as e:
            logger.warning(traceback.format_exc(1))
            logger.warning('Vban exception during execution: ' + traceback.format_exception_only(e) + \
                           '\n' + ','.join([str(t[1]) for t in sgids]))

async def upd_vbanPlayer():
    serverid_gameIds = []
    vbans = {}
    async with async_db_session() as session:
        vban_rows = (await session.execute(select(ServerVBans))).all()
        vban_servers = set(r[0].serverid for r in vban_rows)
        for serverid in vban_servers:
            gameId = await get_gameid_from_serverid(serverid)
            is_alive = await redis_client.exists(f'draw_dict:{gameId}')
            if is_alive > 0:
                serverid_gameIds.append((serverid, gameId))
                vbans[serverid] = {'pid':[], 'groupqq': [], 'reason': []}
        for vban_row in vban_rows:
            serverid = vban_row[0].serverid
            if serverid in vbans:
                vbans[serverid]['pid'].append(vban_row[0].pid)
                vbans[serverid]['groupqq'].append(vban_row[0].notify_group)
                vbans[serverid]['reason'].append(vban_row[0].reason)

    if len(serverid_gameIds) == 0:
        return
    sgids = []
    for i in range(len(serverid_gameIds)):
        if len(sgids) < 10:
            sgids.append(serverid_gameIds[i])
        else:
            logger.debug(sgids)
            await start_vban(sgids,vbans)
            #await asyncio.sleep(4) 
            sgids = []
    if 0 < len(sgids) < 10:
        logger.debug(sgids)
        await start_vban(sgids,vbans)


######################################## Schedule jobs #########################################

@scheduler.scheduled_job("interval", minutes=15, id=f"job_reset_alarm_session")
async def bf1_reset_alarm_session():
    alarm_sessions = await load_alarm_session_from_db()
    keys_to_del = [f"alarmamount:{groupqq}" for groupqq in alarm_sessions]
    if len(keys_to_del):
        await redis_client.delete(*keys_to_del)
    logger.info('Alarm session reset')

@scheduler.scheduled_job("interval", hours=2, id=f"job_2")
async def bf1_init_token():
    await token_helper()

@scheduler.scheduled_job("interval", hours=12, id=f"job_3")
async def bf1_init_session():
    await session_helper()

@scheduler.scheduled_job("interval", minutes=1, id=f"job_0", misfire_grace_time=120)
async def bf1_alarm(timeout: int = 20):
    tasks = []

    remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
    await upd_draw(remid,sid,sessionID,timeout)
    logger.info('Update draw dict complete')
    
    start_time = datetime.datetime.now()

    alarm_session_set = await redis_client.smembers('alarmsession')
    for groupqq_b in alarm_session_set:
        groupqq = int(groupqq_b)
        bot = None
        bots = nonebot.get_bots().values()
        for bot in bots:
            try:
                botlist = await bot.get_group_list()
            except:
                continue
            if next((1 for i in botlist if i['group_id']==groupqq), False):
                break
        if not bot:
            continue
        main_groupqq = await check_session(groupqq)
        servers = await get_server_num(main_groupqq)
        for ind, serverid in servers:
            alarm_amount = await redis_client.hget(f'alarmamount:{groupqq}', ind)
            if (not alarm_amount) or (int(alarm_amount) < 3):
                res = await get_server_status(groupqq, ind, serverid, bot)
                if res == 1:
                    await asyncio.sleep(2)
                #tasks.append(asyncio.create_task(get_server_status(groupqq, ind, serverid, bot)))
    if len(tasks) != 0:
        await asyncio.wait(tasks)
    
    end_time = datetime.datetime.now()
    thr_time = (end_time - start_time).total_seconds()
    logger.info(f"预警用时：{thr_time}秒")

@scheduler.scheduled_job("interval", minutes=2, id=f"job_4",max_instances=2)
async def bf1_upd_vbanPlayer():
    start_time = datetime.datetime.now()
    # await upd_ping()
    # await asyncio.sleep(10)

    await upd_vbanPlayer()
    end_time = datetime.datetime.now()
    thr_time = (end_time - start_time).total_seconds()
    logger.info(f"Vban用时：{thr_time}秒")

    # if thr_time % 60 < 30:
    #     await asyncio.sleep(int(31-thr_time))
    #     await upd_ping()
    
    # elif 30 <= thr_time % 60 < 60:
    #     await upd_ping()