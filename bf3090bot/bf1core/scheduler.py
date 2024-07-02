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

from ..utils import BF1_SERVERS_DATA, NONEBOT_PORT
from ..bf1rsp import upd_kickPlayer, upd_getPersonasByIds, RSPException
from ..bf1draw import *
from ..secret import *
from ..rdb import *
from ..redis_helper import redis_client
from ..bf1helper import *

from .matcher import BF1_SERVER_ALARM,BF1_SERVER_ALARMOFF,BF1_SERVER_BFEAC,BF1_SERVER_BFEACOFF,BF1_SERVER_BFBAN,BF1_SERVER_BFBANOFF

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
        await BF1_SERVER_ALARM.finish(MessageSegment.reply(event.message_id) + f'群组{groupqq}未初始化')
    admin_perm = await check_admin(groupqq_main, user_id)
    if admin_perm:
        await redis_client.sadd('alarmsession', groupqq)
        async with async_db_session() as session:
            group_r = (await session.execute(select(ChatGroups).filter_by(groupqq=groupqq))).first()
            if group_r[0].alarm:
                await BF1_SERVER_ALARM.finish(f'请不要重复打开')
            else:
                group_r[0].alarm = True
                session.add(group_r[0])
                await session.commit()
                await BF1_SERVER_ALARM.finish(f'已打开预警，请注意接收消息')
    else:
        await BF1_SERVER_ALARM.finish('你不是本群组的管理员')

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
                await BF1_SERVER_ALARMOFF.finish('已关闭预警')
            else:
                await BF1_SERVER_ALARMOFF.finish('本群组未打开预警')
    else:
        await BF1_SERVER_ALARMOFF.finish('你不是本群组的管理员')

@BF1_SERVER_BFEAC.handle()
async def bf1_server_bfeac(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    try:
        arg = message.extract_plain_text().split()
        groupqq = int(arg[0])
    except:
        groupqq = event.group_id
    user_id = event.user_id
    groupqq_main = await check_session(groupqq)
    if not groupqq_main:
        await BF1_SERVER_BFEAC.finish(MessageSegment.reply(event.message_id) + f'群组{groupqq}未初始化')

    servers = await get_server_num(groupqq)
    admin_perm = await check_admin(groupqq_main, user_id)
    if admin_perm:
        async with async_db_session() as session:
            for server_ind, server_id in servers:
                group_r = (await session.execute(select(ServerAutoKicks).filter_by(serverid=server_id))).first()
                if not group_r:
                    session.add(ServerAutoKicks(
                        serverid = server_id,
                        bfeac = True
                    ))
                else:
                    group_r[0].bfeac = True
                    session.add(group_r[0])
            
            await session.commit()
            await BF1_SERVER_BFEAC.finish(f'已打开BFEAC自动踢实锤功能')
    else:
        await BF1_SERVER_BFEAC.finish('你不是本群组的管理员')


@BF1_SERVER_BFEACOFF.handle()
async def bf1_server_bfeacoff(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    try:
        arg = message.extract_plain_text().split()
        groupqq = int(arg[0])
    except:
        groupqq = event.group_id
    user_id = event.user_id
    groupqq_main = await check_session(groupqq)
    if not groupqq_main:
        await BF1_SERVER_BFEACOFF.finish(MessageSegment.reply(event.message_id) + f'群组{groupqq}未初始化')

    servers = await get_server_num(groupqq)
    admin_perm = await check_admin(groupqq_main, user_id)
    if admin_perm:
        async with async_db_session() as session:
            for server_ind, server_id in servers:
                group_r = (await session.execute(select(ServerAutoKicks).filter_by(serverid=server_id))).first()
                if not group_r:
                    session.add(ServerAutoKicks(
                        serverid = server_id,
                        bfeac = False
                    ))
                else:
                    group_r[0].bfeac = False
                    session.add(group_r[0])
            
            await session.commit()
            await BF1_SERVER_BFEACOFF.finish(f'已关闭BFEAC自动踢实锤功能')
    else:
        await BF1_SERVER_BFEACOFF.finish('你不是本群组的管理员')

@BF1_SERVER_BFBAN.handle()
async def bf1_server_bfban(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    try:
        arg = message.extract_plain_text().split()
        groupqq = int(arg[0])
    except:
        groupqq = event.group_id
    user_id = event.user_id
    groupqq_main = await check_session(groupqq)
    if not groupqq_main:
        await BF1_SERVER_BFBAN.finish(MessageSegment.reply(event.message_id) + f'群组{groupqq}未初始化')

    servers = await get_server_num(groupqq)
    admin_perm = await check_admin(groupqq_main, user_id)
    if admin_perm:
        async with async_db_session() as session:
            for server_ind, server_id in servers:
                group_r = (await session.execute(select(ServerAutoKicks).filter_by(serverid=server_id))).first()
                if not group_r:
                    session.add(ServerAutoKicks(
                        serverid = server_id,
                        bfban = True
                    ))
                else:
                    group_r[0].bfban = True
                    session.add(group_r[0])
            
            await session.commit()        
            await BF1_SERVER_BFBAN.finish(f'已打开BFBAN自动踢实锤功能')
    else:
        await BF1_SERVER_BFBAN.finish('你不是本群组的管理员')


@BF1_SERVER_BFBANOFF.handle()
async def bf1_server_bfbanoff(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    try:
        arg = message.extract_plain_text().split()
        groupqq = int(arg[0])
    except:
        groupqq = event.group_id
    user_id = event.user_id
    groupqq_main = await check_session(groupqq)
    if not groupqq_main:
        await BF1_SERVER_BFBANOFF.finish(MessageSegment.reply(event.message_id) + f'群组{groupqq}未初始化')

    servers = await get_server_num(groupqq)
    admin_perm = await check_admin(groupqq_main, user_id)
    if admin_perm:
        async with async_db_session() as session:
            for server_ind, server_id in servers:
                group_r = (await session.execute(select(ServerAutoKicks).filter_by(serverid=server_id))).first()
                if not group_r:
                    session.add(ServerAutoKicks(
                        serverid = server_id,
                        bfban = False
                    ))
                else:
                    group_r[0].bfban = False
                    session.add(group_r[0])
            
            await session.commit()
            await BF1_SERVER_BFBANOFF.finish(f'已关闭BFBAN自动踢实锤功能')
    else:
        await BF1_SERVER_BFBANOFF.finish('你不是本群组的管理员')
######################################## Schedule jobs #########################################

@scheduler.scheduled_job("interval", minutes=1, id=f"job_alarm", misfire_grace_time=120)
async def bf1_alarm(timeout: int = 20):
    start_time = datetime.datetime.now()

    alarm_msgs = await redis_client.xreadgroup(
        streams={'alarmstream': '>'},
        consumername='nonebot',
        groupname=f'cg{NONEBOT_PORT}',
        count=100
    )
    bots = nonebot.get_bots()
    if len(alarm_msgs):
        for id, alarm_msg in alarm_msgs[0][1]:
            await redis_client.xack('alarmstream', f'cg{NONEBOT_PORT}', id)
            groupqq = int(alarm_msg['groupqq'])
            bot = await getbotforAps(bots, groupqq)
            if not bot:
                continue
            amount = alarm_msg['alarm']
            ind = alarm_msg['ind']
            playerAmount = alarm_msg['player']
            mapName = alarm_msg['map']
            await bot.send_group_msg(group_id=groupqq, message=f'第{amount}次警告：{ind}服人数大量下降到{playerAmount}人，请注意。当前地图为：{mapName}。')
            await asyncio.sleep(1)        
    end_time = datetime.datetime.now()
    thr_time = (end_time - start_time).total_seconds()
    logger.info(f"预警消费用时：{thr_time}秒")

@scheduler.scheduled_job("interval", minutes=2, id=f"job_4", misfire_grace_time=120)
async def bf1_upd_vbanPlayer():
    start_time = datetime.datetime.now()

    vban_msgs = await redis_client.xreadgroup(
        streams={'vbanstream': '>'},
        consumername='nonebot',
        groupname=f'cg{NONEBOT_PORT}',
        count=100
    )
    bots = nonebot.get_bots()
    if len(vban_msgs):
        for id, vban_msg in vban_msgs[0][1]:
            await redis_client.xack('vbanstream', f'cg{NONEBOT_PORT}', id)
            groupqq = int(vban_msg['groupqq'])
            bot = await getbotforAps(bots, groupqq)
            if not bot:
                continue
            await bot.send_group_msg(group_id=groupqq, message=vban_msg['msg'])
            await asyncio.sleep(1)        
    end_time = datetime.datetime.now()
    thr_time = (end_time - start_time).total_seconds()
    logger.info(f"Vban消费用时：{thr_time}秒")