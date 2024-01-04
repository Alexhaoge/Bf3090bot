import nonebot

from nonebot.log import logger
from nonebot.params import _command_arg
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment, Bot
from nonebot.typing import T_State

import json
import asyncio
import datetime
import traceback

from nonebot_plugin_apscheduler import scheduler

from sqlalchemy.future import select

from ..bf1draw2 import upd_draw
from ..utils import BF1_SERVERS_DATA
from ..bf1rsp import *
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
        arg = message.extract_plain_text().split(' ')
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


######################################## Schedule job parts #########################################
async def get_server_status(groupqq: int, ind: str, serverid: int, bot: Bot, draw_dict: dict): 
    with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
        zh_cn = json.load(f)
    try:
        gameId = await get_gameid_from_serverid(serverid)
        status = draw_dict[f"{gameId}"]
    except:
        logger.debug(f'No data for gameid:{gameId}')
    else:
        playerAmount = int(status['serverAmount'])
        maxPlayers = int(status['serverMax'])
        map = zh_cn[status['map']]
        #print(playerAmount,maxPlayers,map)
        #print(f'{bot}{session}群{i+1}服人数{playerAmount}')
        try:
            #if True: # Test
            if max(maxPlayers-34,maxPlayers/3) < playerAmount < maxPlayers-10:
                alarm_amount = await redis_client.hincrby(f'alarmamount:{groupqq}', ind)
                await bot.send_group_msg(group_id=groupqq, message=f'第{alarm_amount}次警告：{ind}服人数大量下降到{playerAmount}人，请注意。当前地图为：{map}。')
                return 1
            else:
                return 0
        except:
            logger.error(traceback.format_exc(2))
            return 0

async def kick_vbanPlayer(pljson: dict, sgids: list, vbans: dict, draw_dict: dict):
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
        bfeac_ids = await bfeac_checkBanMulti(pl_ids)
        if bfeac_ids != []:
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
                    name = draw_dict[f"{gameId}"]["server_name"]
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


async def start_vban(sgids: list, vbans: dict, draw_dict: dict):
    try:
        #pljson = await upd_blazeplforvban([t[1] for t in sgids])
        pljson = await Blaze2788Pro([t[1] for t in sgids])
    except:
        logger.warning(traceback.format_exc(1))
        logger.warning('Vban Blaze error for ' + ','.join([str(t[1]) for t in sgids]))
    else:
        try:
            await kick_vbanPlayer(pljson, sgids,vbans,draw_dict) 
        except RSPException as rsp_exc:
            logger.warning('Vban RSP exception: ' + rsp_exc.echo() + '\n' + ','.join([str(t[1]) for t in sgids]))
        except:
            logger.warning(traceback.format_exc(1))
            logger.warning('Vban exception during execution: ' + traceback.format_exception_only() + \
                           '\n' + ','.join([str(t[1]) for t in sgids]))

async def upd_vbanPlayer(draw_dict:dict):
    alive_servers = list(draw_dict.keys())
    serverid_gameIds = []
    vbans = {}
    async with async_db_session() as session:
        vban_rows = (await session.execute(select(ServerVBans))).all()
        vban_servers = set(r[0].serverid for r in vban_rows)
        for serverid in vban_servers:
            gameId = await get_gameid_from_serverid(serverid)
            if str(gameId) in alive_servers:
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
            await start_vban(sgids,vbans,draw_dict)
            #await asyncio.sleep(4) 
            sgids = []
    if 0 < len(sgids) < 10:
        logger.debug(sgids)
        await start_vban(sgids,vbans,draw_dict)


@scheduler.scheduled_job("interval", minutes=15, id=f"job_reset_alarm_session")
async def bf1_reset_alarm_session():
    alarm_sessions = await load_alarm_session_from_db()
    await redis_client.delete(*[f"alarmamount:{groupqq}" for groupqq in alarm_sessions])
    logger.info('Alarm session reset')

@scheduler.scheduled_job("interval", hours=2, id=f"job_2")
async def bf1_init_token():
    await token_helper()

@scheduler.scheduled_job("interval", hours=12, id=f"job_3")
async def bf1_init_session():
    await session_helper()

@scheduler.scheduled_job("interval", minutes=1, id=f"job_0", misfire_grace_time=120)
async def bf1_alarm(timeout: int = 20):
    global draw_dict
    tasks = []

    remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
    draw_dict = await upd_draw(remid,sid,sessionID,timeout)
    logger.info('Update draw dict complete')
    
    start_time = datetime.datetime.now()

    alarm_session_set = await redis_client.smembers('alarmsession')
    for groupqq_b in alarm_session_set:
        groupqq = int(groupqq_b)
        bot = None
        for bot in nonebot.get_bots().values():
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
                res = await get_server_status(groupqq, ind, serverid, bot, draw_dict)
                if res == 1:
                    await asyncio.sleep(2)
                #tasks.append(asyncio.create_task(get_server_status(groupqq, ind, serverid, bot, draw_dict)))
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

    await upd_vbanPlayer(draw_dict)
    end_time = datetime.datetime.now()
    thr_time = (end_time - start_time).total_seconds()
    logger.info(f"Vban用时：{thr_time}秒")

    # if thr_time % 60 < 30:
    #     await asyncio.sleep(int(31-thr_time))
    #     await upd_ping()
    
    # elif 30 <= thr_time % 60 < 60:
    #     await upd_ping()