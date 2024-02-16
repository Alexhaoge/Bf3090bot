from nonebot.log import logger
from nonebot.params import _command_arg, ArgStr
from nonebot.adapters.onebot.v11 import Message, MessageSegment, GroupMessageEvent
from nonebot.typing import T_State

import html
import traceback
from sqlalchemy.future import select
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy import or_

from ..bf1rsp import *
from ..bf1draw import *
from ..secret import *
from ..rdb import *
from ..bf1helper import *
from ..utils import PREFIX

from .matcher import (
    BF1_INIT,BF1_INIT2,
    BF1_BIND,BF1_BIND2,BF1_REBIND,BF1_ADDBIND,BF1_UNBIND,
    BF1_RMGROUP, BF1_RMSERVER,
    BF1_ADDADMIN,BF1_DELADMIN,BF1_ADMINLIST
)

@BF1_INIT.handle()
async def bf1_init(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    groupqq = event.group_id
    arg = message.extract_plain_text()

    main_groupqq = groupqq if arg.startswith(f'{PREFIX}') else arg
    async with async_db_session() as session:
        if main_groupqq != groupqq:
            exist_main_group = (await session.execute(select(ChatGroups).filter_by(groupqq=main_groupqq))).first()
            if not exist_main_group:
                await BF1_INIT.finish(MessageSegment.reply(event.message_id)+'主群不存在!')
        exist_group = (await session.execute(select(ChatGroups).filter_by(groupqq=groupqq))).first()
        if exist_group:
            exist_group[0].bind_to_group = main_groupqq
            session.add(exist_group[0])
        else:
            session.add(ChatGroups(groupqq=groupqq, bind_to_group=main_groupqq))
        await session.commit()
    
    await BF1_INIT.send(MessageSegment.reply(event.message_id) + f'初始化完成：{main_groupqq}')

@BF1_INIT2.handle()
async def bf1_init(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(maxsplit=1)
    if arg.startswith(f'{PREFIX}'):
        await BF1_INIT2.send(MessageSegment.reply(event.message_id)+'参数格式不正确')
    if len(arg) > 1:
        groupqq, main_groupqq = int(arg[0]), int(arg[1])
    else:
        groupqq, main_groupqq = int(arg[0]), int(arg[0])
    async with async_db_session() as session:
        if main_groupqq != groupqq:
            exist_main_group = (await session.execute(select(ChatGroups).filter_by(groupqq=main_groupqq))).first()
            if not exist_main_group:
                await BF1_INIT2.finish(MessageSegment.reply(event.message_id)+'主群不存在!')
        exist_group = (await session.execute(select(ChatGroups).filter_by(groupqq=groupqq))).first()
        if exist_group:
            exist_group[0].bind_to_group = main_groupqq
            session.add(exist_group[0])
        else:
            session.add(ChatGroups(groupqq=groupqq, bind_to_group=main_groupqq))
        await session.commit()
    await BF1_INIT2.send(MessageSegment.reply(event.message_id) + f'初始化完成：{main_groupqq}')


@BF1_BIND.handle()
async def bf1_bindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(maxsplit=1)
    server_ind = arg[0]
    server_keyword = html.unescape(arg[1])
    groupqq = await check_session(event.group_id)
    logger.info(str(server_keyword))
    remid, sid, sessionID, _ = await get_one_random_bf1admin()
    try:
        result = await upd_servers(remid, sid, sessionID, server_keyword)
        lens = len(result['result']['gameservers'])
        if lens > 1:
            await BF1_BIND.finish('搜索到的服务器数量大于1。')
        gameId = result['result']['gameservers'][0]['gameId']
        #detailedresult = await get_detailedServer_databyid(gameId)
        detailedServer = await upd_detailedServer(remid, sid, sessionID, gameId)
    except RSPException as rsp_exc:
        await BF1_BIND.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_BIND.finish(MessageSegment.reply(event.message_id) + "无法获取服务器数据\n" \
                              + traceback.format_exception_only(e))
    else:
        async with async_db_session() as session:
            serverid = detailedServer['result']['rspInfo']['server']['serverId']
            server_name = result['result']['gameservers'][0]['name']
            bind_stmt = select(GroupServerBind).filter(
                GroupServerBind.groupqq == groupqq,
                or_(GroupServerBind.ind == server_ind, GroupServerBind.serverid == serverid))
            exist_bind = (await session.execute(bind_stmt)).first()
            if exist_bind:
                await BF1_BIND.finish(f'服务器{server_ind}或{serverid}已存在')
            else:
                session.add(GroupServerBind(groupqq = groupqq, serverid = serverid, ind = server_ind))
            exist_s = (await session.execute(select(Servers).filter_by(serverid=serverid))).first()
            if not exist_s:
                session.add(Servers(
                    guid=detailedServer['result']['serverInfo']['guid'],
                    serverid=serverid,
                    name = server_name,
                    keyword = server_keyword,
                    opserver = (detailedServer['result']['serverInfo']['mapMode'] == 'BreakthroughLarge')
                ))
            await session.commit()
            
        await BF1_BIND.finish(f'本群已绑定服务器:{server_name}，编号为{server_ind}')
        # except Exception as e:
        #    await BF1_BIND.finish(f'请联系管理员处理\n{traceback.format_exc(2)}')

@BF1_BIND2.handle()
async def bf1_bindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(maxsplit=2)
    if len(arg) != 3:
        await BF1_BIND2.finish(MessageSegment.reply(event.message_id) + '参数格式错误')
    server_ind = arg[1]
    server_keyword = html.unescape(arg[2])
    groupqq = await check_session(int(arg[0]))
    if not groupqq:
        await BF1_BIND2.finish(MessageSegment.reply(event.message_id) + '该群组未初始化')
    logger.info(f'{groupqq}, {server_ind}, {server_keyword}')
    remid, sid, sessionID, _ = await get_one_random_bf1admin()
    try:
        result = await upd_servers(remid, sid, sessionID, server_keyword)
        lens = len(result['result']['gameservers'])
        if lens > 1:
            await BF1_BIND2.finish('搜索到的服务器数量大于1。')
        gameId = result['result']['gameservers'][0]['gameId']
        #detailedresult = await get_detailedServer_databyid(gameId)
        detailedServer = await upd_detailedServer(remid, sid, sessionID, gameId)
    except RSPException as rsp_exc:
        await BF1_BIND2.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_BIND.finish(MessageSegment.reply(event.message_id) + "无法获取服务器数据\n" \
                              + traceback.format_exception_only(e))
    else:
        async with async_db_session() as session:
            serverid = detailedServer['result']['rspInfo']['server']['serverId']
            server_name = result['result']['gameservers'][0]['name']
            bind_stmt = select(GroupServerBind).filter(
                GroupServerBind.groupqq == groupqq,
                or_(GroupServerBind.ind == server_ind, GroupServerBind.serverid == serverid))
            exist_bind = (await session.execute(bind_stmt)).first()
            if exist_bind:
                await BF1_BIND2.finish(f'服务器{server_ind}或{serverid}已存在')
            else:
                session.add(GroupServerBind(groupqq = groupqq, serverid = serverid, ind = server_ind))
            exist_s = (await session.execute(select(Servers).filter_by(serverid=serverid))).first()
            if not exist_s:
                session.add(Servers(
                    guid=detailedServer['result']['serverInfo']['guid'],
                    serverid=serverid,
                    name = server_name,
                    keyword = server_keyword,
                    opserver = (detailedServer['result']['serverInfo']['mapMode'] == 'BreakthroughLarge')
                ))
            await session.commit()
            
        await BF1_BIND2.finish(f'群{groupqq}({arg[0]})已绑定服务器:{server_name}，编号为{server_ind}')


@BF1_REBIND.handle()
async def bf1_rebindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(maxsplit=1)
    server_ind = arg[0]
    new_server_ind = html.unescape(arg[1])
    groupqq = await check_session(event.group_id)
 
    async with async_db_session() as session:
        stmt = select(GroupServerBind).filter_by(groupqq=groupqq, ind=server_ind)
        exist_server = (await session.execute(stmt)).first()
        if exist_server:
            exist_server[0].ind = new_server_ind
            session.add(exist_server[0])
        else:
            await BF1_REBIND.finish(f"服务器{server_ind}不存在")
        await session.commit()
    await BF1_REBIND.finish(f'已将"{server_ind}"改绑为"{new_server_ind}"')

@BF1_ADDBIND.handle()
async def bf1_addbindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(maxsplit=1)
    server_ind = arg[0]
    new_server_ind = html.unescape(arg[1])
    groupqq = await check_session(event.group_id)

    async with async_db_session() as session:
        stmt = select(GroupServerBind).filter_by(groupqq=groupqq, ind=server_ind)
        exist_server = (await session.execute(stmt)).first()
        if exist_server:
            exist_server[0].alias = new_server_ind
            session.add(exist_server[0])
            await session.commit()
        else:
            await BF1_REBIND.finish(f"服务器{server_ind}不存在")
    await BF1_ADDBIND.finish(f'已将"{server_ind}"的别名设置为："{new_server_ind}"')

@BF1_ADDADMIN.handle()
async def bf1_admin(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    groupqq = await check_session(event.group_id)
    adminqqs = message.extract_plain_text().split()
    failed_qqs = []
    success_qqs = []
    async with async_db_session() as session:
        new_admins = []
        for adqq_str in adminqqs:
            if adqq_str.isdigit():
                adqq = int(adqq_str)
                stmt = select(GroupAdmins).filter(GroupAdmins.groupqq==groupqq, GroupAdmins.qq==adqq)
                exist_qq = (await session.execute(stmt)).first()
                if exist_qq:
                    failed_qqs.append(adqq_str)
                else:
                    new_admins.append(GroupAdmins(groupqq=groupqq, qq=adqq))
                    success_qqs.append(adqq_str)
        session.add_all(new_admins)
        await session.commit()
    msg = (f"本群组已添加管理: {','.join(success_qqs)}" if len(success_qqs) else '') +\
        ('\n' if len(success_qqs) and len(failed_qqs) else '') +\
        (f"请不要重复添加：{','.join(failed_qqs)}" if len(failed_qqs) else '')
    await BF1_ADDADMIN.send(MessageSegment.reply(event.message_id) + msg)

@BF1_DELADMIN.handle()
async def bf1_deladmin(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    groupqq = await check_session(event.group_id)
    arg = message.extract_plain_text().split()
    deleted_qqs = []
    async with async_db_session() as session:
        for admin_str in arg:
            if admin_str.isdigit():
                admin_qq = int(admin_str)
                stmt = select(GroupAdmins).filter(GroupAdmins.groupqq==groupqq, GroupAdmins.qq==admin_qq)
                admin_del = (await session.execute(stmt)).first()
                if admin_del:
                    await session.delete(admin_del[0])
                    deleted_qqs.append(admin_str)
                await session.commit()
    await BF1_DELADMIN.send(MessageSegment.reply(event.message_id) + f"本群组已删除管理：{','.join(deleted_qqs)}")

@BF1_ADMINLIST.handle()
async def bf1_adminlist(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    groupqq = await check_session(event.group_id)
    async with async_db_session() as session:
        stmt = select(GroupAdmins).filter(GroupAdmins.groupqq==groupqq)
        adminlist = [str(row[0].qq) for row in (await session.execute(stmt)).all()]
    await BF1_DELADMIN.send(MessageSegment.reply(event.message_id) + "本群组管理列表：\n" + '\n'.join(adminlist))


@BF1_UNBIND.handle()
async def bf1_unbind_invoke(event: GroupMessageEvent, state: T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(maxsplit=1)
    if len(arg) != 2:
        await BF1_UNBIND.finish(MessageSegment.reply(event.message_id)+'参数格式不正确')
    
    groupqq = int(arg[0])
    main_groupqq = await check_session(groupqq)
    if not main_groupqq:
        await BF1_UNBIND.finish(MessageSegment.reply(event.message_id)+'该群组未初始化')
    
    server_ind = arg[1]
    server_ind, server_id = await check_server_id(main_groupqq, server_ind)
    if not server_id:
        await BF1_UNBIND.finish(f"服务器{arg[1]}不存在")
    state['groupqq'] = groupqq
    state['main_groupqq'] = main_groupqq
    state['server_id'] = server_id
    state['server_ind'] = server_ind
    
    async with async_db_session() as session:
        related_vbans = (await session.execute(
            select(ServerVBans).filter_by(serverid=server_id, notify_group=main_groupqq))).all()
        await BF1_UNBIND.send(MessageSegment.reply(event.message_id) + f'服务器{server_ind}({server_id})的Vbans中有{len(related_vbans)}个与群组{groupqq}关联，是否删除？')

@BF1_UNBIND.got('msg', prompt='发送"y"删除并解绑，"n"保留并解绑，发送其他内容撤销解绑')
async def bf1_unbind_confirm(event: GroupMessageEvent, state: T_State, msg: Message = ArgStr("msg")):
    server_id = state['server_id']
    server_ind = state['server_ind']
    groupqq = state['groupqq']
    main_groupqq = state['main_groupqq']
    async with async_db_session() as session:
        related_vbans = (await session.execute(
            select(ServerVBans).filter_by(serverid=server_id, notify_group=main_groupqq))).all()
        if msg == 'y' or msg == 'Y':
            for r in related_vbans:
                await session.delete(r[0])
            n_del = len(related_vbans)  
        elif msg == 'n' or msg == 'N':
            for r in related_vbans:
                r[0].notify_group = None
            n_del = 0
        else:
            await session.rollback()
            await BF1_UNBIND.send(MessageSegment.reply(event.message_id) + '操作已取消')   
            return
        
        gsbind = (await session.execute(select(GroupServerBind).filter_by(serverid=server_id, groupqq=main_groupqq))).first()
        await session.delete(gsbind[0])
        await session.commit()
        await BF1_UNBIND.finish(MessageSegment.reply(event.message_id) + f'从群组{main_groupqq}解绑{server_ind}({server_id})成功，并删除{n_del}个vban')   

@BF1_RMSERVER.handle()
async def bf1_remove_server_invoke(event: GroupMessageEvent, state: T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().strip()
    if not arg.isdigit():
        await BF1_RMSERVER.finish(MessageSegment.reply(event.message_id)+'参数格式不正确')
    server_id = int(arg)
    
    try:
        remid, sid, sessionID, _ = await get_one_random_bf1admin()
        gameId = await get_gameid_from_serverid(server_id)
        detailedServer = await upd_detailedServer(remid, sid, sessionID, gameId)
        servername = detailedServer['result']['rspInfo']['serverSettings']['name']
    except RSPException as rsp_exc:
        await BF1_RMSERVER.send(MessageSegment.reply(event.message_id) + '服务器信息获取失败，请手动验证服务器编号是否正确')
    else:
        await BF1_RMSERVER.send(MessageSegment.reply(event.message_id) + f'即将删除服务器{server_id}\n{servername}')

    async with async_db_session() as session:
        server = (await session.execute(select(Servers).filter_by(serverid=server_id))).first()
        if not server:
            await BF1_RMSERVER.finish(MessageSegment.reply(event.message_id)+f'服务器{server_id}不在数据库记录中')
        related_vbans = (await session.execute(
            select(ServerVBans).filter_by(serverid=server_id))).all()
        related_vips = (await session.execute(
            select(ServerVips).filter_by(serverid=server_id))).all()
        related_binds = (await session.execute(
            select(GroupServerBind).filter_by(serverid=server_id))).all()
        state['server_id'] = server[0].serverid
        await BF1_RMSERVER.send(MessageSegment.reply(event.message_id)\
                          +f'删除该服务器将同时删除数据库内{len(related_vbans)}条Vban记录, '\
                          +f'{len(related_vips)}条VIP记录(不执行unvip), ' \
                          +f'并从{len(related_binds)}个群解绑该服务器')


@BF1_RMSERVER.got('msg', prompt='发送"y"确认删除服务器，发送其他内容撤销删服')
async def bf1_rmserver_confirm(event: GroupMessageEvent, state: T_State, msg: Message = ArgStr("msg")):
    server_id = state['server_id']
    if msg == 'y' or msg == 'Y':
        async with async_db_session() as session:
            server = (await session.execute(select(Servers).filter_by(serverid=server_id))).first()
            try:
                related_vbans = (await session.execute(
                    select(ServerVBans).filter_by(serverid=server_id))).all()
                related_vips = (await session.execute(
                    select(ServerVips).filter_by(serverid=server_id))).all()
                related_binds = (await session.execute(
                    select(GroupServerBind).filter_by(serverid=server_id))).all()
                related_bfadmins = (await session.execute(
                    select(ServerBf1Admins).filter_by(serverid=server_id))).all()
                for r in related_vbans:
                    await session.delete(r[0])
                for r in related_vips:
                    await session.delete(r[0])
                for r in related_binds:
                    await session.delete(r[0])
                for r in related_bfadmins:
                    await session.delete(r[0])
                await session.delete(server[0])
            except Exception as e:
                await session.rollback()
                await BF1_RMSERVER.finish(MessageSegment.reply(event.message_id) + f'删除服务器{server_id}失败\n' + traceback.format_exception_only(e))   
            else:
                await session.commit()
                await BF1_RMSERVER.finish(MessageSegment.reply(event.message_id) + f'删除服务器{server_id}成功，请注意服务器实际VIP需要使用插件手动清除')
    else:
        await BF1_RMSERVER.send(MessageSegment.reply(event.message_id) + '操作取消')

@BF1_RMGROUP.handle()
async def bf1_remove_group_invoke(event: GroupMessageEvent, state: T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().strip()
    if not arg.isdigit():
        await BF1_RMGROUP.finish(MessageSegment.reply(event.message_id)+'参数格式不正确')
    groupqq = int(arg)
    
    async with async_db_session() as session:
        group = (await session.execute(select(ChatGroups).filter_by(groupqq=groupqq))).first()
        if not group:
            await BF1_RMGROUP.finish(MessageSegment.reply(event.message_id)+f'群{groupqq}不在数据库记录中')
        related_groups = (await session.execute(select(ChatGroups).filter(ChatGroups.groupqq!=groupqq, ChatGroups.bind_to_group==groupqq))).all()
        if len(related_groups):
            await BF1_RMGROUP.finish(MessageSegment.reply(event.message_id)+f'群组{groupqq}被以下群组关联，请修改后再执行删除操作\n'\
                                     + '\n'.join(str(r[0].groupqq) for r in related_groups))
        state['groupqq'] = groupqq
        admins = (await session.execute(select(GroupAdmins).filter_by(groupqq=groupqq))).all()
        members = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq))).all()
        binds = (await session.execute(select(GroupServerBind).filter_by(groupqq=groupqq))).all()
        await BF1_RMGROUP.send(MessageSegment.reply(event.message_id)\
                            + f'删除群组{groupqq}\n'\
                            + f'将同时删除数据库内{len(admins)}条群组管理记录\n'\
                            + f'{len(members)}条群成员记录' \
                            + f'并解绑{len(binds)}个服务器')


@BF1_RMGROUP.got('msg', prompt='发送"y"确认删除群，发送其他内容撤销删群')
async def bf1_rmgroup_confirm(event: GroupMessageEvent, state: T_State, msg: Message = ArgStr("msg")):
    groupqq = state['groupqq']
    if msg == 'y' or msg == 'Y':
        async with async_db_session() as session:
            group = (await session.execute(select(ChatGroups).filter_by(groupqq=groupqq).options(
                    selectinload(ChatGroups.admins),
                    selectinload(ChatGroups.members),
                    selectinload(ChatGroups.servers)
                ))).first()
            try:
                related_vbans = (await session.execute(select(ServerVBans).filter_by(notify_group=groupqq))).all()
                for r in related_vbans:
                    r[0].notify_group = None
                for r in group[0].admins:
                    await session.delete(r)
                for r in group[0].members:
                    await session.delete(r)
                for r in group[0].servers:
                    await session.delete(r)
                await session.delete(group[0])
            except Exception as e:
                await session.rollback()
                await BF1_RMGROUP.finish(MessageSegment.reply(event.message_id) + f'删除群组{groupqq}失败\n' + traceback.format_exception_only(e))   
            else:
                await session.commit()
                await BF1_RMGROUP.finish(MessageSegment.reply(event.message_id) + f'删除群组{groupqq}成功')  
    else:
        await BF1_RMGROUP.send(MessageSegment.reply(event.message_id) + '操作取消')
 