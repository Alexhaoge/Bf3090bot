import nonebot

from nonebot import get_driver
from nonebot import get_bot
from nonebot import on_command,on_notice, on_request

from nonebot.rule import Rule,to_me
from nonebot.log import logger
from nonebot.params import CommandArg, Depends, _command_arg, Arg, ArgStr, Received
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import (
    GROUP, Message, MessageEvent, MessageSegment, GroupMessageEvent, 
    Bot, GroupDecreaseNoticeEvent, GroupIncreaseNoticeEvent, GroupRequestEvent
)
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER

import httpx,html
import json
import os
import numpy
import zhconv
import asyncio
import random
import datetime
import traceback

from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_htmlrender import md_to_pic, html_to_pic

from sqlalchemy.future import select
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from typing import Union, Tuple, List
from random import choice

from .config import Config
from .bf1draw2 import draw_server_array2,upd_draw
from .template import apply_template, get_vehicles_data_md, get_weapons_data_md, get_group_list, get_server_md
from .utils import (
    PREFIX, BF1_PLAYERS_DATA, BF1_SERVERS_DATA, CODE_FOLDER,
    ASSETS_FOLDER, SUPERUSERS, CURRENT_FOLDER, LOGGING_FOLDER,
    request_API, get_wp_info,search_a,getsid,MapTeamDict
)
from .bf1rsp import *
from .bf1draw import *
from .secret import *
from .image import upload_img
from .rdb import *
from .redis_helper import redis_client

GAME = 'bf1'
LANG = 'zh-tw'

async def token_helper():
    async with async_db_session() as session:
        # Fetch admins from db
        admins = [row[0] for row in (await session.execute(select(Bf1Admins))).all()]
        tasks_token = [asyncio.create_task(upd_token(admin.remid, admin.sid)) for admin in admins]
        list_cookies_tokens = await asyncio.gather(*tasks_token) # Update tokens
        for i in range(len(admins)):
            admins[i].remid, admins[i].sid, admins[i].token = list_cookies_tokens[i]
        session.add_all(admins) # Write into db
        await session.commit()
        logger.info('Token updates complete')

async def session_helper():
    async with async_db_session() as session:
        admins = [row[0] for row in (await session.execute(select(Bf1Admins))).all()]
        tasks_session = [
            asyncio.create_task(upd_sessionId(admin.remid, admin.sid)) for admin in admins
        ]
        list_cookies_sessionIDs = await asyncio.gather(*tasks_session)
        logger.debug('\n'.join([t[2] for t in list_cookies_sessionIDs]))

        for i in range(len(admins)):
            admins[i].remid, admins[i].sid, admins[i].sessionid = list_cookies_sessionIDs[i]
        session.add_all(admins)
        await session.commit()
        logger.info('SessionID updates complete')

async def get_one_random_bf1admin() -> Tuple[str, str, str, str]:
    async with async_db_session() as session:
        admin = (await session.execute(select(Bf1Admins).order_by(func.random()).limit(1))).one()[0]
    return admin.remid, admin.sid, admin.sessionid, admin.token

async def get_bf1admin_by_serverid(serverid: int) -> Tuple[str, str, str, str] | None:
    async with async_db_session() as session:
        server_admin = (await session.execute(select(ServerBf1Admins).filter_by(serverid=serverid))).first()
        if server_admin:
            admin_pid = server_admin[0].pid
            admin = (await session.execute(select(Bf1Admins).filter_by(pid=admin_pid))).first()
            return admin[0].remid, admin[0].sid, admin[0].sessionid, admin[0].token
        else:
            return None, None, None, None

def reply_message_id(event: GroupMessageEvent) -> int:
    message_id = None
    for seg in event.original_message:
        if seg.type == "reply":
            message_id = int(seg.data["id"])
            break
    return message_id



admin_logger = logging.getLogger('adminlog')
def admin_logging_helper(
        incident: str, processor: int, groupqq: int, main_groupqq: int = None,
        server_ind: str = None, server_id: int = None, pid: int = None, 
        log_level: int = logging.INFO, **kwargs):
    """
    Admin logging helper function. TODO: typing check for preset arguments.
    """
    kwargs['incident'], kwargs['processor'], kwargs['groupqq'] = incident, processor, groupqq
    if main_groupqq:
        kwargs['maingroupqq'] =  main_groupqq
    if pid:
        kwargs['pid'] = pid
    if server_ind:
        kwargs['serverind'] = server_ind
    if server_id:
        kwargs['serverid'] = server_id
    admin_logger.log(level=log_level, msg=json.dumps(kwargs))

async def check_admin(groupqq: int, user_id: int) -> int:
    if user_id in SUPERUSERS:
        return True
    async with async_db_session() as session:
        perm_rec = (await session.execute(select(GroupAdmins).filter_by(groupqq=groupqq, qq=user_id))).all()
    return len(perm_rec)

def check_sudo(groupqq: int, user_id: int) -> int:
    return (user_id in SUPERUSERS) or (groupqq in SUDOGROUPS)
    
async def check_session(groupqq: int) -> int:
    async with async_db_session() as session:
        group_rec = (await session.execute(select(ChatGroups).filter_by(groupqq=int(groupqq)))).first()
    return int(group_rec[0].bind_to_group) if group_rec else 0

async def check_server_id(groupqq: int, server_ind: str) -> Tuple[str, int] | None:
    """
    Return the true server_ind, serverid from group server alias
    """
    server_id = str(server_ind)
    async with async_db_session() as session:
        group_server = (await session.execute(
            select(GroupServerBind).filter(GroupServerBind.groupqq==groupqq)\
                .filter(or_(GroupServerBind.ind == server_id, GroupServerBind.alias == server_ind))\
                )
            ).first()
    return (group_server[0].ind, group_server[0].serverid) if group_server else (None, None)

async def get_user_pid(groupqq:int, qq: int) -> Tuple[int, bool]:
    """
    Get pid the user bind within the given group
    """
    async with async_db_session() as session:
        player = (await session.execute(
            select(GroupMembers).filter_by(groupqq=groupqq, qq=qq)
        )).first()
    return player[0].pid if player else False

async def get_gameid_from_serverid(serverid: int) -> int | None:
    """
    Get gameid from redis based on serverid
    """
    gameid = await redis_client.get(f'gameid:{serverid}')
    if gameid:
        return int(gameid)
    else:
        logger.warning(f'Warning:gameid for {serverid} not find!')

async def add_vban(personaId: int, groupqq: int, serverId: int, reason: str, user_id: int):
    """
    Update: vban now records serverid(from Battlefield) instead group server code(1, 2, 3, etc.)
    """
    async with async_db_session() as session:
        exist_vban = (await session.execute(select(ServerVBans).filter_by(pid=personaId, serverid=serverId))).first()
        if not exist_vban:
            session.add(ServerVBans(
                pid = personaId, serverid = serverId,
                time = datetime.datetime.now(), reason = reason,
                processor = user_id, notify_group = groupqq
            ))
            await session.commit()

async def del_vban(personaId: int, serverId: int):
    """
    Update: vban now records serverid(from Battlefield) instead group server code(1, 2, 3)
    """
    async with async_db_session() as session:
        vban_rec = (await session.execute(select(ServerVBans).filter_by(pid=personaId, serverid=serverId))).first()
        if vban_rec:
            await session.delete(vban_rec[0])
            await session.commit()
    
async def get_server_num(groupqq:int) -> List[Tuple[str, int]]:
    """
    Return the (server_ind, serverid) of all the server bound to this chargroup
    """
    async with async_db_session() as session:
        stmt = select(GroupServerBind).filter_by(groupqq=groupqq).order_by(GroupServerBind.ind)
        servers = (await session.execute(stmt)).all()
        return [(row[0].ind, row[0].serverid) for row in servers]

async def update_or_bind_player_name(
        mode: int, groupqq: int, user_id: int,
        remid: str, sid: str, sessionID: str, access_token: str,
        playerName: str = None, usercard: str = None) -> dict:
    ret_dict = {}
    if mode == 1:
        try:
            personaId,userName,pidid = await getPersonasByName(access_token, playerName)
        except:
            ret_dict['err'] = '无效id'
            return ret_dict
    if mode == 2:
        async with async_db_session() as session:
            gm = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq, qq=user_id))).first()
            player = (await session.execute(select(Players).filter_by(qq=user_id))).first()
            if gm:
                personaId = gm[0].pid
                res = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
                userName = res['result'][f'{personaId}']['displayName']
                pidid = res['result'][f'{personaId}']['platformId']
                if player:
                    player[0].originid = userName
                    session.add(player[0])
                else:
                    session.add(Players(pid=gm[0].pid, originid=userName, qq=user_id))
            else:
                try:
                    playerName = usercard
                    personaId,userName,pidid = await getPersonasByName(access_token, playerName)
                except:
                    ret_dict['err'] = f'您还未绑定，尝试绑定{usercard}失败'
                    return ret_dict
                ret_dict['msg'] = f'您还未绑定，尝试绑定{usercard}成功'
                session.add(GroupMembers(groupqq=groupqq, qq=user_id, pid=personaId))
                if player:
                    player[0].originid = userName
                    session.add(player[0])
                else:
                    session.add(Players(pid=personaId, originid=userName, qq=user_id))
            await session.commit()                          
    ret_dict['userName'] = userName
    ret_dict['pid'] = personaId
    ret_dict['pidid'] = pidid
    return ret_dict

async def get_bf1status(game:str):
    return await request_API(game,'status',{"platform":"pc"})

async def get_player_id(player_name:str)->dict:
    return await request_API(GAME,'player',{'name':player_name})

async def get_pl(gameID:str)->dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url="https://api.gametools.network/bf1/players",
            params = {
                "gameid": f"{gameID}"
	            }
        )
    return response.json()

async def get_player_data(player_name:str)->dict:
    return await request_API(GAME,'all',{'name':player_name,'lang':LANG})

async def get_player_databyID(personaId)->dict:
    return await request_API(GAME,'all',{'playerid':personaId,'lang':LANG})

async def get_server_data(server_name:str)->dict:
    return await request_API(GAME,'servers',{'name':server_name,'lang':LANG,"platform":"pc","limit":20})

async def get_detailedServer_data(server_name:str)->dict:
    return await request_API(GAME,'detailedserver',{'name':server_name})

async def get_detailedServer_databyid(server_name)->dict:
    return await request_API(GAME,'detailedserver',{'gameid':server_name})

async def _is_del_user(event: Event) -> bool:
    return isinstance(event, GroupDecreaseNoticeEvent)

async def _is_get_user(event: Event) -> bool:
    return isinstance(event, GroupIncreaseNoticeEvent)

async def _is_add_user(event: Event) -> bool:
    return isinstance(event, GroupRequestEvent)

async def getbotforAps(bots,session:int):
    sign = 0
    for bot in bots.values():
        botlist = await bot.get_group_list()
        for i in botlist:
            if int(i["group_id"]) == session:
                sign = 1
                break
        if sign == 1:
            break
    return bot    
    
async def load_alarm_session_from_db():
    async with async_db_session() as session:
        stmt = select(ChatGroups).filter_by(alarm=True)
        alarm_groups = [int(r[0].groupqq) for r in (await session.execute(stmt)).all()]
        if len(alarm_groups):
            await redis_client.sadd("alarmsession", *alarm_groups)
        return alarm_groups

#bf1 help
BF1_PING = on_command(f"{PREFIX}ping",aliases={f'{PREFIX}原神'},block=True, priority=1)
BF1_INIT = on_command(f'{PREFIX}init', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_HELP = on_command(f"{PREFIX}help",block=True, priority=1)
BF1_FAQ = on_command(f"{PREFIX}FAQ",block=True, priority=1)
BF1_BOT = on_command(f"{PREFIX}bot", aliases={f'{PREFIX}管服号'}, block=True, priority=1)
BF1_CODE = on_command(f"{PREFIX}code", block=True, priority=1)
BF1_REPORT = on_command(f"{PREFIX}举报",aliases={f'{PREFIX}举办', f'{PREFIX}report'}, block=True, priority=1)

#bf1rsp
BF1_ADDADMIN = on_command(f'{PREFIX}addadmin', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_DELADMIN = on_command(f'{PREFIX}deladmin', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_ADMINLIST = on_command(f'{PREFIX}adminlist', aliases={f'{PREFIX}管理列表'}, block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_CHOOSELEVEL = on_command(f'{PREFIX}map', block=True, priority=1)
BF1_KICK = on_command(f'{PREFIX}k', aliases={f'{PREFIX}kick', f'{PREFIX}踢出'}, block=True, priority=1)
BF1_KICKALL = on_command(f'{PREFIX}kickall', aliases={f'{PREFIX}炸服', f'{PREFIX}清服'}, block=True, priority=1)
BF1_BAN = on_command(f'{PREFIX}ban', block=True, priority=1)
BF1_BANALL = on_command(f'{PREFIX}bana',aliases={f'{PREFIX}banall', f'{PREFIX}ba'}, block=True, priority=1)
BF1_UNBAN = on_command(f'{PREFIX}unban', block=True, priority=1)
BF1_UNBANALL = on_command(f'{PREFIX}unbana',aliases={f'{PREFIX}unbanall', f'{PREFIX}uba'}, block=True, priority=1)
BF1_VBAN = on_command(f'{PREFIX}vban', aliases={f'{PREFIX}vb'}, block=True, priority=1)
BF1_VBANALL = on_command(f'{PREFIX}vbana',aliases={f'{PREFIX}vbanall', f'{PREFIX}vba'}, block=True, priority=1)
BF1_UNVBAN = on_command(f'{PREFIX}unvban', aliases={f'{PREFIX}uvb',f'{PREFIX}uvban'} , block=True, priority=1)
BF1_UNVBANALL = on_command(f'{PREFIX}unvbana',aliases={f'{PREFIX}unvbanall', f'{PREFIX}uvba',f'{PREFIX}unvba'}, block=True, priority=1)
BF1_MOVE = on_command(f'{PREFIX}move', block=True, priority=1)
BF1_VIP = on_command(f'{PREFIX}vip', block=True, priority=1)
BF1_VIPLIST = on_command(f'{PREFIX}viplist', block=True, priority=1)
BF1_CHECKVIP = on_command(f'{PREFIX}checkvip', block=True, priority=1)
BF1_UNVIP = on_command(f'{PREFIX}unvip', block=True, priority=1)
BF1_PL = on_command(f'{PREFIX}pl', block=True, priority=1)
BF1_ADMINPL = on_command(f'{PREFIX}adminpl', block=True, priority=1)
BF1_PLS = on_command(f'{PREFIX}查黑队', block=True, priority=1)
BF1_PLSS = on_command(f'{PREFIX}查战队', block=True, priority=1)
BF1_PLA = on_command(f'{PREFIX}搜战队', block=True, priority=1)
BF1_PLAA = on_command(f'{PREFIX}查战队成员', aliases={f'{PREFIX}查成员'}, block=True, priority=1)
BF1_UPD = on_command(f'{PREFIX}配置', block=True, priority=1)
BF1_INSPECT = on_command(f'{PREFIX}查岗', block=True, priority=1)

#grouprsp
del_user = on_notice(Rule(_is_del_user), priority=1, block=True)
get_user = on_notice(Rule(_is_get_user), priority=1, block=True)
add_user = on_request(Rule(_is_add_user), priority=1, block=True)
welcome_user = on_command(f'{PREFIX}配置入群欢迎', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
approve_req = on_command('y',rule = to_me ,aliases={'n'},priority=1, block=True)

#bf1status
BF_STATUS = on_command(f'{PREFIX}bf status', block=True, priority=1)
BF1_STATUS = on_command(f'{PREFIX}bf1 status', aliases={f'{PREFIX}战地1', f'{PREFIX}status', f'{PREFIX}bf1'}, block=True, priority=1)
BF1_MODE= on_command(f'{PREFIX}bf1 mode', block=True, priority=1)
BF1_MAP= on_command(f'{PREFIX}bf1 map', block=True, priority=1)
BF1_SA= on_command(f'{PREFIX}查', block=True, priority=1)
BF1_INFO= on_command(f'{PREFIX}info', block=True, priority=1)
BF1_TYC= on_command(f'{PREFIX}tyc', aliases={f'{PREFIX}天眼查'}, block=True, priority=1)
BF1_F= on_command(f'{PREFIX}f', block=True, priority=1)
BF1_WP= on_command(f'{PREFIX}武器', aliases={f'{PREFIX}w', f'{PREFIX}wp', f'{PREFIX}weapon'}, block=True, priority=1)
BF1_S= on_command(f'{PREFIX}s', aliases={f'{PREFIX}stat', f'{PREFIX}战绩', f'{PREFIX}查询',f'{PREFIX}生涯'}, block=True, priority=1)
BF1_R= on_command(f'{PREFIX}r', aliases={f'{PREFIX}对局'}, block=True, priority=1)
BF1_RE= on_command(f'{PREFIX}最近', block=True, priority=1)
BF1_BIND_PID = on_command(f'{PREFIX}bind', aliases={f'{PREFIX}绑定', f'{PREFIX}绑id'}, block=True, priority=1)
BF1_EX= on_command(f'{PREFIX}交换', block=True, priority=1)
BF1_DRAW= on_command(f'{PREFIX}draw', block=True, priority=1)
BF1_ADMINDRAW= on_command(f'{PREFIX}admindraw', block=True, priority=1)

#bf1 server alarm
BF1_SERVER_ALARM = on_command(f'{PREFIX}打开预警', block=True, priority=1)
BF1_SERVER_ALARMOFF = on_command(f'{PREFIX}关闭预警', block=True, priority=1)

#bf1 super admin commands
BF1_BIND = on_command(f'{PREFIX}绑服', block=True, priority=1, permission=SUPERUSER)
BF1_REBIND = on_command(f'{PREFIX}改绑', block=True, priority=1, permission=SUPERUSER)
BF1_ADDBIND = on_command(f'{PREFIX}添加服别名', block=True, priority=1, permission=SUPERUSER)
BF1_SLP = on_command(f'{PREFIX}slog', aliases={f'{PREFIX}搜日志', f'{PREFIX}sl'}, block=True, priority=1)
BF1_SLF = on_command(f'{PREFIX}log', aliases={f'{PREFIX}服务器日志'}, block=True, priority=1)
BF1_SLK = on_command(f'{PREFIX}slogkey', aliases={f'{PREFIX}slk'}, block=True, priority=1)

@BF1_PING.handle()
async def bf1_ping(event:GroupMessageEvent, state:T_State):
    with Image.open(Path('file:///') / CURRENT_FOLDER/'ys.png') as im:
        await BF1_INIT.send(MessageSegment.reply(event.message_id) + MessageSegment.image(base64img(im)))


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

@BF1_HELP.handle()
async def bf_help(event:MessageEvent, state:T_State):
    with open(ASSETS_FOLDER/'Readme.md',encoding='utf-8') as f:
        md_help = f.read()
    
    md_help = md_help.format(p=PREFIX)

    pic = await md_to_pic(md_help, css_path=ASSETS_FOLDER/"github-markdown-dark.css",width=900)

    await BF1_HELP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(pic) + '捐赠地址：爱发电搜索Mag1Catz，所有收益将用于服务器运行。输入.code [代码]可以更换查战绩背景。\n使用EAC功能请直接输入.举报 id。\n更多问题请输入.FAQ查询或加群908813634问我。')

@BF1_FAQ.handle()
async def bf_faq(event:MessageEvent, state:T_State):
    file_dir = await draw_faq()
    #file_dir = Path('file:///') / CURRENT_FOLDER/'Caches'/'faq.png'
    await BF1_HELP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))

@BF1_BOT.handle()
async def bf1_init_botqq(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    
    async with async_db_session() as session:
        bf1admins = [row[0] for row in (await session.execute(select(Bf1Admins).order_by(Bf1Admins.id))).all()]
        pids = [admin.pid for admin in bf1admins]
        tmpid = choice(range(len(bf1admins)))
        userName_res = await upd_getPersonasByIds(
            bf1admins[tmpid].remid, bf1admins[tmpid].sid, bf1admins[tmpid].sessionid, pids)
        names = [userName_res['result'][str(pid)]['displayName'] for pid in pids]
        num_res = (await session.execute(select(ServerBf1Admins, func.count()).group_by(ServerBf1Admins.pid))).all()
        nums = {r[0].pid:r[1] for r in num_res}
    msg = ''
    for i in range(len(bf1admins)):
        admins = nums[bf1admins[i].pid] if bf1admins[i].pid in nums.keys() else 0
        if int(admins) < 20:
            msg = msg + f'{bf1admins[i].id}. {names[i]}: {admins}/20 \n'
    msg.rstrip()
    await BF1_BOT.send(MessageSegment.reply(event.message_id) + f'请选择未满的eaid添加服管：\n{msg}') 

@BF1_CODE.handle()
async def cmd_receive(event: GroupMessageEvent, state: T_State, pic: Message = CommandArg()):
    message = _command_arg(state) or event.get_message()
    user_id = event.user_id
    code = message.extract_plain_text().split(' ')[0]
    groupqq = await check_session(event.group_id)

    with open(CURRENT_FOLDER/'code.txt','r') as f:
        codearg = f.read().split()
    if code in codearg:
        async with async_db_session() as session:
            player_r = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq, qq=user_id))).first()
            if player_r:
                personaId = player_r[0].pid
                code_r = (await session.execute(select(BotVipCodes).filter_by(code=code))).first()
                if code_r:
                    exist_pid = code_r[0].pid
                    if int(exist_pid) != int(personaId):
                        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
                        res = await upd_getPersonasByIds(remid, sid, sessionID, [exist_pid])
                        userName = res['result'][f'{exist_pid}']['displayName']
                        await BF1_CODE.finish(MessageSegment.reply(event.message_id) + f'这个code已经被使用过，使用者id为：{userName}。')
                    else:
                        state["personaId"] = personaId
                else:
                    session.add(BotVipCodes(code=code, pid=personaId))
                    await session.commit()
                    state["personaId"] = personaId
            else:
                await BF1_CODE.finish(MessageSegment.reply(event.message_id) + '请先绑定eaid。')
    else:
        await BF1_CODE.finish(MessageSegment.reply(event.message_id) + '请输入正确的code。')

@BF1_CODE.got("Message_pic", prompt="请发送你的背景图片，最好为正方形jpg格式。如果发现发送一切违反相关法律规定的图片的行为，将永久停止你的bot使用权限！")
async def get_pic(bot: Bot, event: GroupMessageEvent, state: T_State, msgpic: Message = Arg("Message_pic")):
    for segment in msgpic:
        if segment.type == "image":
            pic_url: str = segment.data["url"]  # 图片链接
            logger.success(f"获取到图片: {pic_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(pic_url,timeout=20)
                image_data = response.content
                image = Image.open(BytesIO(image_data))
            
            image.convert("RGB").save(BF1_PLAYERS_DATA/'Caches'/f'{state["personaId"]}.jpg')

            await BF1_CODE.finish(MessageSegment.reply(event.message_id) + '绑定code完成。')

        else:
            await BF1_CODE.finish(MessageSegment.reply(event.message_id) + "你发送的不是图片，请以“图片”形式发送！")

@BF1_REPORT.handle()
async def cmd_receive_report(event: GroupMessageEvent, state: T_State, pic: Message = CommandArg()):
    message = _command_arg(state) or event.get_message()
    user_id = event.user_id
    playerName = message.extract_plain_text().split(' ')[0]
    
    try:
        access_token = (await get_one_random_bf1admin())[3]
        personaId,name,userId = await getPersonasByName(access_token, playerName)
    except:
        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'无效id')
    bfeac = await bfeac_checkBan(personaId)
    if bfeac['stat'] == '无':
        state['case_body'] = ''
        state['case_num'] = 0
        state['target_EAID'] = name
        state['txturl'] = []
        await BF1_REPORT.send(f'开始举报: {name}\n可以发送图片/文字/链接\n图片和文字请分开发送\n共计可以接收5次举报消息\n声明: 每次举报都会在后台记录举报者的qq号码，仅作为留档用。恶意举报将永久封停你的bot使用权限，情节严重者将封停群内所有成员的bot使用权。\n学习如何鉴挂: https://bitly.ws/YQAg')
    elif bfeac['stat'] == '已封禁':
        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'该玩家已被bfeac封禁，案件链接: {bfeac["url"]}')
    else:
        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'该玩家在bfeac已经有案件，但是没有被封禁，案件链接: {bfeac["url"]}。\n如果想要补充证据请直接注册账号并在case下方回复，管理员会看到并处理你的回复。')    

@BF1_REPORT.got("Message")
async def get_pic(bot: Bot, event: GroupMessageEvent, state: T_State, msgpic: Message = Arg("Message")):
    for segment in msgpic:
        if segment.is_text():
            if str(segment) == "确认":
                bg_url = "https://3090bot.oss-cn-beijing.aliyuncs.com/asset/3090.png"
                state['case_body'] += "<p><img class=\"img-fluid\" src=\"" + bg_url + "\"/></p>"

                res = await bfeac_report(state['target_EAID'],state['case_body'])
                try:
                    case_id = res['data']
                except:
                    await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'举报失败，请联系作者处理。')
                else:
                    with open(CURRENT_FOLDER/'bfeac_case'/f'{case_id}.txt','w') as f:
                        string = "\"qq\":" + str(event.user_id) + "\n\"group\":" + str(event.group_id)
                        f.write(string)
                    await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'举报成功，案件链接: https://bfeac.com/#/case/{case_id}。')
                
            elif str(segment) == "取消":
                await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'已取消举报。')
                
            elif str(segment) == "预览":
                msg_show = ''
                for body in state['txturl']:
                    if str(body).startswith('https://3090bot'):
                        msg_show += (MessageSegment.image(body) +'\n')
                    else:
                        msg_show += (body + '\n')
                await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + msg_show)
            else:
                if state['case_num'] < 5:
                    state['case_num'] += 1
                    state['case_body'] += "<p>" + str(segment) + "</p>"
                    state['txturl'].append(segment)
                    await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'文字上传完成\n发送确认以结束举报\n发送取消以取消举报\n发送预览以预览举报\n你还可以发送{5-state["case_num"]}条证据')
                else:
                    await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'能够发送的证据数量已满。')
        elif segment.type == "image":
            if state['case_num'] < 5:    
                pic_url: str = segment.data["url"]  # 图片链接
                logger.success(f"获取到图片: {pic_url}")
                async with httpx.AsyncClient() as client:
                    response = await client.get(pic_url,timeout=20)
                    image_data = response.content
                    image = Image.open(BytesIO(image_data))
                
                imageurl = upload_img(image,f"report{random.randint(1, 100000000000)}.png")
                state['case_num'] += 1
                state['case_body'] += "<p><img class=\"img-fluid\" src=\"" + imageurl + "\"/></p>"
                state['txturl'].append(imageurl)
                await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'图片上传完成\n发送确认以结束举报\n发送取消以取消举报\n发送预览以预览举报\n你还可以发送{5-state["case_num"]}条证据')
            else:
                await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'能够发送的证据数量已满。')    
        else:
            await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + "发送证据的格式不合法。")

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
        
        res = await upd_chooseLevel(remid, sid, sessionID, persistedGameId, levelIndex)
        if 'error' in res:
            if res['error']['message'] == 'ServerNotRestartableException':
                await BF1_CHOOSELEVEL.send(MessageSegment.reply(event.message_id) + '服务器未开启')
            elif res['error']['message'] == 'LevelIndexNotSetException':
                await BF1_CHOOSELEVEL.send(MessageSegment.reply(event.message_id) + 'sessionID失效')
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
            except:
                logger.error(traceback.format_exc())
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + f'无效id')

            res = await upd_kickPlayer(remid, sid, sessionID, gameId, personaId, reason)
            if 'error' in res:
                await BF1_KICK.send(MessageSegment.reply(event.message_id) + f'踢出玩家：{name}失败，理由：玩家不在服务器中、无法处置管理员或者bot没有权限.')
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
            remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
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

            await asyncio.gather(*tasks)
            for pid in personaIds:
                admin_logging_helper('kickall' if arg[0] == 'all' else 'kick', user_id, event.group_id,
                                     main_groupqq=groupqq, server_ind=pl_json['serverind'],
                                     server_id=server_id, pid=pid, reason=reason)
            await BF1_KICK.send(MessageSegment.reply(event.message_id) + f'已踢出{len(personaIds)-mode}个玩家，理由：{reason}')
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
        state["serverind"] = server_ind
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
        tasks = [
            asyncio.create_task(upd_kickPlayer(remid, sid, sessionID, gameId, i['id'], reason)) for i in pl['1']
        ]
        tasks.extend(
            [asyncio.create_task(upd_kickPlayer(remid, sid, sessionID, gameId, i['id'], reason)) for i in pl['2']]
        )
        await asyncio.gather(*tasks)
        
        for i in pl['1']:
            admin_logging_helper('kickall', event.user_id, event.group_id, 
                                 main_groupqq=groupqq, server_ind=server_ind,
                                 server_id=server_id, pid=i['id'], reason=reason)
        for i in pl['2']:
            admin_logging_helper('kickall', event.user_id, event.group_id,
                                 main_groupqq=groupqq, server_ind=server_ind,
                                 server_id=server_id, pid=i['id'], reason=reason)
        
        await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + f'已踢出{len(pl["1"])+len(pl["2"])}个玩家,理由: {reason}')          
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

            gameId = await get_bf1admin_by_serverid(server_id)
            remid,sid,sessionID,access_token = (await get_bf1admin_by_serverid(server_id))
            if not remid:
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            try:
                personaId,personaName,_ = await getPersonasByName(access_token, personaName)
            except:
                await BF1_BAN.finish(MessageSegment.reply(event.message_id) + '无效id')
            
            res = await upd_kickPlayer(remid, sid, sessionID, gameId, personaId, reason)
            res = await upd_banPlayer(remid, sid, sessionID, server_id, personaId)

            if 'error' in res:
                error_code = res["error"]["code"]
                reason = error_code_dict[error_code]
                await BF1_BAN.send(MessageSegment.reply(event.message_id) + f'封禁玩家：{personaName}失败，理由：{reason}')
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
            res = await upd_getPersonasByIds(remid, sid, sessionID, personaIds)
            personaName = res['result'][f'{personaId}']['displayName']    
            res = await upd_kickPlayer(remid, sid, sessionID, gameId, personaId, reason)
            res = await upd_banPlayer(remid, sid, sessionID, server_id, personaId)

            if 'error' in res:
                await BF1_BAN.send(MessageSegment.reply(event.message_id) + f'封禁玩家：{personaName}失败，理由：无法处置管理员')
            else:
                admin_logging_helper('ban', user_id, event.group_id, main_groupqq=groupqq,
                                     server_ind=pl_json['serverind'], server_id=server_id, pid=personaId, reason=reason)
                await BF1_BAN.send(MessageSegment.reply(event.message_id) + f'已封禁玩家：{personaName}，理由：{reason}')
                # TODO: ban logging
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
        except:
            await BF1_BANALL.finish(MessageSegment.reply(event.message_id) + '无效id')
        err_message = ''
        for server_ind, server_id in servers:
            gameId = await get_gameid_from_serverid(server_id)
            remid,sid,sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            if remid:
                tasks.append(asyncio.create_task(upd_banPlayer(remid, sid, sessionID, server_id, personaId)))
            else:
                err_message += f'\nbot没有服务器#{server_ind}管理权限'
        await asyncio.gather(*tasks)
        admin_logging_helper('banall', user_id, event.group_id,
                             main_groupqq=groupqq, pid=personaId, reason=reason)
        await BF1_BANALL.send(MessageSegment.reply(event.message_id) + f'已封禁玩家：{personaName}，理由：{reason}{err_message}')
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
        except:
            await BF1_UNBANALL.finish(MessageSegment.reply(event.message_id) + '无效id')
        err_message = ''
        for server_ind, server_id in servers:
            gameid = await get_gameid_from_serverid(server_id)
            remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
            if remid:                 
                tasks.append(asyncio.create_task(upd_unbanPlayer(remid, sid, sessionID, server_id, personaId)))
            else:
                err_message += f'\nbot没有服务器#{server_ind}管理权限'
        await asyncio.gather(*tasks)
        admin_logging_helper('unbanall', user_id, event.group_id, main_groupqq=groupqq, pid=personaId)
        await BF1_UNBANALL.send(MessageSegment.reply(event.message_id) + f'已解封玩家：{personaName}{err_message}')
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
    #    reason = zhconv.convert(arg[2], 'zh-tw')
        gameid = await get_gameid_from_serverid(server_id)
        remid,sid,sessionID,access_token = await get_bf1admin_by_serverid(server_id)
        if not remid:
            await BF1_UNBAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
        except:
            await BF1_UNBAN.finish(MessageSegment.reply(event.message_id) + '无效id')
        res = await upd_unbanPlayer(remid, sid, sessionID, server_id, personaId)

        if 'error' in res:
            await BF1_UNBAN.send(MessageSegment.reply(event.message_id) + f'解封玩家：{personaName}失败')
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
            gameId = await get_gameid_from_serverid(server_id)
            remid,sid,sessionID,access_token = await get_bf1admin_by_serverid(server_id)
            if not remid:
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            try:
                personaId,personaName,_ = await getPersonasByName(access_token, personaName)
            except:
                await BF1_VBAN.finish(MessageSegment.reply(event.message_id) + '无效id')

            await add_vban(personaId,groupqq,server_id,reason,user_id)
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
            res = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
            personaName = res['result'][f'{personaId}']['displayName']
                
            await add_vban(personaId,groupqq,server_id,reason,user_id)
            admin_logging_helper('vban', user_id, event.group_id, pl_json['serverind'], server_id, personaId, reason=reason)
            await BF1_VBAN.send(MessageSegment.reply(event.message_id) + f'已在{server_id}为玩家{personaName}添加VBAN，理由：{reason}')
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
        except:
            await BF1_VBANALL.finish(MessageSegment.reply(event.message_id) + '无效id')
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
        except:
            await BF1_UNVBANALL.finish(MessageSegment.reply(event.message_id) + '无效id')
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
        except:
            await BF1_UNVBAN.finish(MessageSegment.reply(event.message_id) + '无效id')

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
            except:
                await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + '无效id')
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
                else : await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + '移动失败,玩家不在服务器中')

                res = await upd_movePlayer(remid, sid, sessionID, gameId, personaId, teamId)

                if 'error' in res:
                    await BF1_MOVE.send(MessageSegment.reply(event.message_id) + '移动失败，可能是sessionID过期')
                else:
                    with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
                        zh_cn = json.load(f)
                    admin_logging_helper('move', event.user_id, event.group_id, main_groupqq=groupqq,
                                         server_ind=server_ind, server_id=server_id, pid=personaId)
                    await BF1_MOVE.send(MessageSegment.reply(event.message_id) + f'已移动玩家{personaName}至队伍{3-teamId}：{zh_cn[teamName]}')

            except:
                await BF1_MOVE.send(MessageSegment.reply(event.message_id) + 'API HTTP ERROR，请稍后再试')
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
            for i in range(len(personaIds)):
                res = await upd_movePlayer(remid, sid, sessionID, gameId, personaIds[i], teamIds[i])
                if not 'error' in res:
                    admin_logging_helper('move', event.user_id, event.group_id, main_groupqq=groupqq,
                                         server_ind=pl_json['serverind'], server_id=server_id, pid=personaIds[i])
            await BF1_MOVE.send(MessageSegment.reply(event.message_id) + f'已移动{len(arg)}个玩家。')
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
            except:
                await BF1_VIP.finish(MessageSegment.reply(event.message_id) + '无效id')
            day = int(arg[2]) if len(arg) > 2 else 36500
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
            res = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
            personaName = res['result'][f'{personaId}']['displayName']
            day = int(arg[1]) if len(arg) > 1 else 36500

        async with async_db_session() as session:
            exist_vip = (await session.execute(
                select(ServerVips).filter_by(serverid=server_id, pid=personaId)
            )).first()
            if exist_vip: # If vip exists, update the current vip
                exist_vip[0].expire += datetime.timedelta(days=day)
                nextday = datetime.datetime.strftime(exist_vip[0].expire, "%Y-%m-%d")
                session.add(exist_vip[0])
                await session.commit()
                await BF1_VIP.send(MessageSegment.reply(event.message_id) +\
                                    f"已为玩家{personaName}添加{day}天的vip({nextday}){'' if exist_vip[0].enabled else '(未生效)'}")
            else: # If vip does not exists, create a new record
                remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
                if not remid:
                    await BF1_VIP.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
                    
                gameid = await get_gameid_from_serverid(server_id)
                serverBL = await upd_detailedServer(remid, sid, sessionID, gameid)
                is_operation_server = serverBL['result']['serverInfo']['mapMode'] == 'BreakthroughLarge'
                # Add to db (not committed yey)
                new_vip = ServerVips(
                    serverid = server_id, pid = personaId, originid = personaName,
                    expire = datetime.datetime.now() + datetime.timedelta(days=day),
                    enabled = not is_operation_server
                )
                session.add(new_vip)
                nextday = datetime.datetime.strftime(new_vip.expire, "%Y-%m-%d")
                # For operation servers, do not send vip request immediately, set enabled to False and add to database
                if is_operation_server:
                    await session.commit() 
                    await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})(未生效)')
                # For other servers, send vip request immediately, set enabled to True
                else:
                    res = await upd_vipPlayer(remid, sid, sessionID, server_id, personaId)
                    if 'error' in res: # If request failed, roll back transaction
                        await session.rollback()
                        error_code = res["error"]["code"]
                        reason = error_code_dict[error_code]
                        await BF1_VIP.finish(MessageSegment.reply(event.message_id) + f'添加失败：{reason}')
                    else: # Request success then commit
                        await session.commit()
                        await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})')
            admin_logging_helper('vip', event.user_id, event.group_id, main_groupqq=groupqq,
                                 server_ind=server_ind, server_id=server_id, pid=personaId, operation_server=is_operation_server, day=day)
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
                if row[0].expire > dt_now:
                    vip_str += f"({datetime.datetime.strftime(row[0].expire, '%Y-%m-%d')})"
                    if not row[0].enabled:
                        vip_str += '(未生效)'
                else:
                    vip_str += '(已过期)'
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
        now_dt = datetime.datetime.now()
        if not remid:
            await BF1_CHECKVIP.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        
        async_tasks = []
        expire_or_enable = []
        n_add = n_remove = 0
        err_names = []
        async with async_db_session() as session:
            vip_rows = (await session.execute(select(ServerVips).filter_by(serverid=server_id).order_by(ServerVips.originid))).all()
            for i, v in enumerate(vip_rows):
                if v[0].expire < now_dt:
                    async_tasks.append(asyncio.create_task(upd_unvipPlayer(remid, sid, sessionID, server_id, v[0].pid)))
                    expire_or_enable.append((i, False))
                elif not v[0].enabled:
                    async_tasks.append(asyncio.create_task(upd_vipPlayer(remid, sid, sessionID, server_id, v[0].pid)))
                    expire_or_enable.append((i, True))
            results = await asyncio.gather(*async_tasks, return_exceptions=True)
            
            for i, res in zip(expire_or_enable, results):
                if isinstance(res, BaseException) or ("error" in res):
                    if isinstance(res, BaseException):
                        logger.error(traceback.format_exc(res))
                    else:
                        logger.error(str(res))
                    err_names.append(vip_rows[i[0]][0].originid)
                elif i[1]: # enabled vip to update
                    vip_rows[i[0]][0].enabled = True
                    session.add(vip_rows[i[0]][0])
                    n_add += 1
                else: # expired vip to delete
                    await session.delete(vip_rows[i[0]][0])
                    n_remove += 1
            await session.commit()
        msg = f"已添加{n_add}个vip，删除{n_remove}个vip，{len(err_names)}个vip处理失败"
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
        except:
            await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + '无效id')
        gameid = await get_gameid_from_serverid(server_id)
        serverBL = await upd_detailedServer(remid, sid, sessionID, gameid)
        is_operation = serverBL['result']['serverInfo']['mapMode'] == 'BreakthroughLarge'

        async with async_db_session() as session:
            vip = (await session.execute(select(ServerVips).filter_by(serverid=server_id, pid=personaId))).first()
            if vip:
                if is_operation: 
                    if vip[0].enabled:
                        # Enabled vip in operation server will not be requested or deleted immediated, we only set it to expired in database
                        vip[0].expire = datetime.datetime.now() - datetime.timedelta(days=2)
                        session.add(vip[0])
                        await session.commit()
                        await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + f'已移除玩家{personaName}的行动vip(需要check)')
                    else:
                        # Vip in operation server that does not come into effect will be deleted
                        await session.delete(vip[0])
                        await session.commit()
                        await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + f'已移除玩家{personaName}未生效的行动vip(不需要check)')
                else:
                    await session.delete(vip[0])
                    await session.commit()
            else:
                if is_operation:
                    await BF1_UNVIP.send(MessageSegment.reply(event.message_id) + f'您正在尝试删除未在bot数据库内的行动vip，请在删除完成后立刻进行切图处理！')

            res = await upd_unvipPlayer(remid, sid, sessionID, server_id, personaId)
            if 'error' in res:
                await session.rollback()
                await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + '移除失败，可能是sessionID失效')
            else:
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
        except:
            logger.error(traceback.format_exc())
            await BF1_PL.send(MessageSegment.reply(event.message_id) + '服务器未开启。')
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
        except:
            logger.error(traceback.format_exc())
            await BF1_ADMINPL.send(MessageSegment.reply(event.message_id) + '服务器未开启。')
 
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
        except:
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
        except:
            await BF1_PLSS.send(MessageSegment.reply(event.message_id) + '服务器未开启。')
    else:
        await BF1_PLSS.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员') 

@BF1_PLA.handle()
async def bf_pla(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    platoon = html.unescape(message.extract_plain_text())

    try:
        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
        file_dir = await asyncio.wait_for(draw_searchplatoons(remid, sid, sessionID,platoon), timeout=20)
        reply = await BF1_PLA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except:
        await BF1_PLA.send(MessageSegment.reply(event.message_id) + '连接超时')

@BF1_PLAA.handle()
async def bf_plaa(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    platoon = html.unescape(message.extract_plain_text())

    try:
        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
        file_dir = await asyncio.wait_for(draw_detailplatoon(remid, sid, sessionID,platoon), timeout=20)
        reply = await BF1_PLAA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except:
        await BF1_PLAA.send(MessageSegment.reply(event.message_id) + '连接超时')

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
            remid, sid, sessionID = (await get_bf1admin_by_serverid(server_id))[0:3]
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

            res = await upd_detailedServer(remid, sid, sessionID, gameId)
            
            rspInfo = res['result']['rspInfo']
            maps = rspInfo['mapRotations'][0]['maps']
            name = rspInfo['serverSettings']['name']
            description = rspInfo['serverSettings']['description']
            settings = rspInfo['serverSettings']['customGameSettings']

            with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
                zh_cn = json.load(f)

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

            res_pid = await upd_getPersonasByIds(remid, sid, sessionID, adminpids)
            res_tyc = await upd_getServersByPersonaIds(remid,sid,sessionID,adminpids)

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

@del_user.handle()
async def user_bye(event: GroupDecreaseNoticeEvent):
    async with async_db_session() as session:
        group_row = (await session.execute(select(ChatGroups).filter_by(groupqq=event.group_id))).first()
        if group_row:
            groupqq = group_row[0].bind_to_group
            stmt = select(GroupMembers).filter_by(groupqq=groupqq, qq=event.user_id)
            user_rec = (await session.execute(stmt)).all()
            for row in user_rec:
                await session.delete(row[0])
            await session.commit()
    if event.sub_type == 'leave':
        await del_user.send(f'{event.user_id}退群了。')
    else: 
        await del_user.send(f'{event.user_id}被{event.operator_id}送走了。')

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
        message = event.get_message().extract_plain_text().split(' ')
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
            logger.info('approve_req:123456789123456789')
            if message[0].strip().lower() == 'y':
                if 'personaId' in apply:
                    logger.info('approve_req:123456789123456789')
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

@BF_STATUS.handle()
async def bf_status(event:GroupMessageEvent, state:T_State):
    try:
        tasks = []
        tasks.append(asyncio.create_task(request_API('bf1942','status')))
        tasks.append(asyncio.create_task(request_API('bf2','status',{"platform":"pc"})))
        tasks.append(asyncio.create_task(request_API('bf3','status')))
        tasks.append(asyncio.create_task(request_API('bf4','status',{"platform":"pc"})))
        tasks.append(asyncio.create_task(request_API('bf1','status',{"platform":"pc"})))
        tasks.append(asyncio.create_task(request_API('bfv','status',{"platform":"pc"})))
        tasks.append(asyncio.create_task(request_API('bf2042','status')))
        bf1942_json, bf2_json, bf3_json, bf4_json, bf1_json, bf5_json, bf2042_json = await asyncio.gather(*tasks)

        try:
            bf1942 = bf1942_json['regions'][0]['soldierAmount']
            bf1942_s = bf1942_json['regions'][0]['serverAmount']
        except:
            bf1942 = bf1942_s = "接口错误"
        
        try:
            bf2 = bf2_json['regions'][0]['soldierAmount']
            bf2_s = bf2_json['regions'][0]['serverAmount']
        except:
            bf2 = bf2_s = "接口错误"
        
        try:
            bf3 = bf3_json['regions']['ALL']['amounts']['soldierAmount']
            bf3_s = bf3_json['regions']['ALL']['amounts']['serverAmount']
        except:
            bf3 = bf3_s = "接口错误"        
        
        try:
            bf4 = bf4_json['regions']['ALL']['amounts']['soldierAmount']
            bf4_s = bf4_json['regions']['ALL']['amounts']['serverAmount']       
        except:
            bf4 = bf4_s = "接口错误"        
        
        try:
            bf1 = bf1_json['regions']['ALL']['amounts']['soldierAmount']
            bf1_s = bf1_json['regions']['ALL']['amounts']['serverAmount']
        except:
            bf1 = bf1_s = "接口错误"
        
        try:
            bf5 = bf5_json['regions']['ALL']['amounts']['soldierAmount']
            bf5_s = bf5_json['regions']['ALL']['amounts']['serverAmount']
        except:
            bf5 = bf5_s = "接口错误"
        
        try:
            bf2042 = bf2042_json['regions']['ALL']['amounts']['soldierAmount']
            bf2042_s = bf2042_json['regions']['ALL']['amounts']['serverAmount']
        except:
            bf2042 = bf2042_s = "接口错误"
        await BF_STATUS.send(MessageSegment.reply(event.message_id) + f'战地pc游戏人数统计：\n格式：<服数> | <人数>\nbf1942：{bf1942_s} | {bf1942}\nbf2：{bf2_s} | {bf2}\nbf3：{bf3_s} | {bf3}\nbf4：{bf4_s} | {bf4}\nbf1：{bf1_s} | {bf1}\nbfv：{bf5_s} | {bf5}\nbf2042：{bf2042_s} | {bf2042}')
    except: 
        await BF_STATUS.send(MessageSegment.reply(event.message_id) + '无法获取到服务器数据。')

@BF1_STATUS.handle()
async def bf1_status(event:GroupMessageEvent, state:T_State):
    try:
        result = await get_bf1status('bf1')
        server_amount_all = result['regions']['ALL']['amounts']['serverAmount']
        server_amount_dice = result['regions']['ALL']['amounts']['diceServerAmount']
        amount_all = result['regions']['ALL']['amounts']['soldierAmount']
        amount_all_dice = result['regions']['ALL']['amounts']['diceSoldierAmount']
        amount_all_queue = result['regions']['ALL']['amounts']['queueAmount']
        amount_all_spe = result['regions']['ALL']['amounts']['spectatorAmount']
        amount_asia = result['regions']['Asia']['amounts']['soldierAmount']
        amount_asia_dice = result['regions']['Asia']['amounts']['diceSoldierAmount']
        amount_eu = result['regions']['EU']['amounts']['soldierAmount']
        amount_eu_dice = result['regions']['EU']['amounts']['diceSoldierAmount']
        await BF1_STATUS.send(MessageSegment.reply(event.message_id) + f'开启服务器：{server_amount_all}({server_amount_dice})\n游戏中人数：{amount_all}({amount_all_dice})\n排队/观战中：{amount_all_queue}/{amount_all_spe}\n亚服：{amount_asia}({amount_asia_dice})\n欧服：{amount_eu}({amount_eu_dice})')
    except: 
        await BF1_STATUS.send(MessageSegment.reply(event.message_id) + '无法获取到服务器数据。')

@BF1_MODE.handle()
async def bf1_mode(event:GroupMessageEvent, state:T_State):
    try:
        result = await get_bf1status('bf1')
        result = result['regions']['ALL']['modePlayers']
        AirAssault = result['AirAssault']
        Breakthrough = result['Breakthrough']
        BreakthroughLarge = result['BreakthroughLarge']
        Conquest = result['Conquest']
        Domination = result['Domination']
        Possession = result['Possession']
        Rush = result['Rush']
        TeamDeathMatch = result['TeamDeathMatch']
        TugOfWar = result['TugOfWar']
        ZoneControl = result['ZoneControl']
        await BF1_MODE.send(MessageSegment.reply(event.message_id) + f'模式人数统计：\n征服：{Conquest}\n行动：{BreakthroughLarge}\n小模式：{TeamDeathMatch+AirAssault+Breakthrough+Domination+Possession+Rush+TugOfWar+ZoneControl}')
    except: 
        await BF1_MODE.send(MessageSegment.reply(event.message_id) + '无法获取到服务器数据。')

@BF1_MAP.handle()
async def bf1_map(event:GroupMessageEvent, state:T_State):
    try:
        result = await get_bf1status('bf1')
        result = result['regions']['ALL']['mapPlayers']
        result = sorted(result.items(), key=lambda item:item[1], reverse=True)
        print(result)
        with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
            zh_cn = json.load(f)
        for i in range(10):
            result[i] = list(result[i])
            result[i][0] = zh_cn[f'{result[i][0]}']
        await BF1_MAP.send(MessageSegment.reply(event.message_id) + f'地图游玩情况：\n1.{result[0][0]}：{result[0][1]}\n2.{result[1][0]}：{result[1][1]}\n3.{result[2][0]}：{result[2][1]}\n4.{result[3][0]}：{result[3][1]}\n5.{result[4][0]}：{result[4][1]}\n6.{result[5][0]}：{result[5][1]}\n7.{result[6][0]}：{result[6][1]}\n8.{result[7][0]}：{result[7][1]}\n9.{result[8][0]}：{result[8][1]}\n10.{result[9][0]}：{result[9][1]}')
    except: 
        await BF1_MAP.send(MessageSegment.reply(event.message_id) + '无法获取到服务器数据。')

@BF1_SA.handle()
async def bf1_sa(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    mode = 0

    logger.debug(arg)
    playerName = None
    if len(arg) == 1:
        searchmode = arg[0]
        mode = 2
    else:
        searchmode = arg[0]
        playerName = arg[1]
        mode = 1
    logger.debug(f'mode={mode}')

    groupqq = await check_session(event.group_id)
    user_id = event.user_id
    usercard = event.sender.card
    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    
    ret_dict = await update_or_bind_player_name(
        mode, groupqq, user_id, remid, sid, sessionID, access_token, playerName, usercard
    )
    if 'err' in ret_dict:
        await BF1_SA.finish(MessageSegment.reply(event.message_id) + ret_dict['err'])
    elif 'msg' in ret_dict:
        await BF1_SA.send(MessageSegment.reply(event.message_id) + ret_dict['msg'])
    personaId, userName = ret_dict['pid'], ret_dict['userName']

    if searchmode == 'vban':
        num,name,reason = search_vban(personaId)
    else:
        num,name = search_a(personaId,searchmode)
        reason = []
    search_modes = {'o': '', 'a': '的管理', 'v': '的vip', 'b':'的ban位', 'vban': '的vban位'}
    if searchmode in search_modes:
        msg_title = f'玩家{userName}共拥有{num}个服务器' + search_modes[searchmode] + (':' if num else '')
        await BF1_SA.send(MessageSegment.reply(event.message_id) + msg_title)    
        if num:
            file_dir = await draw_a(num,name,reason,personaId)
            await BF1_SA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))

@BF1_INFO.handle()
async def bf1_info(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    logger.info(message.extract_plain_text())

    serverName = message.extract_plain_text()
    serverName = html.unescape(serverName)
    remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]

    try:
        res = await upd_servers(remid, sid, sessionID, serverName)
        res = res['result']['gameservers']
        gameId = res[0]['gameId']
        servername = res[0]['name']
        servermap = res[0]['mapNamePretty']
        serveramount = res[0]['slots']['Soldier']['current']
        serverspect = res[0]['slots']['Spectator']['current']
        serverque = res[0]['slots']['Queue']['current']
        servermaxamount = res[0]['slots']['Soldier']['max']
        servermode = res[0]['mapModePretty']
        serverinfo = res[0]['description']

        res_0 = await upd_detailedServer(remid, sid, sessionID, gameId)
        serverstar = res_0['result']['serverInfo']['serverBookmarkCount']
        guid = res_0['result']['serverInfo']['guid']
        rspInfo = res_0['result']['rspInfo']
        serverid = rspInfo['server']['serverId']
        ownerid = rspInfo['server']['ownerId']
        createdDate = rspInfo.get("server", {}).get("createdDate")
        createdDate = datetime.datetime.fromtimestamp(int(createdDate) / 1000)
        expirationDate = rspInfo.get("server", {}).get("expirationDate")
        expirationDate = datetime.datetime.fromtimestamp(int(expirationDate) / 1000)
        updatedDate = rspInfo.get("server", {}).get("updatedDate")
        updatedDate = datetime.datetime.fromtimestamp(int(updatedDate) / 1000)

        personaIds = []
        personaIds.append(ownerid)
        res1 = await upd_getPersonasByIds(remid, sid, sessionID, personaIds)
        userName = res1['result'][f'{ownerid}']['displayName']
    except: 
        await BF1_INFO.send(MessageSegment.reply(event.message_id) + '未查询到数据')
    else:
        status1 = servermode + '-' +servermap
        status1 = zhconv.convert(status1,'zh-cn')
        status2 = f'{serveramount}/{servermaxamount}[{serverque}]({serverspect})'
        status3 = f'★{serverstar}'
        msg = f'{servername}\n人数: {status2} {status3}\n地图: {status1}\nGameId: {gameId}\nGuid: {guid}\nServerId: {serverid}\n创建时间: {createdDate}\n续费时间: {updatedDate}\n到期时间: {expirationDate}\n服主EAID: {userName}'
        await BF1_INFO.send(MessageSegment.reply(event.message_id) + msg)

@BF1_TYC.handle()
async def bf1_tyc(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    user_id = event.user_id
    groupqq = await check_session(event.group_id)
    usercard = event.sender.card

    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    if reply_message_id(event) == None:
        playerName = message.extract_plain_text()
        mode = 2 if playerName.startswith(f'{PREFIX}') else 1

        ret_dict = await update_or_bind_player_name(
            mode, groupqq, user_id, remid, sid, sessionID, access_token, playerName, usercard
        )
        if 'err' in ret_dict:
            await BF1_TYC.finish(MessageSegment.reply(event.message_id) + ret_dict['err'])
        elif 'msg' in ret_dict:
            await BF1_TYC.send(MessageSegment.reply(event.message_id) + ret_dict['msg'])
        personaId, userName, pidid = ret_dict['pid'], ret_dict['userName'], ret_dict['pidid']
    
    else:
        redis_pl = await redis_client.get(f"pl:{groupqq}:{reply_message_id(event)}")
        if not redis_pl:
            await BF1_TYC.finish(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
        pl_json = json.loads(redis_pl)
        for i in pl_json['pl']:
            if int(i['slot']) == int(arg[0]):
                personaId = i['id']
                break
        res1 = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
        userName = res1['result'][f'{personaId}']['displayName']
        pidid = res1['result'][f'{personaId}']['platformId']
            
    msg = await tyc(remid,sid,sessionID,personaId,userName,pidid)
    await BF1_TYC.send(MessageSegment.reply(event.message_id) + msg)

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
                1/0
            else:
                try:
                    file_dir = await asyncio.wait_for(draw_server(remid, sid, sessionID, serverName,res), timeout=15)
                    await BF1_F.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                except:
                    await BF1_F.send(MessageSegment.reply(event.message_id) + '连接超时')
        except: await BF1_F.send(MessageSegment.reply(event.message_id) + '未查询到数据')
    if mode == 2:
        groupqq = await check_session(event.group_id)
        servers = await get_server_num(groupqq)
        gameids = []
        for server_ind, server_id in servers:
            gameid = await get_gameid_from_serverid(server_id)
            gameids.append(gameid)
        #try:
        file_dir = await asyncio.wait_for(draw_f(gameids,groupqq,remid, sid, sessionID), timeout=15)
        await BF1_F.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        #except:
        #    await BF1F.send(MessageSegment.reply(event.message_id) + '连接超时')

@BF1_S.handle()
async def bf1_statimage(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    usercard = event.sender.card
    user_id = event.user_id

    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    if reply_message_id(event) == None:
        playerName = message.extract_plain_text()
        mode = 2 if playerName.startswith(f'{PREFIX}') else 1
        logger.debug(f'mode={mode}')

        ret_dict = await update_or_bind_player_name(
            mode, groupqq, user_id, remid, sid, sessionID, access_token, playerName, usercard
        )
        if 'err' in ret_dict:
            await BF1_S.finish(MessageSegment.reply(event.message_id) + ret_dict['err'])
        elif 'msg' in ret_dict:
            await BF1_S.send(MessageSegment.reply(event.message_id) + ret_dict['msg'])
        personaId, userName = ret_dict['pid'], ret_dict['userName']

    else:
        redis_pl = await redis_client.get(f"pl:{groupqq}:{reply_message_id(event)}")
        if not redis_pl:
            await BF1_S.finish(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
        pl_json = json.loads(redis_pl)
        personaId = None
        for i in pl_json['pl']:
            if int(i['slot']) == int(arg[0]):
                personaId = i['id']
                break
        if personaId:
            res1 = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
            userName = res1['result'][f'{personaId}']['displayName']
        else:
            await BF1_S.finish(MessageSegment.reply(event.message_id)+'请选择正确的玩家序号')
    try:
        file_dir = await asyncio.wait_for(draw_stat(remid, sid, sessionID, personaId, userName), timeout=15)
        await BF1_S.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except asyncio.TimeoutError:
        await BF1_S.send(MessageSegment.reply(event.message_id) + '连接超时')

@BF1_WP.handle()
async def bf1_wp(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message() 
    message = message.extract_plain_text()
    groupqq = await check_session(event.group_id)
    usercard = event.sender.card
    user_id = event.user_id

    if message.endswith("行") or message.endswith("列"):
        row_arg = re.findall(r'(\d+)行', message)
        row = int(row_arg[0]) if len(row_arg) else 4
        col_arg = re.findall(r'(\d+)列', message)
        col = int(col_arg[0]) if len(col_arg) else 4
        if row > 7 or col < 2 or col > 7:
            await BF1_WP.finish(MessageSegment.reply(event.message_id) + '行列数设置不合法，允许1-7行和2-7列')
        index = message.rfind(" ")
        if index != -1:
            message = message[:index]
        else:
            message = ".w"
    else:
        row = 5
        col = 2
    arg = message.split(' ') 

    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    if reply_message_id(event) == None:
        mode = 0
        playerName = None
        if message.startswith(f'{PREFIX}'):
            wpmode = 0
            mode = 2
        else:
            if len(message.split(' ')) == 1:
                [playerName,wpmode,mode] = get_wp_info(message,user_id)
            else:
                playerName = message.split(' ')[1]
                mode = 1
                wpmode = get_wp_info(message.split(' ')[0],user_id)[1]
        logger.debug(f'mode={mode},wpmode={wpmode}')

        ret_dict = await update_or_bind_player_name(
            mode, groupqq, user_id, remid, sid, sessionID, access_token, playerName, usercard
        )
        if 'err' in ret_dict:
            await BF1_WP.finish(MessageSegment.reply(event.message_id) + ret_dict['err'])
        elif 'msg' in ret_dict:
            await BF1_WP.send(MessageSegment.reply(event.message_id) + ret_dict['msg'])
        personaId, userName = ret_dict['pid'], ret_dict['userName']
        
    else:
        redis_pl = await redis_client.get(f"pl:{groupqq}:{reply_message_id(event)}")
        if not redis_pl:
            await BF1_WP.finish(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
        pl_json = json.loads(redis_pl)
        personaId = None
        for i in pl_json['pl']:
            if int(i['slot']) == int(arg[-1]):
                personaId = i['id']
                break
        if not personaId:
            await BF1_WP.finish(MessageSegment.reply(event.message_id)+'请选择正确的玩家序号')
        
        wpmode = get_wp_info(message.split(' ')[0],user_id)[1]
        res1 = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
        userName = res1['result'][f'{personaId}']['displayName']
    
    try:
        file_dir = await asyncio.wait_for(draw_wp(remid, sid, sessionID, personaId, userName, wpmode, col, row), timeout=15)
        await BF1_WP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except asyncio.TimeoutError:
        await BF1_WP.send(MessageSegment.reply(event.message_id) + '连接超时')

@BF1_R.handle()
async def bf1_recent(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    groupqq = await check_session(event.group_id)
    usercard = event.sender.card
    user_id = event.user_id

    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    playerName = message.extract_plain_text()
    mode = 2 if playerName.startswith(f'{PREFIX}') else 1
    logger.debug(f'mode={mode}')

    ret_dict = await update_or_bind_player_name(
        mode, groupqq, user_id, remid, sid, sessionID, access_token, playerName, usercard
    )
    if 'err' in ret_dict:
        await BF1_R.finish(MessageSegment.reply(event.message_id) + ret_dict['err'])
    elif 'msg' in ret_dict:
        await BF1_R.send(MessageSegment.reply(event.message_id) + ret_dict['msg'])
    personaId, userName = ret_dict['pid'], ret_dict['userName']

    try:
        file_dir = await asyncio.wait_for(draw_r(remid, sid, sessionID, personaId, userName), timeout=60)
        if str(file_dir) != '0':
            await BF1_R.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        else:
            await BF1_R.send(MessageSegment.reply(event.message_id) + "暂无有效对局信息，请检查BTR服务器是否正常。")
    except Exception as e: 
        await BF1_R.send(MessageSegment.reply(event.message_id) + str(e))

@BF1_RE.handle()
async def bf1_recent1(event:GroupMessageEvent, state:T_State):
    BF1_RE.finish(MessageSegment.reply(event.message_id) + f'此功能暂时关闭，查询最近对局请使用{PREFIX}r')    
    message = _command_arg(state) or event.get_message()
    groupqq = await check_session(event.group_id)
    usercard = event.sender.card
    user_id = event.user_id

    mode = 0
    if message.extract_plain_text().startswith(f'{PREFIX}'):
        mode = 2
    else:
        playerName = message.extract_plain_text()
        mode = 1
    
    print(f'mode={mode}')

    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    playerName = message.extract_plain_text()
    mode = 2 if playerName.startswith(f'{PREFIX}') else 1
    logger.debug(f'mode={mode}')

    ret_dict = await update_or_bind_player_name(
        mode, groupqq, user_id, remid, sid, sessionID, access_token, playerName, usercard
    )
    if 'err' in ret_dict:
        await BF1_RE.finish(MessageSegment.reply(event.message_id) + ret_dict['err'])
    elif 'msg' in ret_dict:
        await BF1_RE.send(MessageSegment.reply(event.message_id) + ret_dict['msg'])
    personaId, userName = ret_dict['pid'], ret_dict['userName']

    try:
        file_dir = await asyncio.wait_for(draw_re(remid, sid, sessionID, personaId, userName), timeout=35)
        if str(file_dir) != '0':
            await BF1_RE.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        else:
            await BF1_RE.send(MessageSegment.reply(event.message_id) + "暂无有效对局信息，请检查BTR服务器是否正常。")
    except: 
        await BF1_RE.send(MessageSegment.reply(event.message_id) + 'btr天天炸，一拳给它打爆！')

@BF1_BIND_PID.handle()
async def bf1_bindplayer(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    user_id = event.user_id
    groupqq = await check_session(event.group_id)
    usercard = event.sender.card

    if message.extract_plain_text().startswith(f'{PREFIX}'):
        playerName = usercard
    else:
        playerName = message.extract_plain_text()

    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    try:
        personaId,userName,_ = await getPersonasByName(access_token, playerName)
    except:
        await BF1_BIND_PID.finish(MessageSegment.reply(event.message_id) + '绑定失败，无效id或http error')
    
    async with async_db_session() as session:
        gm = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq, qq=user_id))).first()
        if gm:
            gm[0].pid = personaId
            session.add(gm[0])
        else:
            session.add(GroupMembers(pid=personaId, groupqq=groupqq, qq=user_id))
        player = (await session.execute(select(Players).filter_by(qq=user_id))).first()
        if player:
            player[0].originid = userName
            player[0].pid = personaId
            session.add(player[0])
        else:
            session.add(Players(pid=personaId, originid=userName, qq=user_id))
        await session.commit()                          
    
    await BF1_BIND_PID.send(MessageSegment.reply(event.message_id) + f'已绑定: {userName}')

@BF1_EX.handle()
async def bf1_ex(event:GroupMessageEvent, state:T_State):
    try:
        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
        file_dir = await asyncio.wait_for(draw_exchange(remid, sid, sessionID), timeout=35)
        await BF1_EX.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except: 
        await BF1_EX.send(MessageSegment.reply(event.message_id) + '连接超时')

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
    except: 
        await BF1_BIND.finish('无法获取到服务器数据。')
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

@BF1_SERVER_ALARM.handle()
async def bf1_server_alarm(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    try:
        arg = message.extract_plain_text().split(' ')
        groupqq = int(arg[0])
    except:
        groupqq = event.group_id
    user_id = event.user_id
    groupqq_main = await check_session(groupqq)
    if not groupqq_main:
        await BF1_SERVER_ALARM.finish(MessageSegment.reply(event.message_id) + '本群组未初始化')
    admin_perm = await check_admin(groupqq_main, user_id)
    if admin_perm:
        await redis_client.sadd('alarmsession', groupqq)
        async with async_db_session() as session:
            group_r = (await session.execute(select(ChatGroups).filter_by(groupqq=groupqq))).first()
            if group_r[0].alarm:
                await BF1_SERVER_ALARM.send(f'请不要重复打开')
            else:
                group_r[0].alarm = True
                session.add(group_r[0])
                await session.commit()
                await BF1_SERVER_ALARM.send(f'已打开预警，请注意接收消息')
    else:
        await BF1_SERVER_ALARM.send('你不是本群组的管理员')

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
                await BF1_SERVER_ALARMOFF.send('已关闭预警')
            else:
                await BF1_SERVER_ALARMOFF.send('本群组未打开预警')
    else:
        await BF1_SERVER_ALARMOFF.send('你不是本群组的管理员')


@BF1_DRAW.handle()
async def bf1_draw_server_array(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    _, server_id = await check_server_id(groupqq,arg[0])
    gameId = await get_gameid_from_serverid(server_id)
        
        # server_array = await request_API(GAME,'serverarray', {'gameid': GameId, 'days': days})
    try:
        img = draw_server_array2(str(gameId))
        await BF1_DRAW.send(MessageSegment.reply(event.message_id) + MessageSegment.image(img))
    except:
        await BF1_DRAW.send(MessageSegment.reply(event.message_id) + traceback.format_exc(2))

@BF1_ADMINDRAW.handle()
async def bf1_admindraw_server_array(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    server = html.unescape(message.extract_plain_text())
    groupqq = event.group_id

    if check_sudo(groupqq, event.user_id):
        try:
            remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
            result = await upd_servers(remid, sid, sessionID, server)
            gameId = result['result']['gameservers'][0]['gameId']
        except: 
            await BF1_ADMINDRAW.finish('无法获取到服务器数据。')
        
        try:
            img = draw_server_array2(str(gameId))
            await BF1_ADMINDRAW.send(MessageSegment.reply(event.message_id) + MessageSegment.image(img))
        except:
            await BF1_ADMINDRAW.send(MessageSegment.reply(event.message_id) + traceback.format_exc(2))

admin_logger_lock = asyncio.Lock() # Must define the lock in global scope
async def search_log(pattern: str|re.Pattern, limit: int = 50) -> list:
    """
    Search all log files by regex expression, time exhausting!
    """
    matching_lines = []
    async with admin_logger_lock:
        with open(LOGGING_FOLDER/'admin.log', 'r', encoding='UTF-8') as f:
            for line in f:
                if re.search(pattern, line):
                    matching_lines.append(line)
                    if len(matching_lines) == limit:
                        break
    if len(matching_lines) < limit:
        backups = sorted(os.listdir(LOGGING_FOLDER), reverse=True)
        for backup in backups:
            if backup != 'admin.log':
                async with admin_logger_lock:
                    with open(LOGGING_FOLDER/backup, 'r', encoding='UTF-8') as f:
                        for line in f:
                            if re.search(pattern, line):
                                matching_lines.append(line)
                                if len(matching_lines) == limit:
                                    break
    return sorted(matching_lines, reverse=True)

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
        except:
            logger.warning(traceback.format_exc(2))
            await BF1_SLP.finish(MessageSegment.reply(event.message_id) + '无效id或网络错误')
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
    arg = message.extract_plain_text().split(' ')

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

######################################## Schedule job parts #########################################
async def get_server_status(groupqq: int, ind: str, serverid: int, bot: Bot, draw_dict: dict): 
    with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
        zh_cn = json.load(f)
    try:
        gameId = await get_gameid_from_serverid(serverid)
        status = draw_dict[f"{gameId}"]
    except:
        logger.debug(f'No data for gameid:{gameId}')
    else:
        playerAmount = int(status['serverAmount'])
        maxPlayers = int(status['serverMax'])
        map = zh_cn[status['map']]
        #print(playerAmount,maxPlayers,map)
        #print(f'{bot}{session}群{i+1}服人数{playerAmount}')
        try:
            #if True: # Test
            if max(maxPlayers-34,maxPlayers/3) < playerAmount < maxPlayers-10:
                alarm_amount = await redis_client.hincrby(f'alarmamount:{groupqq}', ind)
                await bot.send_group_msg(group_id=groupqq, message=f'第{alarm_amount}次警告：{ind}服人数大量下降到{playerAmount}人，请注意。当前地图为：{map}。')
                return 1
            else:
                return 0
        except:
            logger.error(traceback.format_exc(2))
            return 0

async def kick_vbanPlayer(pljson: dict, sgids: list, vbans: dict, draw_dict: dict):
    tasks = []
    report_list = []
    personaIds = []

    for serverid, gameId in sgids:
        pl = pljson[str(gameId)]
        vban_ids = vbans[serverid]['pid']
        vban_reasons = vbans[serverid]['reason']
        vban_groupqqs = vbans[serverid]['groupqq']

        remid, sid, sessionID, access_token  = await get_bf1admin_by_serverid(serverid)
        if not remid:
            continue

        pl_ids = [int(s['id']) for s in pl['1']] + [int(s['id']) for s in pl['2']]
        bfeac_ids = await bfeac_checkBanMulti(pl_ids)
        if bfeac_ids != []:
            reason = "Banned by bfeac.com"
            for personaId in bfeac_ids:
                tasks.append(upd_kickPlayer(remid,sid,sessionID,gameId,personaId,reason))

        for personaId in pl_ids:
            if personaId in vban_ids:
                index = vban_ids.index(personaId)
                reason = vban_reasons[index]
                groupqq = vban_groupqqs[index]
                personaIds.append(personaId)
                report_list.append(
                    {
                        "gameId": gameId,
                        "personaId": personaId,
                        "reason": reason, 
                        "groupqq": groupqq
                        }
                    )
                tasks.append(upd_kickPlayer(remid,sid,sessionID,gameId,personaId,reason))

    res = await asyncio.gather(*tasks)
    logger.debug(res)
    remid2, sid2, sessionID2, access_token2  = await get_one_random_bf1admin()
    res_pid = await upd_getPersonasByIds(remid2,sid2,sessionID2,personaIds)

    if res != []:
        bots = nonebot.get_bots()
        for report_dict in report_list:
            try:
                gameId = report_dict["gameId"]
                reason = report_dict["reason"]
                personaId = report_dict["personaId"]
                groupqq = report_dict["groupqq"]

                name = draw_dict[f"{gameId}"]["server_name"]
                eaid = res_pid['result'][f'{personaId}']['displayName']
                report_msg = f"Vban提示: 在{name}踢出{eaid}, 理由: {reason}"
                logger.info(report_msg)
                bot = await getbotforAps(bots,groupqq)
                reply = await bot.send_group_msg(group_id=groupqq, message=report_msg.rstrip())
                logger.info(reply)
            except Exception as e:
                logger.error(e)
                continue


async def start_vban(sgids: list, vbans: dict, draw_dict: dict):
    try:
        #pljson = await upd_blazeplforvban([t[1] for t in sgids])
        pljson = await Blaze2788Pro([t[1] for t in sgids])
    except:
        logger.warning(traceback.format_exc(1))
        logger.warning('Vban Blaze error for ' + ','.join([str(t[1]) for t in sgids]))
    else:
        await kick_vbanPlayer(pljson, sgids,vbans,draw_dict) 

async def upd_vbanPlayer(draw_dict:dict):
    alive_servers = list(draw_dict.keys())
    serverid_gameIds = []
    vbans = {}
    async with async_db_session() as session:
        vban_rows = (await session.execute(select(ServerVBans))).all()
        vban_servers = set(r[0].serverid for r in vban_rows)
        for serverid in vban_servers:
            gameId = await get_gameid_from_serverid(serverid)
            if str(gameId) in alive_servers:
                serverid_gameIds.append((serverid, gameId))
                vbans[serverid] = {'pid':[], 'groupqq': [], 'reason': []}
        for vban_row in vban_rows:
            serverid = vban_row[0].serverid
            if serverid in vbans:
                vbans[serverid]['pid'].append(vban_row[0].pid)
                vbans[serverid]['groupqq'].append(vban_row[0].notify_group)
                vbans[serverid]['reason'].append(vban_row[0].reason)

    if len(serverid_gameIds) == 0:
        return
    sgids = []
    for i in range(len(serverid_gameIds)):
        if len(sgids) < 10:
            sgids.append(serverid_gameIds[i])
        else:
            logger.debug(sgids)
            await start_vban(sgids,vbans,draw_dict)
            #await asyncio.sleep(4) 
            sgids = []
    if 0 < len(sgids) < 10:
        logger.debug(sgids)
        await start_vban(sgids,vbans,draw_dict)


draw_dict = {}

@scheduler.scheduled_job("interval", minutes=15, id=f"job_reset_alarm_session")
async def bf1_reset_alarm_session():
    alarm_sessions = await load_alarm_session_from_db()
    await redis_client.delete(*[f"alarmamount:{groupqq}" for groupqq in alarm_sessions])
    logger.info('Alarm session reset')

@scheduler.scheduled_job("interval", hours=2, id=f"job_2")
async def bf1_init_token():
    await token_helper()

@scheduler.scheduled_job("interval", hours=12, id=f"job_3")
async def bf1_init_session():
    await session_helper()

@scheduler.scheduled_job("interval", minutes=1, id=f"job_0", misfire_grace_time=120)
async def bf1_alarm(timeout: int = 20):
    global draw_dict
    tasks = []

    remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
    draw_dict = await upd_draw(remid,sid,sessionID,timeout)
    logger.info('Update draw dict complete')
    
    start_time = datetime.datetime.now()

    alarm_session_set = await redis_client.smembers('alarmsession')
    for groupqq_b in alarm_session_set:
        groupqq = int(groupqq_b)
        bot = None
        for bot in nonebot.get_bots().values():
            botlist = await bot.get_group_list()
            if next((1 for i in botlist if i['group_id']==groupqq), False):
                break
        if not bot:
            continue
        main_groupqq = await check_session(groupqq)
        servers = await get_server_num(main_groupqq)
        for ind, serverid in servers:
            alarm_amount = await redis_client.hget(f'alarmamount:{groupqq}', ind)
            if (not alarm_amount) or (int(alarm_amount) < 3):
                res = await get_server_status(groupqq, ind, serverid, bot, draw_dict)
                if res == 1:
                    await asyncio.sleep(2)
                #tasks.append(asyncio.create_task(get_server_status(groupqq, ind, serverid, bot, draw_dict)))
    if len(tasks) != 0:
        await asyncio.wait(tasks)
    
    end_time = datetime.datetime.now()
    thr_time = (end_time - start_time).total_seconds()
    logger.info(f"预警用时：{thr_time}秒")

@scheduler.scheduled_job("interval", minutes=2, id=f"job_4",max_instances=2)
async def bf1_upd_vbanPlayer():
    start_time = datetime.datetime.now()
    # await upd_ping()
    # await asyncio.sleep(10)

    await upd_vbanPlayer(draw_dict)
    end_time = datetime.datetime.now()
    thr_time = (end_time - start_time).total_seconds()
    logger.info(f"Vban用时：{thr_time}秒")

    # if thr_time % 60 < 30:
    #     await asyncio.sleep(int(31-thr_time))
    #     await upd_ping()
    
    # elif 30 <= thr_time % 60 < 60:
    #     await upd_ping()