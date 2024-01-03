from nonebot.log import logger
from nonebot.params import _command_arg
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent
from nonebot.typing import T_State

import html
import traceback
from sqlalchemy.future import select
from sqlalchemy import or_

from ..bf1rsp import *
from ..bf1draw import *
from ..secret import *
from ..rdb import *
from ..bf1helper import *
from ..utils import PREFIX

from .matcher import (
    BF1_INIT,BF1_BIND,BF1_REBIND,BF1_ADDBIND,
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
    
@BF1_BIND.handle()
async def bf1_bindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',1)
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
        await BF1_BIND.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
    except:
        logger.warning(traceback.format_exc())
        await BF1_BIND.finish(MessageSegment.reply(event.message_id) + "无法获取服务器数据\n" \
                              + traceback.format_exception_only())
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

@BF1_REBIND.handle()
async def bf1_rebindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',1)
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
    arg = message.extract_plain_text().split(' ',1)
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
    adminqqs = message.extract_plain_text().split(' ')
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
    arg = message.extract_plain_text().split(' ')
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

