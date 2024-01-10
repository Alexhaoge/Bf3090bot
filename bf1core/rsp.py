from nonebot.log import logger
from nonebot.params import _command_arg, ArgStr
from nonebot.adapters.onebot.v11 import Message, MessageSegment, GroupMessageEvent, Bot
from nonebot.typing import T_State

import html
import json
import zhconv
import asyncio
import datetime
import traceback

from sqlalchemy.future import select
from sqlalchemy import func
from pathlib import Path

from ..utils import (
    PREFIX, BF1_SERVERS_DATA,  MapTeamDict,
    getSettings, UpdateDict, UpdateDict_1, ToSettings
)
from ..bf1rsp import *
from ..bf1draw import *
from ..secret import *
from ..image import upload_img
from ..rdb import *
from ..redis_helper import redis_client
from ..bf1helper import *

from .matcher import (
    BF1_F,
    BF1_CHOOSELEVEL,
    BF1_KICK,BF1_KICKALL,
    BF1_BAN,BF1_BANALL,BF1_UNBAN,BF1_UNBANALL,
    BF1_VBAN,BF1_VBANALL,BF1_UNVBAN,BF1_UNVBANALL,
    BF1_MOVE,
    BF1_VIP,BF1_VIPLIST,BF1_CHECKVIP,BF1_UNVIP,
    BF1_PL,BF1_ADMINPL,BF1_PLS,BF1_PLSS,
    BF1_UPD,
    BF1_INSPECT
)

@BF1_F.handle()
async def bf1_fuwuqi(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    logger.debug(message.extract_plain_text())
    mode = 0
    if message.extract_plain_text().startswith(f'{PREFIX}'):
        mode = 2
    else:
        serverName = message.extract_plain_text()
        serverName = html.unescape(serverName)
        mode = 1
    logger.debug(f'mode={mode}')

    remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
    if mode == 1:
        res = await upd_servers(remid, sid, sessionID, serverName)
        try:
            if len(res['result']['gameservers']) == 0:
                await BF1_F.send(MessageSegment.reply(event.message_id) + f'未查询到包含{serverName}关键字的服务器')
            else:
                file_dir = await asyncio.wait_for(draw_server(remid, sid, sessionID, serverName,res), timeout=15)
                await BF1_F.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        except RSPException as rsp_exc:
            await BF1_F.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_F.finish(MessageSegment.reply(event.message_id) + '未查询到数据\n' + traceback.format_exception_only(e))
    if mode == 2:
        groupqq = await check_session(event.group_id)
        servers = await get_server_num(groupqq)
        gameids = []
        for server_ind, server_id in servers:
            gameid = await get_gameid_from_serverid(server_id)
            if gameid:
                gameids.append(gameid)
        try:
            file_dir = await asyncio.wait_for(draw_f(gameids,groupqq,remid, sid, sessionID), timeout=15)
            await BF1_F.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        except RSPException as rsp_exc:
            await BF1_F.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_F.finish(MessageSegment.reply(event.message_id) + '未查询到数据\n' + traceback.format_exception_only(e))


@BF1_CHOOSELEVEL.handle()
async def bf1_chooseLevel(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id
    
    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq, arg[0])
        if not server_ind:
            await BF1_CHOOSELEVEL.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
        mapName = arg[1]
        try:
            with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
                zh_cn = json.load(f)
                mapName = zh_cn[f'{mapName}']
                mapName_cn = zh_cn[f'{mapName}']
        except:
            if mapName != '重开':
                await BF1_CHOOSELEVEL.finish(MessageSegment.reply(event.message_id) + '请输入正确的地图名称')
        gameId = await get_gameid_from_serverid(server_id)
        remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
        if not remid:
            await BF1_CHOOSELEVEL.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        # TODO: record map rotation so that upd_detailedserver is no longer needed. This comes with the advantage that map name translation can be simplified
        serverBL = await upd_detailedServer(remid, sid, sessionID, gameId)
        rotation = serverBL['result']['serverInfo']["rotation"]
        persistedGameId = serverBL['result']['serverInfo']['guid']
        
        if mapName == '重开':
            mapName = serverBL['result']['serverInfo']["mapNamePretty"]
            mapmode = serverBL['result']['serverInfo']["mapModePretty"]
            mapName_cn = mapName
            
            levelIndex = 0
            for i in rotation:
                if i['mapPrettyName'] == mapName and i['modePrettyName'] == mapmode:
                    break
                else:
                    levelIndex += 1      
        else:
            levelIndex = 0

            try:
                mapmode = arg[2]
                mapmode = zh_cn[mapmode]
            except:
                for i in rotation:
                    if zhconv.convert(i['mapPrettyName'],'zh-cn') == mapName_cn:
                        mapmode = i['modePrettyName']
                        break
                    else:
                        levelIndex += 1
            else:
               for i in rotation:
                    if zhconv.convert(i['mapPrettyName'],'zh-cn') == mapName_cn and i['modePrettyName'] == mapmode:
                        break
                    else:
                        levelIndex += 1            
            if levelIndex == len(rotation):
                await BF1_CHOOSELEVEL.finish(MessageSegment.reply(event.message_id) + '未找到此地图，请更新图池')
        try:
            res = await upd_chooseLevel(remid, sid, sessionID, persistedGameId, levelIndex)
        except RSPException as rsp_exc:
            await BF1_CHOOSELEVEL.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_CHOOSELEVEL.finish(MessageSegment.reply(event.message_id) + '未知错误\n' + traceback.format_exception_only(e))
        else:
            admin_logging_helper('map', user_id, event.group_id,
                                 main_groupqq=groupqq, server_ind=server_ind, server_id=server_id, mapName=mapName_cn)
            await BF1_CHOOSELEVEL.send(MessageSegment.reply(event.message_id) + f'地图已切换到：{zhconv.convert(mapmode,"zh-cn")}-{mapName_cn}')
    else:
        await BF1_CHOOSELEVEL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_KICK.handle()
async def bf1_kick(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg1 = message.extract_plain_text().split(' ',maxsplit=2)
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        if reply_message_id(event) == None: # single kick
            server_ind, server_id = await check_server_id(groupqq,arg1[0])
            if not server_ind:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')

            reason = zhconv.convert(arg1[2], 'zh-hant') if len(arg1) > 2 else zhconv.convert('违反规则', 'zh-hant')
            if len(reason.encode('utf-8')) > 32:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '理由过长')
            
            gameId = await get_gameid_from_serverid(server_id)
            remid, sid, sessionID, access_token = await get_bf1admin_by_serverid(server_id)
            if not remid:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + f'bot没有权限，输入.bot查询服管情况。')
            try:
                personaId,name,_ = await getPersonasByName(access_token, arg1[1])
                res = await upd_kickPlayer(remid, sid, sessionID, gameId, personaId, reason)
            except RSPException as rsp_exc:
                await BF1_KICK.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))
            else:
                admin_logging_helper('kick', user_id, event.group_id,
                                     main_groupqq=groupqq, server_ind=server_ind, server_id=server_id, pid=personaId, reason=reason)
                await BF1_KICK.send(MessageSegment.reply(event.message_id) + f'已踢出玩家：{name}，理由：{reason}')

        else: # kick reply to playerlist
            redis_pl = await redis_client.get(f"pl:{groupqq}:{reply_message_id(event)}")
            if not redis_pl:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
            pl_json = json.loads(redis_pl)
            pl = pl_json['pl']
            server_id = pl_json['serverid'] # Playerlist cache will store serverid instead of server_ind
            slots = []
            personaIds = []
            mode = 0

            gameId = await get_gameid_from_serverid(server_id)
            remid, sid, sessionID, _ = await get_bf1admin_by_serverid(server_id)
            if not remid:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            # TODO: improve branching with on_shellcommand argument parser
            if arg[0].startswith('rank>'):
                reason = f'rank limit {arg[0].split(">")[1]}'
                for i in pl:
                    if i['rank'] > int(arg[0].split(">")[1]):
                        personaIds.append(i['id'])
            elif arg[0].startswith('rank大于'):
                reason = f'rank limit {arg[0].split("大于")[1]}'
                for i in pl:
                    if i['rank'] > int(arg[0].split("大于")[1]):
                        personaIds.append(i['id'])
            elif arg[0].startswith('kd>'):
                reason = f'kd limit {arg[0].split(">")[1]}'
                for i in pl:
                    if i['kd'] > float(arg[0].split(">")[1]):
                        personaIds.append(i['id'])
            elif arg[0].startswith('kd大于'):
                reason = f'kd limit {arg[0].split("大于")[1]}'
                for i in pl:
                    if i['kd'] > float(arg[0].split("大于")[1]):
                        personaIds.append(i['id'])
            elif arg[0].startswith('kp大于'):
                reason = f'kp limit {arg[0].split("大于")[1]}'
                for i in pl:
                    if i['kp'] > float(arg[0].split("大于")[1]):
                        personaIds.append(i['id'])
            elif arg[0].startswith('kp>'):
                reason = f'kp limit {arg[0].split(">")[1]}'
                for i in pl:
                    if i['kp'] > float(arg[0].split(">")[1]):
                        personaIds.append(i['id'])
            elif arg[0] == 'all':
                mode = 1
                reason = zhconv.convert(' '.join(arg[1:]) if len(arg)>1 else '清服', 'zh-hant')
                for i in pl:
                    if i['id']!=0:
                        personaIds.append(i['id'])
                    print(personaIds)
            else:
                if arg[-1].isdigit():
                    reason = zhconv.convert('违反规则', 'zh-hant')
                    slots = arg
                else:
                    slots = arg[:-1]
                    reason = zhconv.convert(arg[-1], 'zh-hant')
                if not slots[0].isdigit(): # remove command prefix, .k,.kick,etc.
                    slots.pop(0)
                if not all(map(str.isdigit, slots)):
                    await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '联动踢出规则不合法。\n.k [序号] [理由] 或 .k [rank/kd/kp>数值] 或.k all [理由]')
                slots = set(map(int, slots))

                for i in pl:
                    if i['slot'] in slots:
                        personaIds.append(i['id'])

            if len(reason.encode('utf-8')) > 32:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '理由过长')
            tasks = [
                asyncio.create_task(upd_kickPlayer(remid, sid, sessionID, gameId, i, reason))
                for i in personaIds
            ]

            res = await asyncio.gather(*tasks, return_exceptions=True)
            cnt = 0
            for r, pid in zip(res, personaIds):
                if not isinstance(res, Exception):
                    cnt += 1
                    admin_logging_helper('kickall' if arg[0] == 'all' else 'kick', user_id, event.group_id, 
                                         main_groupqq=groupqq, server_ind=pl_json['serverind'],
                                         server_id=server_id, pid=pid, reason=reason)
            await BF1_KICK.send(MessageSegment.reply(event.message_id) + f'已踢出{cnt}个玩家，理由：{reason}')
    else:
        await BF1_KICK.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_KICKALL.handle()
async def bf1_kickall(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',maxsplit=1)
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
        try:
            reason = zhconv.convert(arg[1], 'zh-hant')
        except:
            reason = zhconv.convert('管理员进行了清服', 'zh-hant')
        if len(reason.encode('utf-8')) > 32:
            await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + '理由过长')

        gameId = await get_gameid_from_serverid(server_id)  
        try:        
            pl = await upd_blazepl(gameId)
        except:
            await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + '服务器未开启')
        state["playerlist"] = pl
        state["gameId"] = gameId
        state["server_ind"] = server_ind
        state["groupqq"] = groupqq
        state["serverid"] = server_id # also store server_id  for easier access to bf1admin account
        state["reason"] = reason
    else:
        await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_KICKALL.got("msg", prompt="发送确认以踢出服务器内所有玩家，发送其他内容以取消操作。")
async def get_kickall(bot: Bot, event: GroupMessageEvent, state: T_State, msg: Message = ArgStr("msg")): 
    if msg == "确认":
        pl = state["playerlist"] 
        gameId = state["gameId"]
        server_id = state["serverid"]
        reason = state["reason"]
        groupqq = state["groupqq"]
        server_ind = state['server_ind']
        remid,sid,sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
        if not remid:
            await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        pl_both = pl['1'] + pl['2']
        tasks = [
            asyncio.create_task(upd_kickPlayer(remid, sid, sessionID, gameId, i['id'], reason)) for i in pl_both
        ]
        res = await asyncio.gather(*tasks, return_exceptions=True)
        
        cnt = 0
        for i, r in zip(pl_both, res):
            if not isinstance(r, Exception):
                cnt += 1
                admin_logging_helper('kickall', event.user_id, event.group_id, 
                                    main_groupqq=groupqq, server_ind=server_ind,
                                    server_id=server_id, pid=i['id'], reason=reason)
                
        await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + f'已踢出{cnt}个玩家,理由: {reason}')          
    else:
        await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + '已取消操作。')

@BF1_BAN.handle()
async def bf1_ban(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',maxsplit=2)
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        # Single ban command
        if reply_message_id(event) == None:
            server_ind, server_id = await check_server_id(groupqq,arg[0])
            if not server_ind:
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
            personaName = arg[1]
            try:
                reason = zhconv.convert(arg[2], 'zh-tw')
            except:
                reason = zhconv.convert('违反规则', 'zh-tw')

            if len(reason.encode('utf-8')) > 32:
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + '理由过长')

            gameId = await get_gameid_from_serverid(server_id)
            remid,sid,sessionID,access_token = (await get_bf1admin_by_serverid(server_id))
            if not remid:
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            try:
                personaId,personaName,_ = await getPersonasByName(access_token, personaName)
                res = await upd_kickPlayer(remid, sid, sessionID, gameId, personaId, reason)
                res = await upd_banPlayer(remid, sid, sessionID, server_id, personaId)
            except RSPException as rsp_exc:
                await BF1_BAN.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))
            else:
                admin_logging_helper('ban', user_id, event.group_id, 
                                     main_groupqq=groupqq, server_ind=server_ind,
                                     server_id=server_id, pid=personaId, reason=reason)
                await BF1_BAN.send(MessageSegment.reply(event.message_id) + f'已封禁玩家：{personaName}，理由：{reason}')
        # Reply to playerlist
        else:
            redis_pl = await redis_client.get(f"pl:{groupqq}:{reply_message_id(event)}")
            if not redis_pl:
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
            pl_json = json.loads(redis_pl)
            pl = pl_json['pl']
            server_id = pl_json['serverid'] # Playerlist cache will store serverid instead of server_ind
            gameId = await get_gameid_from_serverid(server_id)
            if len(arg) > 1:
                reason = zhconv.convert(arg[1], 'zh-tw')
            else:
                reason = zhconv.convert('违反规则', 'zh-tw')

            if len(reason.encode('utf-8')) > 32:
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + '理由过长')

            personaIds = []
            for i in pl:
                if int(i['slot']) == int(arg[0]):
                    personaId = i['id']
                    personaIds.append(personaId)
                    break
            
            remid,sid,sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            if not remid:
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            try:
                res = await upd_getPersonasByIds(remid, sid, sessionID, personaIds)
                personaName = res['result'][f'{personaId}']['displayName']    
                res = await upd_kickPlayer(remid, sid, sessionID, gameId, personaId, reason)
                res = await upd_banPlayer(remid, sid, sessionID, server_id, personaId)
            except RSPException as rsp_exc:
                await BF1_BAN.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + '未知错误\n' + traceback.format_exception_only(e))
            else:
                admin_logging_helper('ban', user_id, event.group_id, main_groupqq=groupqq,
                                     server_ind=pl_json['serverind'], server_id=server_id, pid=personaId, reason=reason)
                await BF1_BAN.send(MessageSegment.reply(event.message_id) + f'已封禁玩家：{personaName}，理由：{reason}')
    else:
        await BF1_BAN.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_BANALL.handle()
async def bf1_banall(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        personaName = arg[0]
        try:
            reason = zhconv.convert(arg[1], 'zh-tw')
        except:
            reason = zhconv.convert('违反规则', 'zh-tw')
        if len(reason.encode('utf-8')) > 32:
            await BF1_BANALL.finish(MessageSegment.reply(event.message_id) + '理由过长')

        servers = await get_server_num(groupqq)
        tasks = []
        access_token = (await get_one_random_bf1admin())[3]
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
        except RSPException as rsp_exc:
            await BF1_BANALL.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_BANALL.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))
        
        messages = []
        valid_serverinds = []
        for server_ind, server_id in servers:
            #gameId = await get_gameid_from_serverid(server_id)
            remid,sid,sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            if remid:
                tasks.append(asyncio.create_task(upd_banPlayer(remid, sid, sessionID, server_id, personaId)))
                valid_serverinds.append(server_ind)
            else:
                messages.append(f'bot没有服务器#{server_ind}管理权限')
        
        res = await asyncio.gather(*tasks, return_exceptions=True)
        admin_logging_helper('banall', user_id, event.group_id,
                             main_groupqq=groupqq, pid=personaId, reason=reason)
        
        for r, server_ind in zip(res, valid_serverinds):
            if isinstance(r, Exception):
                messages.append(f'在{server_ind}服封禁玩家失败:{r.echo() if isinstance(r, RSPException) else str(r)}')
            else:
                messages.append(f'在{server_ind}封禁玩家：{personaName}，理由：{reason}')
        await BF1_BANALL.send(MessageSegment.reply(event.message_id) + '\n'.join(messages))
    else:
        await BF1_BANALL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_UNBANALL.handle()
async def bf1_unbanall(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        personaName = arg[0]

        servers = await get_server_num(groupqq)
        tasks = []
        access_token = (await get_one_random_bf1admin())[3]
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
        except RSPException as rsp_exc:
            await BF1_UNBANALL.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_UNBANALL.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))
        
        messages = []
        valid_serverinds = []
        for server_ind, server_id in servers:
            #gameid = await get_gameid_from_serverid(server_id)
            remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            if remid:                 
                tasks.append(asyncio.create_task(upd_unbanPlayer(remid, sid, sessionID, server_id, personaId)))
                valid_serverinds.append(server_ind)
            else:
                messages.append(f'bot没有服务器#{server_ind}管理权限')
        
        res = await asyncio.gather(*tasks, return_exceptions=True)
        admin_logging_helper('unbanall', user_id, event.group_id, main_groupqq=groupqq, pid=personaId)
        
        for r, server_ind in zip(res, valid_serverinds):
            if isinstance(r, Exception):
                messages.append(f'在{server_ind}服解封玩家{personaName}失败:{r.echo() if isinstance(r, RSPException) else str(r)}')
            else:
                messages.append(f'已在{server_ind}解封禁玩家{personaName}')
        await BF1_UNBANALL.send(MessageSegment.reply(event.message_id) + '\n'.join(messages))
    else:
        await BF1_UNBANALL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_UNBAN.handle()
async def bf1_unban(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_UNBAN.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
        personaName = arg[1]
        # reason = zhconv.convert(arg[2], 'zh-tw')
        # gameid = await get_gameid_from_serverid(server_id)
        remid,sid,sessionID,access_token = await get_bf1admin_by_serverid(server_id)
        if not remid:
            await BF1_UNBAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
            await upd_unbanPlayer(remid, sid, sessionID, server_id, personaId)
        except RSPException as rsp_exc:
            await BF1_UNBAN.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_UNBAN.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))
        else:
            admin_logging_helper('unban', user_id, event.group_id, main_groupqq=groupqq,
                                 server_ind=server_ind, server_id=server_id, pid=personaId)
            await BF1_UNBAN.send(MessageSegment.reply(event.message_id) + f'已解封玩家：{personaName}')
    else:
        await BF1_UNBAN.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_VBAN.handle()
async def bf1_vban(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',maxsplit=2)
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        if reply_message_id(event) == None:
            server_ind, server_id = await check_server_id(groupqq,arg[0])
            if not server_ind:
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
            
            if len(arg) > 2:
                reason = 'Vban:' + zhconv.convert(arg[2], 'zh-tw')
            else:
                reason = 'Vbanned by admin'
            if len(reason.encode('utf-8')) > 32:
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + '理由过长')

            personaName = arg[1]
            # gameId = await get_gameid_from_serverid(server_id)
            remid,sid,sessionID,access_token = await get_bf1admin_by_serverid(server_id)
            if not remid:
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            try:
                personaId,personaName,_ = await getPersonasByName(access_token, personaName)
                await add_vban(personaId,groupqq,server_id,reason,user_id)
            except RSPException as rsp_exc:
                await BF1_VBAN.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))

            admin_logging_helper('vban', user_id, event.group_id, main_groupqq=groupqq,
                                 server_ind=server_ind, server_id=server_id, pid=personaId, reason=reason)
            await BF1_VBAN.send(MessageSegment.reply(event.message_id) + f'已在{server_ind}服为玩家{personaName}添加VBAN，理由：{reason}')
        else:
            redis_pl = await redis_client.get(f"pl:{groupqq}:{reply_message_id(event)}")
            if not redis_pl:
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
            pl_json = json.loads(redis_pl)
            pl = pl_json['pl']
            server_id = pl_json['serverid'] # Playerlist cache will store serverid instead of server_ind
            if len(arg) > 1:
                reason = 'Vban:' + zhconv.convert(arg[1], 'zh-tw')
            else:
                reason = 'Vbanned by admin'
            if len(reason.encode('utf-8')) > 32:
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + '理由过长')
            personaId = None
            for i in pl:
                if int(i['slot']) == int(arg[0]):
                    personaId = i['id']
                    break
            if not personaId:
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + '请输入正确的玩家序号')
            remid,sid,sessionID,access_token = await get_bf1admin_by_serverid(server_id)
            if not remid:
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            try:
                res = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
                personaName = res['result'][f'{personaId}']['displayName']
                await add_vban(personaId,groupqq,server_id,reason,user_id)
                admin_logging_helper('vban', user_id, event.group_id, pl_json['serverind'], server_id, personaId, reason=reason)
                await BF1_VBAN.send(MessageSegment.reply(event.message_id) + f'已在{server_id}为玩家{personaName}添加VBAN，理由：{reason}')
            except RSPException as rsp_exc:
                await BF1_VBAN.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + '未知错误\n' + traceback.format_exception_only(e))
    else:
        await BF1_VBAN.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_VBANALL.handle()
async def bf1_vbanall(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        personaName = arg[0]
        if len(arg) > 1:
            reason = 'Vban:' + zhconv.convert(arg[1], 'zh-tw')
        else:
            reason = 'Vbanned by admin'

        if len(reason.encode('utf-8')) > 32:
            await BF1_VBANALL.finish(MessageSegment.reply(event.message_id) + '理由过长')
        servers = await get_server_num(groupqq)
        access_token = (await get_one_random_bf1admin())[3]
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
        except RSPException as rsp_exc:
            await BF1_VBANALL.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_VBANALL.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))

        err_message = ''
        for server_ind, server_id in servers:
            remid,sid,sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            if remid:
                await add_vban(personaId,groupqq,server_id,reason,user_id)
            else:
                err_message += f'\nbot没有服务器#{server_ind}管理权限'
        admin_logging_helper('vbanall', user_id, event.group_id, main_groupqq=groupqq, pid=personaId, reason=reason)
        await BF1_VBANALL.send(MessageSegment.reply(event.message_id) + f'已封禁玩家：{personaName}，理由：{reason}{err_message}')
    else:
        await BF1_VBANALL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_UNVBANALL.handle()
async def bf1_unvbanall(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        personaName = arg[0]

        servers = await get_server_num(groupqq)
        access_token = (await get_one_random_bf1admin())[3]
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
        except RSPException as rsp_exc:
            await BF1_UNVBANALL.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_UNVBANALL.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))

        err_message = ''
        for server_ind, server_id in servers:
            remid,sid,sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            if remid:
                await del_vban(personaId, server_id)
            else:
                err_message += f'\nbot没有服务器#{server_ind}管理权限'
        admin_logging_helper('unvbanall', event.user_id, event.group_id, main_groupqq=groupqq, pid=personaId)
        await BF1_UNVBANALL.send(MessageSegment.reply(event.message_id) + f'已解封玩家：{personaName}{err_message}')
    else:
        await BF1_UNVBANALL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_UNVBAN.handle()
async def bf1_unvban(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
                await BF1_UNVBAN.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')

        personaName = arg[1]
        gameId = await get_gameid_from_serverid(server_id)
        remid,sid,sessionID,access_token = await get_bf1admin_by_serverid(server_id)
        if not remid:
            await BF1_UNVBAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
        except RSPException as rsp_exc:
            await BF1_UNVBAN.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_UNVBAN.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))

        await del_vban(personaId, server_id)
        admin_logging_helper('unvban', event.user_id, event.group_id, main_groupqq=groupqq,
                             server_ind=server_ind, serverid=server_id, pid=personaId)
        await BF1_UNVBAN.send(MessageSegment.reply(event.message_id) + f'已在{server_id}解除玩家{personaName}的VBAN')
    else:
        await BF1_UNVBAN.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_MOVE.handle()
async def bf1_move(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        if reply_message_id(event) == None:
            server_ind, server_id = await check_server_id(groupqq,arg[0])
            if not server_ind:
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
            personaName = arg[1]
            gameId = await get_gameid_from_serverid(server_id)
            remid,sid,sessionID,access_token = await get_bf1admin_by_serverid(server_id)
            if not remid:
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            try:
                personaId,personaName,_ = await getPersonasByName(access_token, personaName)
            except RSPException as rsp_exc:
                await BF1_MOVE.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))

            try:
                pl = await upd_blazepl(gameId)
                mapName = MapTeamDict[f'{pl["map"]}']['Chinese']
                teamId = 0
                for i in pl['1']:
                    if int(i['id']) == int(personaId):
                        teamId = 1
                        break

                for j in pl['2']:
                    if int(j['id']) == int(personaId):
                        teamId = 2
                        break

                if teamId == 1:
                    teamName = pl['team2']
                elif teamId == 2:
                    teamName = pl['team1']
                else:
                    await BF1_MOVE.send(MessageSegment.reply(event.message_id) + '移动失败,玩家不在服务器中')
                    return
            except:
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + 'API HTTP ERROR，请稍后再试')
            
            try:
                res = await upd_movePlayer(remid, sid, sessionID, gameId, personaId, teamId)
            except RSPException as rsp_exc:
                await BF1_MOVE.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + '未知错误\n' + traceback.format_exception_only(e))
            else:
                with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
                    zh_cn = json.load(f)
                admin_logging_helper('move', event.user_id, event.group_id, main_groupqq=groupqq,
                                     server_ind=server_ind, server_id=server_id, pid=personaId)
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + f'已移动玩家{personaName}至队伍{3-teamId}：{zh_cn[teamName]}')
        
        else:
            redis_pl = await redis_client.get(f"pl:{groupqq}:{reply_message_id(event)}")
            if not redis_pl:
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
            pl_json = json.loads(redis_pl)
            pl = pl_json['pl']
            server_id = pl_json['serverid'] # Playerlist cache will store serverid instead of server_ind
            teamIds = []
            personaIds = []
            players_to_move = set((int(i) if i.isdigit() else -1 for i in arg))
            for i in pl:
                if int(i['slot']) in players_to_move:
                    personaIds.append(i['id'])
                    if int(i['slot']) < 33:
                        teamIds.append(1)
                    else:
                        teamIds.append(2)

            gameId = await get_gameid_from_serverid(server_id)
            remid,sid,sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            if not remid:
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            cnt = 0
            error_message = ''
            for i in range(len(personaIds)):
                try:
                    res = await upd_movePlayer(remid, sid, sessionID, gameId, personaIds[i], teamIds[i])
                    cnt += 1
                except RSPException as rsp_exc:
                    error_message = rsp_exc.echo()
                    break
                except Exception as e:
                    error_message = traceback.format_exception_only(e)
                    break
                else:
                    admin_logging_helper('move', event.user_id, event.group_id, main_groupqq=groupqq,
                                         server_ind=pl_json['serverind'], server_id=server_id, pid=personaIds[i])
            await BF1_MOVE.send(MessageSegment.reply(event.message_id) + f'已移动{cnt}个玩家。{error_message}')
    else:
        await BF1_MOVE.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_VIP.handle()
async def bf1_vip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        if reply_message_id(event) == None:
            server_ind, server_id = await check_server_id(groupqq,arg[0])
            if not server_ind:
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
            personaName = arg[1]
            access_token = (await get_one_random_bf1admin())[3]
            try:
                personaId,personaName,_ = await getPersonasByName(access_token, personaName)
            except RSPException as rsp_exc:
                await BF1_VIP.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_VIP.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n'+ traceback.format_exception_only(e))
            if len(arg) > 2:
                permanent, days = False, int(arg[2])
                priority = int(arg[3]) if len(arg) > 3 else 1
            else:
                permanent, days, priority = True, 0, 1
        else:
            redis_pl = await redis_client.get(f"pl:{groupqq}:{reply_message_id(event)}")
            if not redis_pl:
                await BF1_VIP.finish(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
            pl_json = json.loads(redis_pl)
            pl = pl_json['pl']
            server_id = pl_json['serverid'] # Playerlist cache will store serverid instead of server_ind
            server_ind = pl_json['serverind']
            personaId = None
            for i in pl:
                if int(i['slot']) == int(arg[0]):
                    personaId = i['id']
                    break
            if not personaId:
                await BF1_VIP.finish(MessageSegment.reply(event.message_id) + '玩家序号错误')
            remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            try:
                res = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
                personaName = res['result'][f'{personaId}']['displayName']
            except RSPException as rsp_exc:
                await BF1_VIP.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_VIP.finish(MessageSegment.reply(event.message_id) + '未知错误\n' + traceback.format_exception_only(e))

            if len(arg) > 1:
                permanent, days = False, int(arg[1])
                priority = int(arg[2]) if len(arg) > 2 else 1
            else:
                permanent, days, priority = True, 0, 1

        async with async_db_session() as session:
            exist_vip = (await session.execute(
                select(ServerVips).filter_by(serverid=server_id, pid=personaId)
            )).first()
            if exist_vip: # If vip exists, update the current vip
                if exist_vip[0].permanent:
                    await BF1_VIP.send(MessageSegment.reply(event.message_id) + '玩家已是永久VIP')
                    return
                exist_vip[0].days += days
                exist_vip[0].permanent |= permanent
                exist_vip[0].priority = max(exist_vip[0].priority, priority)
                session.add(exist_vip[0])
                await session.commit()
                if exist_vip[0].enabled:
                    expire_date = exist_vip[0].start_date + datetime.timedelta(days=exist_vip[0].days)
                    nextday = datetime.datetime.strftime(expire_date, "%Y-%m-%d")
                    msg = f"已为玩家{personaName}添加" + ("永久vip" if exist_vip[0].permanent else f"{days}天的vip({nextday})")
                else:
                    msg = f"已为玩家{personaName}添加" + ("永久vip" if exist_vip[0].permanent else f"{days}天的vip") + "(未生效)"
                await BF1_VIP.send(MessageSegment.reply(event.message_id) + msg)
            else: # If vip does not exists, create a new record
                remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
                if not remid:
                    await BF1_VIP.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
                try:
                    gameid = await get_gameid_from_serverid(server_id)
                    serverBL = await upd_detailedServer(remid, sid, sessionID, gameid)
                    is_operation_server = serverBL['result']['serverInfo']['mapMode'] == 'BreakthroughLarge'
                except RSPException as rsp_exc:
                    await BF1_VIP.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
                    return
                except Exception as e:
                    logger.warning(traceback.format_exc())
                    await BF1_VIP.finish(MessageSegment.reply(event.message_id) + '未知错误\n' + traceback.format_exception_only(e))
                # Add to db (not committed yey)
                new_vip = ServerVips(
                    serverid = server_id, pid = personaId, originid = personaName,
                    days = days, permanent = permanent, enabled = False, priority = priority
                )
                # For operation servers, do not send vip request immediately, set enabled to False and add to database
                if is_operation_server:
                    msg = f'已为玩家{personaName}添加' + ('永久' if new_vip.permanent else f'{days}天的') + 'vip(行动模式，未生效)'
                    session.add(new_vip)
                    await session.commit()
                    await BF1_VIP.send(MessageSegment.reply(event.message_id) + msg)
                elif len(serverBL['result']['rspInfo']['vipList']) >= 50:
                    msg = f'已为玩家{personaName}添加' + ('永久' if new_vip.permanent else f'{days}天的') + 'vip(未生效)\n' +\
                        '服务器VIP位已满，请使用.checkvip/.unvip，或手动删除vip'
                    session.add(new_vip)
                    await session.commit() 
                    await BF1_VIP.send(MessageSegment.reply(event.message_id) + msg)
                # For other servers, send vip request immediately, set enabled to True
                else:
                    try:
                        res = await upd_vipPlayer(remid, sid, sessionID, server_id, personaId)
                    # If request failed, roll back transaction
                    except RSPException as rsp_exc:
                        await session.rollback()
                        await BF1_VIP.finish(MessageSegment.reply(event.message_id) + f'添加失败：{rsp_exc.echo()}')
                    except Exception as e:
                        await session.rollback()
                        logger.warning(traceback.format_exc())
                        await BF1_VIP.finish(MessageSegment.reply(event.message_id) + f'添加失败：{traceback.format_exception_only(e)}')
                    # Request success then commit
                    else:
                        new_vip.enabled = True
                        new_vip.start_date = datetime.datetime.now()
                        nextday = datetime.datetime.strftime(new_vip.start_date + datetime.timedelta(days=new_vip.days), "%Y-%m-%d")
                        msg = f"已为玩家{personaName}添加" + ("永久vip" if new_vip.permanent else f"{days}天的vip({nextday})")
                        session.add(new_vip)
                        await session.commit()
                        await BF1_VIP.send(MessageSegment.reply(event.message_id) + msg)
        admin_logging_helper('vip', event.user_id, event.group_id, main_groupqq=groupqq,
                             server_ind=server_ind, server_id=server_id, pid=personaId, day=days, permanent=permanent, priority=priority)
    else:
        await BF1_VIP.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_VIPLIST.handle()
async def bf1_viplist(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
        dt_now = datetime.datetime.now()
        async with async_db_session() as session:
            vip_rows = (await session.execute(select(ServerVips).filter_by(serverid=server_id))).all()
            viplist = []
            for i, row in enumerate(vip_rows):
                vip_str = f"{i+1}.{row[0].originid}"
                if not row[0].enabled:
                    vip_str += ('永久' if row[0].permanent else f'({row[0].days}天)') + '(未生效)'
                elif row[0].permanent:
                    vip_str += '(永久)'
                else:
                    expire_date = row[0].start_date + datetime.timedelta(days=row[0].days)
                    if expire_date < dt_now:
                        vip_str += '(已过期)'
                    else:
                        vip_str += f"({datetime.datetime.strftime(expire_date, '%Y-%m-%d')})"
                viplist.append(vip_str)
            msg = '只展示通过本bot添加的vip:\n' + '\n'.join(viplist) 
        
        await BF1_VIPLIST.send(MessageSegment.reply(event.message_id) + msg)
    else:
        await BF1_VIPLIST.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_CHECKVIP.handle()
async def bf1_checkvip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = await check_session(event.group_id)

    admin_perm = await check_admin(session, event.user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(session,arg[0])
        if not server_ind:
            await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')

        gameid = await get_gameid_from_serverid(server_id)
        remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
        if not remid:
            await BF1_CHECKVIP.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')

        try:
            serverBL = await upd_detailedServer(remid, sid, sessionID, gameid)
        except RSPException as rsp_exc:
            await BF1_VIP.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_VIP.finish(MessageSegment.reply(event.message_id) + '未知错误\n' + traceback.format_exception_only(e))
        
        n_add = n_remove = n_pending = 0
        err_names = []
        now_dt = datetime.datetime.now()
        
        async_tasks = []
        async with async_db_session() as session:
            # Find all vips to enable, permanent + temporary order by priority
            pending_enable = (await session.execute(select(ServerVips).filter_by(serverid=server_id, enabled=False, permanent=True))).all()
            pending_enable.extend((await session.execute(
                select(ServerVips).filter_by(
                    serverid=server_id, enabled=False, permanent=False).order_by(ServerVips.priority.desc())
            )).all())

            # Find all vips to expire
            activated = (await session.execute(select(ServerVips).filter_by(serverid=server_id, permanent=False, enabled=True))).all()
            pending_expire = list(filter(lambda v: v[0].start_date + datetime.timedelta(v[0].days) < now_dt, activated))
            
            # Execute expiration first
            async_tasks = [asyncio.create_task(upd_unvipPlayer(remid,sid,sessionID,server_id,v[0].pid)) for v in pending_expire]
            results = await asyncio.gather(*async_tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.warning(str(res))
                    err_names.append(pending_expire[i][0].originid)
                else:
                    n_remove += 1
                    await session.delete(pending_expire[i][0])
            
            # Execute activation
            n_expected_to_enable = 50 - len(serverBL['result']['rspInfo']['vipList']) + n_remove
            n_expected_to_enable = min(len(pending_enable), max(n_expected_to_enable, 0))
            
            async_tasks = [asyncio.create_task(upd_vipPlayer(remid,sid,sessionID,server_id,v[0].pid))\
                            for v in pending_enable[:n_expected_to_enable]]
            results = await asyncio.gather(*async_tasks, return_exceptions=True)

            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.warning(str(res))
                    err_names.append(pending_enable[i][0].originid)
                else:
                    n_add += 1
                    pending_enable[i][0].enabled = True
                    pending_enable[i][0].start_date = now_dt
                    session.add(pending_enable[i][0])
            await session.commit()

        msg = f"已添加{n_add}个vip，删除{n_remove}个vip\n" +\
            f"{len(pending_enable)-n_expected_to_enable}个vip尚在等待生效，{len(err_names)}个vip处理失败"
        if len(err_names):
            msg = msg + ':\n' + '\n'.join(err_names)
        await BF1_CHECKVIP.send(MessageSegment.reply(event.message_id) + msg)
    else:
        await BF1_CHECKVIP.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_UNVIP.handle()
async def bf1_unvip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
        personaName = arg[1]
        remid, sid, sessionID, access_token = await get_bf1admin_by_serverid(server_id)
        if not remid:
            await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
            gameid = await get_gameid_from_serverid(server_id)
            serverBL = await upd_detailedServer(remid, sid, sessionID, gameid)
            is_operation = serverBL['result']['serverInfo']['mapMode'] == 'BreakthroughLarge'
        except RSPException as rsp_exc:
            await BF1_UNVIP.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + '玩家id错误\n' + traceback.format_exception_only(e))
        
        async with async_db_session() as session:
            vip = (await session.execute(select(ServerVips).filter_by(serverid=server_id, pid=personaId))).first()
            if vip:
                if is_operation: 
                    if vip[0].enabled:
                        # Enabled vip in operation server will not be requested or deleted immediated, we only set it to expired in database
                        vip[0].days = -1
                        vip[0].permanent = False
                        session.add(vip[0])
                        await session.commit()
                        await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + f'已移除玩家{personaName}的行动vip(需要check)')
                    else:
                        # Vip in operation server that does not come into effect will be deleted
                        await session.delete(vip[0])
                        await session.commit()
                        await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + f'已移除玩家{personaName}未生效的行动vip(不需要check)')
                else: # For regular server, we immediately delete from both database and server. Commit after `upd_unvipPlayer` succeeds.
                    await session.delete(vip[0])
            else:
                if is_operation:
                    await BF1_UNVIP.send(MessageSegment.reply(event.message_id) + f'您正在尝试删除未在bot数据库内的行动vip，请在删除完成后立刻进行切图处理！')

            try:
                await upd_unvipPlayer(remid, sid, sessionID, server_id, personaId)
            except RSPException as rsp_exc:
                await session.rollback()
                await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            except Exception as e:
                await session.rollback()
                logger.warning(traceback.format_exc())
                await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + '移除VIP失败\n' + traceback.format_exception_only(e))
            else:
                await session.commit()
                await BF1_UNVIP.send(MessageSegment.reply(event.message_id) + f'已移除玩家{personaName}的vip')
        admin_logging_helper('unvip', event.user_id, event.group_id, main_groupqq=groupqq,
                             server_ind=server_ind, server_id=server_id, pid=personaId, operation_server=is_operation)
    else:
        await BF1_UNVIP.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_PL.handle()
async def bf_pl(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_PL.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]

        gameId = await get_gameid_from_serverid(server_id)
        try:
            file_dir, pl_cache = await asyncio.wait_for(draw_pl2(groupqq, server_ind, server_id, gameId, remid, sid, sessionID), timeout=20)
            reply = await BF1_PL.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
            await redis_client.set(f"pl:{groupqq}:{reply['message_id']}", pl_cache, ex=1800)
        except asyncio.TimeoutError:
            await BF1_PL.send(MessageSegment.reply(event.message_id) + '连接超时')
        except RSPException as rsp_exc:
            await BF1_PL.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_PL.finish(MessageSegment.reply(event.message_id) + '获取服务器玩家列表失败，可能是服务器未开启')

    else:
        await BF1_PL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')  

@BF1_ADMINPL.handle()
async def bf_adminpl(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    server = html.unescape(message.extract_plain_text())
    main_groupqq = await check_session(event.group_id)

    if check_sudo(event.group_id, event.user_id):
        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
        try:
            result = await upd_servers(remid, sid, sessionID, server)
            gameId = result['result']['gameservers'][0]['gameId']
            serverBL = await upd_detailedServer(remid, sid, sessionID, gameId)
            serverid = serverBL['result']['rspInfo']['server']['serverId']
        except: 
            await BF1_ADMINPL.finish('无法获取到服务器数据。')
        try:
            file_dir, pl_cache = await asyncio.wait_for(draw_pl2(main_groupqq, 'adminpl', serverid, gameId, remid, sid, sessionID), timeout=20)
            reply = await BF1_ADMINPL.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
            await redis_client.set(f"pl:{main_groupqq}:{reply['message_id']}", pl_cache, ex=1800)
        except asyncio.TimeoutError:
            await BF1_ADMINPL.send(MessageSegment.reply(event.message_id) + '连接超时')
        except RSPException as rsp_exc:
            await BF1_ADMINPL.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_ADMINPL.finish(MessageSegment.reply(event.message_id) + '获取服务器玩家列表失败，可能是服务器未开启')
 
@BF1_PLS.handle()
async def bf_pls(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_PLS.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
        gameId = await get_gameid_from_serverid(server_id)
        remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
        if not remid:
            await BF1_PLS.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')

        try:
            file_dir = await asyncio.wait_for(draw_platoons(remid, sid, sessionID, gameId,1), timeout=20)
            reply = await BF1_PLS.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        except asyncio.TimeoutError:
            await BF1_PLS.send(MessageSegment.reply(event.message_id) + '连接超时')
        except RSPException as rsp_exc:
            await BF1_PLS.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except:
            logger.warning(traceback.format_exc())
            await BF1_PLS.send(MessageSegment.reply(event.message_id) + '服务器未开启，或者服务器内无两人以上黑队。')
    else:
        await BF1_PLS.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员') 


@BF1_PLSS.handle()
async def bf_plss(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_PLSS.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
        gameId = await get_gameid_from_serverid(server_id)
        remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
        if not remid:
            await BF1_PLSS.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')

        try:
            file_dir = await asyncio.wait_for(draw_platoons(remid, sid, sessionID,gameId,0), timeout=20)
            reply = await BF1_PLSS.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        except asyncio.TimeoutError:
            await BF1_PLSS.send(MessageSegment.reply(event.message_id) + '连接超时')
        except RSPException as rsp_exc:
            await BF1_PLSS.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_PLSS.finish(MessageSegment.reply(event.message_id) + '获取服务器玩家列表失败，可能是服务器未开启')
    else:
        await BF1_PLSS.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员') 

@BF1_UPD.handle()
async def bf_upd(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    message = html.unescape(message.extract_plain_text())
    arg = message.split(" ",maxsplit=2)
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        if len(arg) == 2 and arg[1] == "info":
            server_ind, server_id = await check_server_id(groupqq,arg[0])
            if not server_ind:
                await BF1_UPD.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
            gameId = await get_gameid_from_serverid(server_id)
            remid, sid, sessionID, _ = await get_bf1admin_by_serverid(server_id)
            if not remid:
                await BF1_UPD.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            
            res = await upd_detailedServer(remid, sid, sessionID, gameId)
            rspInfo = res['result']['rspInfo']
            maps = rspInfo['mapRotations'][0]['maps']
            name = rspInfo['serverSettings']['name']
            description = rspInfo['serverSettings']['description']
            settings = rspInfo['serverSettings']['customGameSettings']

            with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
                zh_cn = json.load(f)

            map = ""
            for i in maps:
                mode = i["gameMode"]
                map0 = i["mapName"]

                map += f'{UpdateDict_1[map0]}{UpdateDict_1[mode]} '

            sets = getSettings(settings)

            file_dir = Path('file:///') / BF1_SERVERS_DATA/'Caches'/f'info.png' 
            file_dir1 = Path('file:///') / BF1_SERVERS_DATA/'Caches'/f'info1.png'               
            await BF1_UPD.finish(MessageSegment.reply(event.message_id) + f"名称: {name}\n简介: {description}\n图池: {map.rstrip()}\n配置: {sets}\n" + MessageSegment.image(file_dir) + MessageSegment.image(file_dir1))
        elif len(arg) < 3 or arg[1] not in ["name","desc","map","set"]:
            file_dir = Path('file:///') / BF1_SERVERS_DATA/'Caches'/f'info.png'
            file_dir1 = Path('file:///') / BF1_SERVERS_DATA/'Caches'/f'info1.png'
            await BF1_UPD.finish(MessageSegment.reply(event.message_id) + ".配置 <服务器> info\n.配置 <服务器> name <名称>\n.配置 <服务器> desc <简介>\n.配置 <服务器> map <地图>\n.配置 <服务器> set <设置>\n示例: \n1).配置 1 map 1z 2z 3z 15z 21z\n2).配置 1 set 1-off 2-off 40-50%\n3).配置 1 set 默认值\n详细配置图请输入.配置 <服务器> info查询\n请谨慎配置行动服务器\n请确认配置内容的合法性:\n服务器名纯英文需低于64字节\n简介需低于256字符且低于512字节\n为避免混淆，服务器设置均按默认值为基础来修改，与服务器现有配置无关。")
        else:
            server_ind, server_id = await check_server_id(groupqq,arg[0])
            if not server_ind:
                await BF1_UPD.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
            gameId = await get_gameid_from_serverid(server_id)
            remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            if not remid:
                await BF1_UPD.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')

            try:
                res = await upd_detailedServer(remid, sid, sessionID, gameId)
                
                rspInfo = res['result']['rspInfo']
                maps = rspInfo['mapRotations'][0]['maps']
                name = rspInfo['serverSettings']['name']
                description = rspInfo['serverSettings']['description']
                settings = rspInfo['serverSettings']['customGameSettings']
                with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
                    zh_cn = json.load(f)
            except RSPException as rsp_exc:
                await BF1_UPD.send(MessageSegment.reply(event.message_id) + '无法获取服务器信息\n' + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_UPD.finish(MessageSegment.reply(event.message_id) + '无法获取服务器信息\n' + traceback.format_exception_only(e))

            try:
                if arg[1] == "desc":
                    description = zhconv.convert(arg[2], 'zh-hant')
                    if len(description) > 256 or len(description.encode('utf-8')) > 512:
                        await BF1_UPD.finish(MessageSegment.reply(event.message_id) + '简介过长')
                    await upd_updateServer(remid,sid,sessionID,rspInfo,maps,name,description,settings)
                    await BF1_UPD.finish(MessageSegment.reply(event.message_id) + '已配置简介: '+ description)
                elif arg[1] == "name":
                    name = arg[2]
                    if len(name) > 64 or len(name.encode('utf-8')) > 64:
                        await BF1_UPD.finish(MessageSegment.reply(event.message_id) + '名称过长')
                    await upd_updateServer(remid,sid,sessionID,rspInfo,maps,name,description,settings)
                    await BF1_UPD.finish(MessageSegment.reply(event.message_id) + '已配置服务器名: '+ name)
                elif arg[1] == "map":
                    map = arg[2].split(" ")
                    maps = []
                    msg = ""
                    for i in map:
                        try:
                            mode = UpdateDict[f'{str.upper(i[-1])}']
                            map0 = UpdateDict[f'{i[:-1]}']
                            msg += f'{zh_cn[map0]}-{zh_cn[mode]}\n'
                            maps.append(
                                {   
                                    "gameMode": mode,
                                    "mapName": map0
                                }
                            )
                        except:
                            continue
                    await upd_updateServer(remid,sid,sessionID,rspInfo,maps,name,description,settings)
                    await BF1_UPD.finish(MessageSegment.reply(event.message_id) + '已配置图池:\n'+ msg.rstrip())
                elif arg[1] == "set":
                    setstrlist = arg[2].split(" ")
                    print(setstrlist)
                    settings = ToSettings(setstrlist)
                    await upd_updateServer(remid,sid,sessionID,rspInfo,maps,name,description,settings)
                    await BF1_UPD.finish(MessageSegment.reply(event.message_id) + '已配置服务器设置:\n'+ getSettings(settings))
            except RSPException as rsp_exc:
                await BF1_UPD.send(MessageSegment.reply(event.message_id) + '配置失败\n' + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_UPD.finish(MessageSegment.reply(event.message_id) + '配置失败\n' + traceback.format_exception_only(e))
    else:
        await BF1_UPD.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')     


@BF1_INSPECT.handle()
async def bf1_ins(event:GroupMessageEvent, state:T_State):
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        remid, sid, sessionID, access_token = await get_one_random_bf1admin()
        async with async_db_session() as session:
            stmt = select(GroupAdmins).filter(GroupAdmins.groupqq==groupqq)
            adminlist = [row[0].qq for row in (await session.execute(stmt)).all()]
            stmt_pid = select(Players).filter(Players.qq.in_(adminlist))
            adminpids = [row[0].pid for row in (await session.execute(stmt_pid)).all()]
            try:
                res_pid = await upd_getPersonasByIds(remid, sid, sessionID, adminpids)
                res_tyc = await upd_getServersByPersonaIds(remid,sid,sessionID,adminpids)
            except RSPException as rsp_exc:
                await BF1_INSPECT.send(MessageSegment.reply(event.message_id) + '获取玩家信息失败\n' + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_INSPECT.finish(MessageSegment.reply(event.message_id) + '获取玩家信息失败\n' + traceback.format_exception_only(e))

            eaids = [res_pid['result'][f'{personaId}']['displayName'] for personaId in adminpids]
            tycs = [res_tyc['result'][f'{personaId}'] for personaId in adminpids]

            servers = await get_server_num(groupqq)
            gameids = []
            for server_ind, server_id in servers:
                gameid = await get_gameid_from_serverid(server_id)
                gameids.append(gameid)

            names = []
            tyc_game = {
                "names": [],
                "on": {},
                "off": {}
            }
            for i in range(len(eaids)):
                if tycs[i]:
                    print(eaids[i])
                    name =  tycs[i]['name']
                    gameid = tycs[i]['gameId']
                    if name not in tyc_game['names']:
                        tyc_game['names'].append(name)
                        if int(gameid) in gameids:
                            tyc_game['on'][name] = ''
                        else:
                            tyc_game['off'][name] = ''

                    if int(gameid) in gameids:
                        tyc_game['on'][name] += str(eaids[i]) + ' '
                    else:
                        tyc_game['off'][name] += str(eaids[i]) + ' '
            on_msg = '在岗: \n'
            off_msg = '离岗: \n'
            print(tyc_game)
            for name in list(tyc_game['on'].keys()):
                on_msg += f"{name[:20]}: \n{tyc_game['on'][name].rstrip()}\n"

            for name in list(tyc_game['off'].keys()):
                off_msg += f"{name[:20]}: \n{tyc_game['off'][name].rstrip()}\n"            
            
            ins_msg = on_msg + off_msg.rstrip()
            await BF1_INSPECT.finish(MessageSegment.reply(event.message_id) + ins_msg)
            
    else:
        await BF1_INSPECT.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员') 