import nonebot
from nonebot import get_bot
from nonebot.rule import Rule
from nonebot.typing import T_State
from nonebot.rule import to_me
from nonebot.params import CommandArg, Depends, _command_arg
from nonebot.plugin import on_notice, on_request, on_command,on_message
from nonebot.adapters.onebot.v11 import (
    Bot, Event, Message,MessageSegment,GroupMessageEvent,
    GroupDecreaseNoticeEvent, GroupIncreaseNoticeEvent,
    GroupRequestEvent,
)
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER

from typing import Annotated
import asyncio
import html
import os
import pathlib
import re
from .bf1 import get_player_data,remid,sid,access_token,sessionID,check_session,reply_message_id,get_player_databyID,check_admin
from .bf1rsp import getPersonasByName,upd_getPersonasByIds
from .bf1draw import draw_stat
from .utils import *
from .image import *

message_id = 0

async def _is_del_user(event: Event) -> bool:
    return isinstance(event, GroupDecreaseNoticeEvent)

async def _is_get_user(event: Event) -> bool:
    return isinstance(event, GroupIncreaseNoticeEvent)

async def _is_add_user(event: Event) -> bool:
    return isinstance(event, GroupRequestEvent)

del_user = on_notice(Rule(_is_del_user), priority=1, block=True)

get_user = on_notice(Rule(_is_get_user), priority=1, block=True)

add_user = on_request(Rule(_is_add_user), priority=1, block=True)

welcome_user = on_command(f'{PREFIX}配置入群欢迎', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)

approve_req = on_command('y',rule = to_me ,aliases={'n'},priority=1, block=True)

@del_user.handle()
async def user_bye(event: GroupDecreaseNoticeEvent):
    session = event.group_id
    session = check_session(session)
    for filename in os.listdir(BF1_PLAYERS_DATA/f'{session}'):
        if filename.startswith(str(event.user_id)):
            file_path = os.path.join(BF1_PLAYERS_DATA/f'{session}', filename)
            os.remove(file_path)
    if event.sub_type == 'leave':
        await del_user.send(f'{event.user_id}退群了。')
    else: 
        await del_user.send(f'{event.user_id}被{event.operator_id}送走了。')

@add_user.handle()
async def user_add(event: GroupRequestEvent):
    comment = event.comment.strip()
    playerName = re.findall(re.compile('答案：(.*)'), comment)[0].strip()
    session = event.group_id
    session = check_session(session)

    (BF1_SERVERS_DATA/f'{event.group_id}_apply').mkdir(exist_ok=True)
    res = await getPersonasByName(access_token, playerName)
    print(res)
    print(playerName)
    try:
        personaId,playerName = res
        print(playerName,personaId)
    except:
        try:
            res = await get_player_data(playerName)
            playerName = res['userName']
            personaId = res['id']
        except:
            reply = await add_user.send(f'收到{event.user_id}的加群请求: {playerName}(无效id)\n回复y同意进群，回复n+理由(可选)拒绝进群。')#
            with open(BF1_SERVERS_DATA/f'{event.group_id}_apply'/f'{reply["message_id"]}.txt','w') as f:
                f.write(f'{event.flag},{event.sub_type},{event.user_id}')
        else:
            reply = await add_user.send(f'收到{event.user_id}的加群请求: {playerName}(有效id)，战绩信息如下: \n回复y同意进群，回复n 理由(可选)拒绝进群。')#\n回复y同意进群，回复n+理由(可选)拒绝进群。
            with open(BF1_SERVERS_DATA/f'{event.group_id}_apply'/f'{reply["message_id"]}.txt','w') as f:
                f.write(f'{event.flag},{event.sub_type},{event.user_id},{personaId},{playerName}')
            with open(BF1_PLAYERS_DATA/f'{event.user_id}.txt','w') as f:
                f.write(str(personaId))
            file_dir = await asyncio.wait_for(draw_stat(remid, sid, sessionID, personaId, playerName),timeout=15)
            await add_user.send(MessageSegment.image(file_dir))
    else:
            reply = await add_user.send(f'收到{event.user_id}的加群请求: {playerName}(有效id)，战绩信息如下: \n回复y同意进群，回复n 理由(可选)拒绝进群。')#\n回复y同意进群，回复n+理由(可选)拒绝进群。
            with open(BF1_SERVERS_DATA/f'{event.group_id}_apply'/f'{reply["message_id"]}.txt','w') as f:
                f.write(f'{event.flag},{event.sub_type},{event.user_id},{personaId},{playerName}')
            with open(BF1_PLAYERS_DATA/f'{event.user_id}.txt','w') as f:
                f.write(str(personaId))
            file_dir = await asyncio.wait_for(draw_stat(remid, sid, sessionID, personaId, playerName),timeout=15)
            await add_user.send(MessageSegment.image(file_dir))
            
@approve_req.handle()
async def user_add(event: GroupMessageEvent):
    session = check_session(event.group_id)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        message = event.get_message().extract_plain_text().split(' ')
        bots = nonebot.get_bots()
        sign = 0
        for bot in bots.values():
            botlist = await bot.get_group_list()
            for i in botlist:
                if i["group_id"] == session:
                    sign = 1
                    break
            if sign == 1:
                break
        (BF1_SERVERS_DATA/f'{event.group_id}_apply').mkdir(exist_ok=True)
        message_id = reply_message_id(event)
        print(message_id)
        if message_id != None:
            #try:
                with open(BF1_SERVERS_DATA/f'{event.group_id}_apply'/f'{message_id}.txt','r') as f:
                    arg = f.read().split(',')
                if message[0] == 'y':
                    try:
                        personaId = arg[3]
                        userName = arg[4]
                        (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                        with open(BF1_PLAYERS_DATA/f'{session}'/f'{event.user_id}_{personaId}.txt','w') as f:
                            f.write(userName)
                    except:
                        pass
                    print(arg[0])
                    await bot.set_group_add_request(
                        flag = arg[0],
                        sub_type = arg[1],
                        approve = True
                    )
                else:
                    if(len(message) == 1):
                        await bot.set_group_add_request(
                            flag = arg[0],
                            sub_type = arg[1],
                            approve = False
                        )
                        await approve_req.finish('已拒绝入群')
                    else:
                        await bot.set_group_add_request(
                            flag = arg[0],
                            sub_type = arg[1],
                            approve = False,
                            reason = message[1],
                        )
                        await approve_req.finish(f'已拒绝入群。理由：{message[1]}')             
            #except:
            #    pass


@welcome_user.handle()
async def bf1_welcome(event:GroupMessageEvent, state:T_State):   
    message = _command_arg(state) or event.get_message()
    msg = html.unescape(message.extract_plain_text())
    
    (BF1_SERVERS_DATA/f'{event.group_id}_apply').mkdir(exist_ok=True)
    with open(BF1_SERVERS_DATA/f'{event.group_id}_apply'/f'config.txt','w',encoding="utf-8") as f:
        f.write(msg)
    await welcome_user.finish(MessageSegment.reply(event.message_id) + f'已配置入群欢迎: {msg}')

@get_user.handle()
async def user_get(event: GroupIncreaseNoticeEvent):
    session = event.group_id
    bots = nonebot.get_bots()

    sign = 0
    for bot in bots.values():
        botlist = await bot.get_group_list()
        for i in botlist:
            if i["group_id"] == session:
                sign = 1
                break
        if sign == 1:
            break
    if "config.txt" in os.listdir(BF1_SERVERS_DATA/f'{session}_apply'):
        with open(BF1_SERVERS_DATA/f'{event.group_id}_apply'/f'config.txt',"r",encoding="utf-8") as f:
            msg = f.read()
        await get_user.finish(MessageSegment.at(event.user_id) + " " + msg)
    else:
        try:
            with open(BF1_PLAYERS_DATA/f'{event.user_id}.txt','r') as f:
                personaId= int(f.read())
                personaIds = []
                personaIds.append(personaId)
                res1 = await upd_getPersonasByIds(remid, sid, sessionID, personaIds)
                playerName = res1['result'][f'{personaId}']['displayName']
            await bot.set_group_card(group_id=event.group_id, user_id=event.user_id, card=playerName)
            await get_user.send(f'欢迎入群，已自动将您绑定为{playerName}')
        except:
            await get_user.send(f'欢迎入群')

