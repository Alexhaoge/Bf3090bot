import nonebot
from nonebot import get_bot
from nonebot.rule import Rule
from nonebot.typing import T_State
from nonebot.params import CommandArg, Depends, _command_arg
from nonebot.plugin import on_notice, on_request, on_command
from nonebot.adapters.onebot.v11 import (
    Bot, Event, Message,MessageSegment,GroupMessageEvent,
    GroupDecreaseNoticeEvent, GroupIncreaseNoticeEvent,
    GroupRequestEvent,
)

from typing import Annotated
import asyncio
import time
import os
from .bf1 import get_player_data,remid,sid,sessionID
from .bf1draw import draw_stat
from .utils import BF1_PLAYERS_DATA

#message_id = 0

def reply_message_id(event: GroupMessageEvent) -> int:
    message_id = None
    for seg in event.original_message:
        if seg.type == "reply":
            message_id = int(seg.data["id"])
            break
    return message_id

async def _is_del_user(event: Event) -> bool:
    return isinstance(event, GroupDecreaseNoticeEvent)

async def _is_get_user(event: Event) -> bool:
    return isinstance(event, GroupIncreaseNoticeEvent)

async def _is_add_user(event: Event) -> bool:
    return isinstance(event, GroupRequestEvent)

del_user = on_notice(Rule(_is_del_user), priority=50, block=True)

get_user = on_notice(Rule(_is_get_user), priority=50, block=True)

add_user = on_request(Rule(_is_add_user), priority=50, block=True)

@del_user.handle()
async def user_bye(event: GroupDecreaseNoticeEvent):
    session = event.group_id
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
    playerName = event.comment.split('：')[2]
    try:
        res = await get_player_data(playerName)
    except:
        await add_user.send(f'收到{event.user_id}的加群请求: {playerName}(无效id)')#\n回复y同意进群，回复n拒绝进群，回复其他消息以回复的消息拒绝。
    else:
        await draw_stat(remid, sid, sessionID, res, playerName)
        await add_user.send(f'收到{event.user_id}的加群请求: {playerName}(有效id)，战绩信息如下: ')#\n回复y同意进群，回复n拒绝进群，回复其他消息以回复的消息拒绝
        with open(BF1_PLAYERS_DATA/f'{event.user_id}.txt','w') as f:
            f.write(playerName)
        await add_user.send(MessageSegment.image(f'file:///C:\\Users\\pengx\\Desktop\\1\\bf1\\bfchat_data\\bf1_servers\\Caches\\{playerName}.jpg'))


@get_user.handle()
async def user_get(event: GroupIncreaseNoticeEvent):
    bot = get_bot()
    try:
        with open(BF1_PLAYERS_DATA/f'{event.user_id}.txt','r') as f:
            playerName = str(f.read())
        await bot.set_group_card(group_id=event.group_id, user_id=event.user_id, card=playerName)
        await get_user.send(f'欢迎入群，已自动将您绑定为{playerName}')
    except:
        await get_user.send(f'欢迎入群，注意: 无效id或者管理员邀请入群')

