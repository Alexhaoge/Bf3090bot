from nonebot.log import logger
from nonebot.params import _command_arg
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent
from nonebot.typing import T_State
from collections import deque

import os
import re
import asyncio
import traceback

from ..utils import PREFIX, LOGGING_FOLDER
from ..bf1rsp import *
from ..bf1draw import *
from ..secret import *
from ..rdb import *
from ..bf1helper import *

from .matcher import BF1_SLP,BF1_SLF,BF1_SLK

admin_logger_lock = asyncio.Lock() # Must define the lock in global scope

async def search_log(pattern: str|re.Pattern, limit: int = 50) -> list:
    """
    Search all log files by regex expression, time exhausting!
    """
    assert limit > 0
    matching_lines = []
    q = deque(maxlen=limit)
    async with admin_logger_lock:
        with open(LOGGING_FOLDER/'admin.log', 'r', encoding='UTF-8') as f:
            for line in f:
                if re.search(pattern, line):
                    q.append(line)
    while(len(q)):
        matching_lines.append(q.pop())
    n_remain = limit - len(matching_lines)
    if len(matching_lines) < limit:
        backups = sorted(os.listdir(LOGGING_FOLDER), reverse=True)
        for backup in backups:
            if backup.startswith('admin.log') and backup != 'admin.log':
                q.clear()
                async with admin_logger_lock:
                    with open(LOGGING_FOLDER/backup, 'r', encoding='UTF-8') as f:
                        for line in f:
                            if re.search(pattern, line):
                                if len(q) == n_remain:
                                    q.popleft()
                                q.append(line)
                n_remain = n_remain - len(q)
                while(len(q)):
                    matching_lines.append(q.pop())
                if n_remain <= 0:
                    break
    return matching_lines

@BF1_SLP.handle()
async def search_adminlog_byplayer(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        if not message.extract_plain_text().startswith(f'{PREFIX}'):
            playerName = message.extract_plain_text()
        remid, sid, sessionID, access_token = await get_one_random_bf1admin()
        try:
            personaId,userName,_ = await getPersonasByName(access_token, playerName)
        except RSPException as rsp_exc:
            await BF1_SLP.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_SLP.finish(MessageSegment.reply(event.message_id) + "无效id或网络错误\n" \
                                    + traceback.format_exception_only(e))

        pattern = re.compile(f'"maingroupqq": {groupqq}(.*)"pid": {personaId}')
        logs = await search_log(pattern)
        
        if len(logs) == 0:
            await BF1_SLP.finish(MessageSegment.reply(event.message_id) + '暂无有效log记录')
        
        file_dir = await asyncio.wait_for(draw_log(logs,remid,sid,sessionID),timeout=20)
        await BF1_SLF.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    else:
        await BF1_SLP.finish(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_SLF.handle()
async def search_adminlog_byserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    groupqq = await check_session(event.group_id)
    user_id = event.user_id
    arg = message.extract_plain_text().split()

    admin_perm = await check_admin(groupqq, user_id)
    if admin_perm:
        remid, sid, sessionID, access_token = await get_one_random_bf1admin()
        server_ind, server_id = await check_server_id(groupqq,arg[0])
        if not server_ind:
            await BF1_SLF.finish(MessageSegment.reply(event.message_id) + f'服务器{arg[0]}不存在')

        pattern = re.compile(f'"maingroupqq": {groupqq}(.*)"serverind": "{server_ind}"')
        logs = await search_log(pattern)

        if len(logs) == 0:
            await BF1_SLF.finish(MessageSegment.reply(event.message_id) + '暂无有效log记录')
        
        file_dir = await asyncio.wait_for(draw_log(logs,remid,sid,sessionID),timeout=20)
        await BF1_SLF.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    else:
        await BF1_SLF.finish(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_SLK.handle()
async def search_adminlog_bykeyword(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    if check_sudo(event.group_id, event.user_id):
        remid, sid, sessionID, access_token = await get_one_random_bf1admin()
        if not message.extract_plain_text().startswith(f'{PREFIX}'):
            pattern = re.compile(message.extract_plain_text())
        logs = await search_log(pattern)
        
        if len(logs) == 0:
            await BF1_SLP.finish(MessageSegment.reply(event.message_id) + '暂无有效log记录')
        
        file_dir = await asyncio.wait_for(draw_log(logs,remid,sid,sessionID),timeout=20)
        await BF1_SLF.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))