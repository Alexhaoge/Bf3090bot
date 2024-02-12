import nonebot

from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent, GroupDecreaseNoticeEvent, GroupIncreaseNoticeEvent, GroupRequestEvent
from nonebot.log import logger
from nonebot.params import _command_arg

from nonebot.typing import T_State

import html
import json
import asyncio

from sqlalchemy.future import select

from ..utils import BF1_SERVERS_DATA
from ..bf1rsp import *
from ..bf1draw import *
from ..secret import *
from ..image import upload_img
from ..rdb import *
from ..redis_helper import redis_client
from ..bf1helper import *
from .matcher import del_user, bye_user, add_user,approve_req,welcome_user,get_user

@del_user.handle()
async def groupmember_del(event: GroupDecreaseNoticeEvent):
    async with async_db_session() as session:
        group_row = (await session.execute(select(ChatGroups).filter_by(groupqq=event.group_id))).first()
        if group_row:
            groupqq = group_row[0].bind_to_group
            stmt = select(GroupMembers).filter_by(groupqq=groupqq, qq=event.user_id)
            user_rec = (await session.execute(stmt)).all()
            for row in user_rec:
                await session.delete(row[0])
            await session.commit()

@bye_user.handle()
async def user_bye(event: GroupDecreaseNoticeEvent):
    if event.sub_type == 'leave':
        await bye_user.send(f'{event.user_id}退群了。')
    else: 
        await bye_user.send(f'{event.user_id}被{event.operator_id}送走了。')

@add_user.handle()
async def user_add_request(event: GroupRequestEvent):
    comment = event.comment.strip()
    playerName = comment[comment.find("答案：") + 3:] \
        if comment.find("答案：") != -1 else None
    groupqq = await check_session(event.group_id)

    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    res = await getPersonasByName(access_token, playerName)
    logger.debug(res)
    logger.debug(playerName)
    apply = {'flag': event.flag, 'subtype': event.sub_type, 'userid': event.user_id}
    try:
        personaId,playerName,pidid = res
        logger.debug(playerName,personaId)
    except Exception as e:
        logger.warning(e)
        reply = await add_user.send(f'收到{event.user_id}的加群请求: {playerName}(无效id,可能是bug，请手动查询此人战绩！)\n回复y同意进群，回复n+理由(可选)拒绝进群。')#
    else:
        reply = await add_user.send(f'收到{event.user_id}的加群请求: {playerName}(有效id)，战绩信息如下: \n回复y同意进群，回复n 理由(可选)拒绝进群。')#\n回复y同意进群，回复n+理由(可选)拒绝进群。
        apply['personaId'], apply['playerName'] = personaId, playerName
        async with async_db_session() as session:
            p = (await session.execute(select(Players).filter_by(qq=event.user_id))).first()
            if p:
                p[0].originid, p[0].pid = playerName, personaId
                session.add(p[0])
            else:
                session.add(Players(pid=personaId, originid=playerName, qq=event.user_id))
            await session.commit()
        file_dir = await asyncio.wait_for(draw_stat(remid, sid, sessionID, personaId, playerName),timeout=15)
        await add_user.send(MessageSegment.image(file_dir))
    await redis_client.set(f'apply:{groupqq}:{reply["message_id"]}', json.dumps(apply), ex=345600) # expire after 4 days
            
@approve_req.handle()
async def user_add(event: GroupMessageEvent):
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        message = event.get_message().extract_plain_text().split()
        bots = nonebot.get_bots()
        sign = 0
        for bot in bots.values():
            botlist = await bot.get_group_list()
            for i in botlist:
                if i["group_id"] == event.group_id:
                    sign = 1
                    break
            if sign == 1:
                break
        (BF1_SERVERS_DATA/f'{event.group_id}_apply').mkdir(exist_ok=True)
        message_id = reply_message_id(event)
        logger.debug(message_id)
        if message_id != None:
            apply_raw = await redis_client.get(f'apply:{groupqq}:{message_id}')
            apply = json.loads(apply_raw)
            if not apply:
                await approve_req.finish('入群自动审批记录已过期，请手动审核')
            logger.info(f'approve_req:{apply["userid"]}')
            if message[0].strip().lower() == 'y':
                if 'personaId' in apply:
                    logger.info(f'approve_req:{apply["userid"]}, {apply["personaId"]}')
                    async with async_db_session() as session:
                        exist_gm = (await session.execute(select(GroupMembers).filter_by(qq=apply['userid'], groupqq=groupqq))).first()
                        if not exist_gm:
                            member = GroupMembers(qq=apply['userid'], groupqq=groupqq, pid=apply['personaId'])
                            session.add(member)
                        exist_player = (await session.execute(select(Players).filter_by(qq=apply['userid']))).first()
                        if exist_player:
                            exist_player[0].pid, exist_player[0].originid = apply['personaId'], apply['playerName']
                            session.add(exist_player[0])
                        else:
                            player = Players(qq=apply['userid'], originid=apply['playerName'], pid=apply['personaId'])
                            session.add(player)
                        await session.commit()
                logger.info(apply['flag'])
                await bot.set_group_add_request(
                    flag = apply['flag'],
                    sub_type = apply['subtype'],
                    approve = True
                )
                #admin_logging_helper('approve_join_group_request', user_id, event.group_id, main_groupqq=groupqq, apply_qq=apply['user_id'])
            else:
                if len(message) == 1:
                    await bot.set_group_add_request(
                        flag = apply['flag'],
                        sub_type = apply['subtype'],
                        approve = False
                    )
                    #admin_logging_helper('reject_join_group_request', user_id, event.group_id, main_groupqq=groupqq, apply_qq=apply['user_id'])
                    await approve_req.finish('已拒绝入群')
                else:
                    await bot.set_group_add_request(
                        flag = apply['flag'],
                        sub_type = apply['subtype'],
                        approve = False,
                        reason = message[1],
                    )
                    #admin_logging_helper('reject_join_group_request', user_id, event.group_id, main_groupqq=groupqq, reason=message[1], apply_qq=apply['user_id'])
                    await approve_req.finish(f'已拒绝入群。理由：{message[1]}')


@welcome_user.handle()
async def bf1_welcome(event:GroupMessageEvent, state:T_State):   
    message = _command_arg(state) or event.get_message()
    msg = html.unescape(message.extract_plain_text())
    
    async with async_db_session() as session:
        group_rec = (await session.execute(select(ChatGroups).filter_by(groupqq=event.group_id))).first()
        if group_rec:
            group_rec[0].welcome = msg
            session.add(group_rec[0])
            await session.commit()
            await welcome_user.finish(MessageSegment.reply(event.message_id) + f'已配置入群欢迎: {msg}')
        else:
            await welcome_user.finish(MessageSegment.reply(event.message_id) + f'群组未初始化')

@get_user.handle()
async def user_get(event: GroupIncreaseNoticeEvent):
    groupqq = event.group_id
    bots = nonebot.get_bots()

    sign = 0
    for bot in bots.values():
        botlist = await bot.get_group_list()
        for i in botlist:
            if i["group_id"] == groupqq:
                sign = 1
                break
        if sign == 1:
            break
    
    async with async_db_session() as session:
        group = (await session.execute(select(ChatGroups).filter_by(groupqq=groupqq))).first()
        welcome_msg = group[0].welcome
        if welcome_msg == '':
            welcome_msg = '欢迎入群'
        player = (await session.execute(select(Players).filter_by(qq=event.user_id))).first()
        if player:
            await bot.set_group_card(group_id=event.group_id, user_id=event.user_id, card=player[0].originid)
            welcome_msg += f'\n已自动将您绑定为{player[0].originid}'
    await get_user.send(MessageSegment.at(event.user_id) + welcome_msg)