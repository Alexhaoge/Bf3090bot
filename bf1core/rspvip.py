from nonebot.log import logger
from nonebot.params import _command_arg, ArgStr
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent
from nonebot.typing import T_State

import json
import asyncio
import datetime
import traceback

from sqlalchemy.future import select

from ..bf1rsp import *
from ..rdb import *
from ..redis_helper import redis_client
from ..bf1helper import *

from .matcher import (
    BF1_VIP,BF1_VIPLIST,BF1_CHECKVIP,BF1_UNVIP, BF1_VIPALL, BF1_VIPGM
)

@BF1_VIP.handle()
async def bf1_vip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split()
    groupqq = await check_session(event.group_id)

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        if reply_message_id(event) == None:
            server_ind, server_id = await check_server_id(groupqq,arg[0])
            if not server_ind:
                await BF1_VIP.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
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
    arg = message.extract_plain_text().split()
    groupqq = await check_session(event.group_id)

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_VIPLIST.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
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
    arg = message.extract_plain_text().split()
    session = await check_session(event.group_id)

    admin_perm = await check_admin(session, event.user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(session,arg[0])
        if not server_ind:
            await BF1_CHECKVIP.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')

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
    arg = message.extract_plain_text().split()
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

@BF1_VIPALL.handle()
async def bf1_vipall(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(maxsplit=1)
    if len(arg)>1:
        try:
            days = int(arg[1])
        except:
            await BF1_VIPALL.finish(MessageSegment.reply(event.message_id) + f'参数格式不正确，应为.vipall 服名 天数')
    else:
        days = 1
    groupqq = await check_session(event.group_id)

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_VIPALL.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')
        
        async with async_db_session() as session:
            vip_rows = (await session.execute(select(ServerVips).filter_by(serverid=server_id))).all()
            for row in vip_rows:
                if not row[0].permanent:
                    row[0].days += days
            await session.commit()
        
        await BF1_VIPALL.send(MessageSegment.reply(event.message_id) + f'为{arg[0]}服所有限时VIP延长{days}天')
    else:
        await BF1_VIPALL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_VIPGM.handle()
async def bf1_vip_groupmember(event: GroupMessageEvent, state: T_State):
    # if not check_sudo(event.group_id, event.user_id):
    #     return
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split()
    groupqq = await check_session(event.group_id)
    days = int(arg[0])
    if len(arg) > 1:
        priority = int(arg[1])
    else:
        priority = 1

    admin_perm = await check_admin(groupqq, event.user_id)
    if admin_perm:
        reply_id = reply_message_id(event)
        if reply_id:
            redis_pl = await redis_client.get(f"pl:{groupqq}:{reply_id}")
            if not redis_pl:
                await BF1_VIPGM.finish(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
            pl_json = json.loads(redis_pl)
            pl = pl_json['pl']
            server_id = pl_json['serverid']
            server_ind = pl_json['serverind']

            remid, sid, sessionID, _ = await get_one_random_bf1admin()
            gameId = await get_gameid_from_serverid(server_id)
            detailedServer = await upd_detailedServer(remid, sid, sessionID, gameId)
            adminList = [int(admin['personaId']) for admin in detailedServer['result']["rspInfo"]['adminList']]
            adminList.append(int(detailedServer['result']['rspInfo']['owner']['personaId']))

            async with async_db_session() as session:
                member_rows = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq))).all()
                member_personaIds = set(r[0].pid for r in member_rows)

                vip_members = []
                # member_personaIds.intersection(player['id'] for player in filter(lambda x: x['slot']<=64, pl))
                for p in pl:
                    if p['slot'] <= 64:
                        pid = int(p['id'])
                        if pid in member_personaIds and pid not in adminList:
                            vip_members.append((p['id'], p['name']))
                            exist_vip = (await session.execute(
                                select(ServerVips).filter_by(serverid=server_id, pid=p['id'])
                            )).first()
                            if exist_vip:
                                exist_vip[0].priority = max(exist_vip[0].priority, priority)
                                if not exist_vip[0].permanent:
                                    exist_vip[0].days += days
                            else:
                                new_vip = ServerVips(
                                    serverid = server_id, pid = p['id'], originid = p['name'],
                                    days = days, permanent = False, enabled = False, priority = priority
                                )
                                session.add(new_vip)
                await session.commit()

            if not len(vip_members):
                await BF1_VIPGM.finish(MessageSegment.reply(event.message_id) + '该玩家列表中没有群友')
            else:
                await BF1_VIPGM.send(MessageSegment.reply(event.message_id) + f'为以下玩家添加{server_ind}服VIP{days}天:\n'\
                            + ', '.join(v[1] if v[1] else f'pid:{v[0]}' for v in vip_members)\
                            + '\n请注意新添加VIP均未生效，不论是否为行动服，请及时checkvip')
        else:
            await BF1_VIPGM.finish(MessageSegment.reply(event.message_id) + '请回复某个玩家列表消息以使用此功能')
    else:
        await BF1_VIPGM.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')