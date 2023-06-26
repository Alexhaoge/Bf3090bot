import nonebot
from nonebot.rule import Rule
from nonebot.plugin import on_notice
from nonebot.adapters.onebot.v11 import (
    Bot, Event, Message,
    GroupDecreaseNoticeEvent,
    GroupRequestEvent
)

from .bf1 import get_player_data,remid,sid,sessionID
from .bf1draw import draw_stat

async def _is_del_user(event: Event) -> bool:
    return isinstance(event, GroupDecreaseNoticeEvent)

async def _is_add_user(event: Event) -> bool:
    return isinstance(event, GroupRequestEvent)

del_user = on_notice(Rule(_is_del_user), priority=50, block=True)

add_user = on_notice(Rule(_is_add_user), priority=50, block=True)

@del_user.handle()
async def user_bye(event: GroupDecreaseNoticeEvent):
    if event.sub_type == 'leave':
        await del_user.send(f'{event.user_id}退群了。')
    else: 
        await del_user.send(f'{event.user_id}被{event.operator_id}送走了。')

@add_user.handle()
async def user_add(event: GroupRequestEvent):
    playerName = event.comment.split('\\')[1][4:]
    print(playerName)
    try:
        res = get_player_data(playerName)
    except:
        await add_user.send(f'收到{event.user_id}的加群请求，验证消息为: {playerName}(无效id)，回复y懒得做了')
    else:
        await draw_stat(remid, sid, sessionID, res, playerName)
        await add_user.send(f'收到{event.user_id}的加群请求，验证消息为: {playerName}(有效id)，战绩信息如下：回复y懒得做了')