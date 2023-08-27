import nonebot

from nonebot import get_driver
from nonebot import get_bot
from nonebot import on_command

from nonebot.log import logger
from nonebot.params import CommandArg, Depends, _command_arg, Arg, ArgStr, Received
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import GROUP, Message, MessageEvent, MessageSegment, GroupMessageEvent, Bot
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER

import requests,httpx,html
import json
import os
import numpy
import zhconv
import asyncio

from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_htmlrender import md_to_pic, html_to_pic

from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import time
import random
from datetime import datetime, timedelta
import datetime
import traceback

from .config import Config
from .bf1draw2 import draw_server_array2
from .template import apply_template, get_vehicles_data_md, get_weapons_data_md, get_group_list, get_server_md
from .utils import PREFIX, BF1_PLAYERS_DATA, BF1_SERVERS_DATA, CODE_FOLDER, request_API, zhconvert, get_wp_info,search_a,getsid,CURRENT_FOLDER,MapTeamDict
from .bf1rsp import *
from .bf1draw import *
from .secret import *
from .image import upload_img

GAME = 'bf1'
LANG = 'zh-tw'

with open(BF1_SERVERS_DATA/'Caches'/'id.txt','r' ,encoding='UTF-8') as f:
    id_list = f.read().split(',')
    remid = id_list[0]
    sid = id_list[1]

with open(BF1_SERVERS_DATA/'Caches'/'id1.txt','r' ,encoding='UTF-8') as f:
    id_list = f.read().split(',')
    remid1 = id_list[0]
    sid1 = id_list[1]

with open(BF1_SERVERS_DATA/'Caches'/'id2.txt','r' ,encoding='UTF-8') as f:
    id_list = f.read().split(',')
    remid2 = id_list[0]
    sid2 = id_list[1]

with open(BF1_SERVERS_DATA/'Caches'/'id3.txt','r' ,encoding='UTF-8') as f:
    id_list = f.read().split(',')
    remid3 = id_list[0]
    sid3 = id_list[1]

with open(BF1_SERVERS_DATA/'Caches'/'id4.txt','r' ,encoding='UTF-8') as f:
    id_list = f.read().split(',')
    remid4 = id_list[0]
    sid4 = id_list[1]

with open(BF1_SERVERS_DATA/'Caches'/'id5.txt','r' ,encoding='UTF-8') as f:
    id_list = f.read().split(',')
    remid5 = id_list[0]
    sid5 = id_list[1]

with open(BF1_SERVERS_DATA/'Caches'/'id6.txt','r' ,encoding='UTF-8') as f:
    id_list = f.read().split(',')
    remid6 = id_list[0]
    sid6 = id_list[1]

async def init_token():
    global sessionID,access_token,res_access_token,remid,sid
    global sessionID1,access_token1,res_access_token1,remid1,sid1
    global sessionID2,access_token2,res_access_token2,remid2,sid2
    global sessionID3,access_token3,res_access_token3,remid3,sid3
    global sessionID4,access_token4,res_access_token4,remid4,sid4
    global sessionID5,access_token5,res_access_token5,remid5,sid5
    global sessionID6,access_token6,res_access_token6,remid6,sid6

    tasks_token = []
    tasks_session = []

    tasks_token.append(upd_token(remid, sid))
    tasks_token.append(upd_token(remid1, sid1))
    tasks_token.append(upd_token(remid2, sid2))
    tasks_token.append(upd_token(remid3, sid3))
    tasks_token.append(upd_token(remid4, sid4))
    tasks_token.append(upd_token(remid5, sid5))
    tasks_token.append(upd_token(remid6, sid6))

    [res_access_token,access_token],[res_access_token1,access_token1],[res_access_token2,access_token2],[res_access_token3,access_token3],[res_access_token4,access_token4],[res_access_token5,access_token5],[res_access_token6,access_token6] = await asyncio.gather(*tasks_token)

    tasks_session.append(upd_sessionId(res_access_token, remid, sid, 0))
    tasks_session.append(upd_sessionId(res_access_token1, remid1, sid1, 1))
    tasks_session.append(upd_sessionId(res_access_token2, remid2, sid2, 2))
    tasks_session.append(upd_sessionId(res_access_token3, remid3, sid3, 3))
    tasks_session.append(upd_sessionId(res_access_token4, remid4, sid4, 4))
    tasks_session.append(upd_sessionId(res_access_token5, remid5, sid5, 5))
    tasks_session.append(upd_sessionId(res_access_token6, remid6, sid6, 6))

    [remid,sid,sessionID],[remid1,sid1,sessionID1],[remid2,sid2,sessionID2],[remid3,sid3,sessionID3],[remid4,sid4,sessionID4],[remid5,sid5,sessionID5],[remid6,sid6,sessionID6] = await asyncio.gather(*tasks_session)
    print(sessionID)
    print(sessionID1)
    print(sessionID2)
    print(sessionID3)
    print(sessionID4)
    print(sessionID5)
    print(sessionID6)

asyncio.run(init_token())

def reply_message_id(event: GroupMessageEvent) -> int:
    message_id = None
    for seg in event.original_message:
        if seg.type == "reply":
            message_id = int(seg.data["id"])
            break
    return message_id

def check_admin(session:int, user_id:int):
    with open(BF1_SERVERS_DATA/f'{session}_admin.txt','r') as f:
        adminlist = f.read().split(',')
    if f'{user_id}' in adminlist:
        return True
    else:
        return False
    
def check_session(session:int):
    with open(BF1_SERVERS_DATA/f'{session}_session.txt','r') as f:
        result = int(f.read())
    return result

def check_server_id(session,new_server_id):
    try:
        with open(BF1_SERVERS_DATA/f'{session}'/ f'{session}_{new_server_id}.json',"r") as f:
            server_id = f.read()
            if f'{session}_{server_id}.json' in os.listdir(BF1_SERVERS_DATA/f'{session}_jsonBL'):
                return server_id
            else:
                return new_server_id
    except:
        return new_server_id

def search_dicts_by_key_value(dict_list, key, value):
    for d in dict_list:
        if d[key] == value:
            return True
        else :
            return False

    
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

def get_server_num(session:int):      
    files = os.listdir(BF1_SERVERS_DATA/f'{session}_jsonBL')
    return files
    
alarm_mode = [0]*100
alarm_session = [0]*100
job_cnt = 0

#bf1 help
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
BF1_INITMAP = on_command(f'{PREFIX}initmap', block=True, priority=1, permission=GROUP_OWNER | GROUP_ADMIN | SUPERUSER)
BF1_CHOOSELEVEL = on_command(f'{PREFIX}map', block=True, priority=1)
BF1_KICK = on_command(f'{PREFIX}k', aliases={f'{PREFIX}kick', f'{PREFIX}踢出'}, block=True, priority=1)
BF1_KICKALL = on_command(f'{PREFIX}kickall', aliases={f'{PREFIX}炸服', f'{PREFIX}清服'}, block=True, priority=1)
BF1_BAN = on_command(f'{PREFIX}ban', block=True, priority=1)
BF1_BANALL = on_command(f'{PREFIX}bana',aliases={f'{PREFIX}banall', f'{PREFIX}ba'}, block=True, priority=1)
BF1_UNBAN = on_command(f'{PREFIX}unban', block=True, priority=1)
BF1_UNBANALL = on_command(f'{PREFIX}unbana',aliases={f'{PREFIX}unbanall', f'{PREFIX}uba'}, block=True, priority=1)
BF1_MOVE = on_command(f'{PREFIX}move', block=True, priority=1)
BF1_VIP = on_command(f'{PREFIX}vip', block=True, priority=1)
BF1_VIPLIST = on_command(f'{PREFIX}viplist', block=True, priority=1)
BF1_CHECKVIP = on_command(f'{PREFIX}checkvip', block=True, priority=1)
BF1_UNVIP = on_command(f'{PREFIX}unvip', block=True, priority=1)
BF1_PL = on_command(f'{PREFIX}pl', block=True, priority=1)
BF1_ADMINPL = on_command(f'{PREFIX}adminpl', block=True, priority=1)

#bf1status
BF_STATUS = on_command(f'{PREFIX}bf status', block=True, priority=1)
BF1_STATUS = on_command(f'{PREFIX}bf1 status', aliases={f'{PREFIX}战地1', f'{PREFIX}status', f'{PREFIX}bf1'}, block=True, priority=1)
BF1_MODE= on_command(f'{PREFIX}bf1 mode', block=True, priority=1)
BF1_MAP= on_command(f'{PREFIX}bf1 map', block=True, priority=1)
BF1_SA= on_command(f'{PREFIX}查', block=True, priority=1)
BF1_INFO= on_command(f'{PREFIX}info', block=True, priority=1)
BF1_PID= on_command(f'{PREFIX}tyc', aliases={f'{PREFIX}天眼查'}, block=True, priority=1)
BF1_F= on_command(f'{PREFIX}f', block=True, priority=1)
BF1_WP= on_command(f'{PREFIX}武器', aliases={f'{PREFIX}w', f'{PREFIX}wp', f'{PREFIX}weapon'}, block=True, priority=1)
BF1_S= on_command(f'{PREFIX}s', aliases={f'{PREFIX}stat', f'{PREFIX}战绩', f'{PREFIX}查询',f'{PREFIX}生涯'}, block=True, priority=1)
BF1_R= on_command(f'{PREFIX}r', aliases={f'{PREFIX}对局'}, block=True, priority=1)
BF1_RE= on_command(f'{PREFIX}最近', block=True, priority=1)
BF1_BIND_MAG = on_command(f'{PREFIX}bind', aliases={f'{PREFIX}绑定', f'{PREFIX}绑id'}, block=True, priority=1)
BF1_EX= on_command(f'{PREFIX}交换', block=True, priority=1)
BF1_DRAW= on_command(f'{PREFIX}draw', block=True, priority=1)
BF1_ADMINDRAW= on_command(f'{PREFIX}admindraw', block=True, priority=1)

#bf1 server alarm
BF_BIND = on_command(f'{PREFIX}绑服', block=True, priority=1, permission=SUPERUSER)
BF_REBIND = on_command(f'{PREFIX}改绑', block=True, priority=1, permission=SUPERUSER)
BF_ADDBIND = on_command(f'{PREFIX}添加服别名', block=True, priority=1, permission=SUPERUSER)
BF1_SERVER_ALARM = on_command(f'{PREFIX}打开预警', block=True, priority=1)
BF1_SERVER_ALARMOFF = on_command(f'{PREFIX}关闭预警', block=True, priority=1)

#original bf1 chat
BF1_BIND = on_command(f'{PREFIX}bf1 bind', block=True, priority=10)
BF1_LS = on_command(f'{PREFIX}bf1 list', block=True, priority=10)
BF1_SERVER = on_command(f'{PREFIX}bf1 server', block=True, priority=10)
BF1F = on_command(f'{PREFIX}bf1', block=True, priority=1)

@BF1_INIT.handle()
async def bf1_init(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    session = event.group_id
    arg = message.extract_plain_text()

    if arg.startswith(f'{PREFIX}'):
        with open(BF1_SERVERS_DATA/f'{session}_session.txt','w') as f:
            f.write(str(session))
        with open(BF1_SERVERS_DATA/f'{session}_admin.txt','w') as f:
            f.write('120681532')
            await BF1_INIT.send(MessageSegment.reply(event.message_id) + f'初始化完成：{session}')
    else:
        with open(BF1_SERVERS_DATA/f'{session}_session.txt','w') as f:
            f.write(arg)
        with open(BF1_SERVERS_DATA/f'{session}_admin.txt','w') as f:
            f.write('120681532')
            await BF1_INIT.send(MessageSegment.reply(event.message_id) + f'初始化完成：{arg}')

@BF1_HELP.handle()
async def bf_help(event:MessageEvent, state:T_State):
    with open(CODE_FOLDER/'Readme.md',encoding='utf-8') as f:
        md_help = f.read()
    
    md_help = md_help.format(p=PREFIX)

    pic = await md_to_pic(md_help, css_path=CODE_FOLDER/"github-markdown-dark.css",width=900)

    await BF1_HELP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(pic) + '捐赠地址：https://afdian.net/a/Mag1Catz，所有收益将用于服务器运行。输入.code [代码]可以更换查战绩背景。\n使用EAC功能请直接输入.举报 id。\n更多问题请输入.FAQ查询或加群908813634问我。')

@BF1_FAQ.handle()
async def bf_faq(event:MessageEvent, state:T_State):
    file_dir = await draw_faq()
    #file_dir = Path('file:///') / CURRENT_FOLDER/'Caches'/'faq.png'
    await BF1_HELP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
@BF1_BOT.handle()
async def bf1_init(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    
    personaIds = [994371625,1005935009564,1006896769855,1006306480221,1006197884886,1007408722331,1007565122039]
    res = await upd_getPersonasByIds(remid,sid,sessionID,personaIds)
    names = []
    nums = []

    for personaId in personaIds:
        names.append(res['result'][f'{personaId}']['displayName'])
        num1,_ = search_a(personaId,'a')
        nums.append(num1)
    
    msg = ''
    for j in range(len(nums)):
        msg = msg + f'{j+1}. {names[j]}: {nums[j]}/20 \n'
    msg.rstrip()
    await BF1_BOT.send(MessageSegment.reply(event.message_id) + f'请选择未满的eaid添加服管：\n{msg}') 

@BF1_CODE.handle()
async def cmd_receive(event: GroupMessageEvent, state: T_State, pic: Message = CommandArg()):
    message = _command_arg(state) or event.get_message()
    user_id = event.user_id
    code = message.extract_plain_text().split(' ')[0]

    with open(CURRENT_FOLDER/'code.txt','r') as f:
        codearg = f.read().split()
    if code in codearg:
        if f'{user_id}.txt' in os.listdir(BF1_PLAYERS_DATA):
            with open(BF1_PLAYERS_DATA/f'{user_id}.txt','r') as f:
                personaId= int(f.read())
            if f'{code}.txt' in os.listdir(BF1_PLAYERS_DATA/'Code'):
                with open(BF1_PLAYERS_DATA/'Code'/f'{code}.txt','r') as f:
                    pid = f.read()
                if int(pid) != int(personaId):
                    personaIds = []
                    personaIds.append(pid)
                    res = await upd_getPersonasByIds(remid, sid, sessionID, personaIds)
                    userName = res['result'][f'{pid}']['displayName']
                    await BF1_CODE.finish(MessageSegment.reply(event.message_id) + f'这个code已经被使用过，使用者id为：{userName}。')
                else:
                    state["personaId"] = personaId
            else:
                with open(BF1_PLAYERS_DATA/'Code'/f'{code}.txt','w') as f:
                    f.write(str(personaId))
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
            
            image.save(BF1_PLAYERS_DATA/'Caches'/f'{state["personaId"]}.jpg')

            await BF1_CODE.finish(MessageSegment.reply(event.message_id) + '绑定code完成。')

        else:
            await BF1_CODE.finish(MessageSegment.reply(event.message_id) + "你发送的不是图片，请以“图片”形式发送！")

@BF1_REPORT.handle()
async def cmd_receive_report(event: GroupMessageEvent, state: T_State, pic: Message = CommandArg()):
    message = _command_arg(state) or event.get_message()
    user_id = event.user_id
    playerName = message.extract_plain_text().split(' ')[0]
    
    try:
        personaId,name,userId = await getPersonasByName(access_token, playerName)
    except:
        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'无效id')
    bfeac = await bfeac_checkBan(name)
    if bfeac['stat'] == '无':
        state['case_body'] = ''
        state['case_num'] = 0
        state['target_EAID'] = name
        state['txturl'] = []
        await BF1_REPORT.send(f'开始举报: {name}\n可以发送图片/文字/链接\n图片和文字请分开发送\n共计可以接收5次举报消息\n声明: 每次举报都会在后台记录举报者的qq号码，仅作为留档用。恶意举报将永久封停你的bot使用权限，情节严重者将封停群内所有成员的bot使用权。')
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
                
                imageurl = upload_img(image,f"report{random.randint(1, 100000000)}.png")
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
    session = event.group_id
    session = check_session(session)
    arg = message.extract_plain_text().split(' ')

    with open(BF1_SERVERS_DATA/f'{session}_admin.txt','r') as f:
        admin = f.read()
        
    with open(BF1_SERVERS_DATA/f'{session}_admin.txt','a+') as f:
        ok = ""
        error = ""
        msg = ""
        for ad in arg:
            if admin.find(ad) != -1:
                error += f"{ad} "
            else:
                try:
                    ad = int(ad)
                    f.write(f',{ad}')
                except:
                    continue
                ok += f"{ad} "
        if error == "":
            msg = f'本群组已添加管理：{ok.rstrip()}'
        elif ok == "":
            msg = f'请不要重复添加：{error.rstrip()}'
        else:
            msg = f'本群组已添加管理：{ok.rstrip()}\n请不要重复添加：{error.rstrip()}'
        await BF1_ADDADMIN.send(MessageSegment.reply(event.message_id) + msg)

@BF1_DELADMIN.handle()
async def bf1_deladmin(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    session = event.group_id
    session = check_session(session)
    arg = message.extract_plain_text().split(' ')
    with open(BF1_SERVERS_DATA/f'{session}_admin.txt','r') as f:
        admin = f.read().split(',')
    
    adminnew = ''
    for ad in admin:
        if ad in arg or ad == '': 
            continue
        else:
            adminnew = adminnew + ad +','
    with open(BF1_SERVERS_DATA/f'{session}_admin.txt','w') as f:
            f.write(adminnew)
    await BF1_DELADMIN.send(MessageSegment.reply(event.message_id) + f'本群组已删除管理：{message.extract_plain_text()}')

@BF1_ADMINLIST.handle()
async def bf1_adminlist(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    session = event.group_id
    session = check_session(session)
    arg = message.extract_plain_text().split(' ')
    with open(BF1_SERVERS_DATA/f'{session}_admin.txt','r') as f:
        admin = f.read().split(',')
    
    adminlist = ''
    for ad in admin:
        if ad == '' or ad == "120681532": 
            continue
        else:
            adminlist = adminlist + ad +'\n'

    await BF1_DELADMIN.send(MessageSegment.reply(event.message_id) + f'本群组管理列表：\n{adminlist.rstrip()}')

@BF1_INITMAP.handle()
async def bf1_initmap(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    with open(BF1_SERVERS_DATA/f'{session}'/f'{session}_{int(arg[0])}.json','r') as f:
        server = f.read()
    try:
        result = await get_server_data(server)
        detailedresult = await get_detailedServer_data(server)
        gameId = result['servers'][0]['gameId']
        detailedServer = await upd_detailedServer(remid, sid, sessionID, gameId)
    except: 
        await BF1_INITMAP.send(MessageSegment.reply(event.message_id) + '无法获取到服务器数据。')

    with open(BF1_SERVERS_DATA/f'{session}_jsonGT'/f'{session}_{int(arg[0])}.json','w', encoding='utf-8') as f:
        json.dump(detailedresult, f, indent=4, ensure_ascii=False)
    with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{int(arg[0])}.json','w', encoding='utf-8') as f:
        json.dump(detailedServer, f, indent=4, ensure_ascii=False)

        await BF1_INITMAP.send(MessageSegment.reply(event.message_id) + '获取服务器数据完成。')


@BF1_CHOOSELEVEL.handle()
async def bf1_chooseLevel(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id
    
    if(check_admin(session, user_id)):
        server_id = check_server_id(session,arg[0])
        mapName = arg[1]
        try:
            with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
                zh_cn = json.load(f)
                mapName = zh_cn[f'{mapName}']
                mapName_cn = zh_cn[f'{mapName}']
        except:
            if mapName != '重开':
                await BF1_CHOOSELEVEL.finish(MessageSegment.reply(event.message_id) + '请输入正确的地图名称')
        
        with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverBL = json.load(f)
        
        gameId = serverBL['result']['serverInfo']['gameId']
        try:
            remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
        except:
            await BF1_CHOOSELEVEL.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        persistedGameId = serverBL['result']['serverInfo']['guid']

        serverBL = await upd_detailedServer(remid0, sid0, sessionID0, gameId)
        rotation = serverBL['result']['serverInfo']["rotation"]
        
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
                zh_cn[mapmode]
            except:
                mapmode = rotation[0]['modePrettyName']
                for i in rotation:
                    if zhconv.convert(i['mapPrettyName'],'zh-cn') == mapName_cn:
                        break
                    else:
                        levelIndex += 1
            else:
               for i in rotation:
                    if zhconv.convert(i['mapPrettyName'],'zh-cn') == mapName_cn:
                        if i['modePrettyName'] == mapmode:
                            break
                    else:
                        levelIndex += 1            
            if levelIndex == len(rotation):
                await BF1_CHOOSELEVEL.finish(MessageSegment.reply(event.message_id) + '未找到此地图，请更新图池')
        
        res = await upd_chooseLevel(remid0, sid0, sessionID0, persistedGameId, levelIndex)
        if 'error' in res:
            if res['error']['message'] == 'ServerNotRestartableException':
                await BF1_CHOOSELEVEL.send(MessageSegment.reply(event.message_id) + '服务器未开启')
            elif res['error']['message'] == 'LevelIndexNotSetException':
                await BF1_CHOOSELEVEL.send(MessageSegment.reply(event.message_id) + 'sessionID失效')
        else:
            await BF1_CHOOSELEVEL.send(MessageSegment.reply(event.message_id) + f'地图已切换到：{zhconv.convert(mapmode,"zh-cn")}-{mapName_cn}')

    else:
        await BF1_CHOOSELEVEL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_KICK.handle()
async def bf1_kick(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',maxsplit=2)
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        if reply_message_id(event) == None:
            try:
                server_id = check_server_id(session,arg[0])
                name = arg[1]
                reason = zhconvert(arg[2])
            except:
                server_id = check_server_id(session,arg[0])
                name = arg[1]
                reason = zhconvert('违反规则')
            with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
                serverBL = json.load(f)
                gameId = serverBL['result']['serverInfo']['gameId']
            try:
                remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
            except:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + f'bot没有权限，输入.bot查询服管情况。')
            
            try:
                personaId,name,_ = await getPersonasByName(access_token, name)
            except:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + f'无效id')

            res = await upd_kickPlayer(remid0, sid0, sessionID0, gameId, personaId, reason)

            if 'error' in res:
                await BF1_KICK.send(MessageSegment.reply(event.message_id) + f'踢出玩家：{name}失败，理由：无法处置管理员或者bot没有权限.')
            else:
                await BF1_KICK.send(MessageSegment.reply(event.message_id) + f'已踢出玩家：{name}，理由：{reason}')
        else:
            try:
                with open(BF1_SERVERS_DATA/f'{session}_pl'/f'{reply_message_id(event)}.txt','r') as f:
                    pl_json = json.load(f)
                    pl = pl_json['pl']
                    server_id = pl_json['id']
            except:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '请回复正确的消息')
            else:
                slots = []
                personaIds = []
                mode = 0

                with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
                    serverBL = json.load(f)
                    gameId = serverBL['result']['serverInfo']['gameId']
                try:
                    remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
                except:
                    await BF1_KICK.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')

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
                    try:
                        reason = arg[1]
                    except:
                        reason = zhconvert('清服')
                    for i in pl:
                        personaIds.append(i['id'])
                        print(personaIds)
                else:
                    try : 
                        slot = int(arg[0])
                    except:
                        await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '联动踢出规则不合法。\n.k [序号] [理由] 或 .k [rank/kd/kp>数值] 或.k all [理由]')
                    else:
                        try:
                            reason = int(arg[-1])
                        except:
                            reason = zhconvert(arg[-1])
                            for i in range(0,len(arg)-1):
                                slots.append(int(arg[i]))
                        else:
                            reason = zhconvert('违反规则')
                            for i in range(0,len(arg)):
                                slots.append(int(arg[i]))

                        for i in pl:
                            if i['slot'] in slots:
                                personaIds.append(i['id'])
                tasks = []
                for i in personaIds:
                    tasks.append(asyncio.create_task(upd_kickPlayer(remid0, sid0, sessionID0, gameId, i, reason)))

                await asyncio.gather(*tasks)
                await BF1_KICK.send(MessageSegment.reply(event.message_id) + f'已踢出{len(personaIds)-mode}个玩家，理由：{reason}')
    else:
        await BF1_KICK.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_KICKALL.handle()
async def bf1_kickall(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',maxsplit=2)
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = check_server_id(session,arg[0])
        try:
            reason = zhconvert(arg[1])
        except:
            reason = zhconvert('管理员进行了清服')
        with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverBL = json.load(f)
            gameId = serverBL['result']['serverInfo']['gameId']      
        
        try:        
            pl = await upd_blazepl(gameId)
        except:
            await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + '服务器未开启')
        state["playerlist"] = pl
        state["gameId"] = gameId
        state["reason"] = reason
    else:
        await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_KICKALL.got("msg", prompt="发送确认以踢出服务器内所有玩家，发送其他内容以取消操作。")
async def get_kickall(bot: Bot, event: GroupMessageEvent, state: T_State, msg: Message = ArgStr("msg")): 
    if msg == "确认":
        tasks = []
        pl = state["playerlist"] 
        gameId = state["gameId"]
        reason = state["reason"]
        try:
            remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
        except:
            await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        for i in pl['1']:
            tasks.append(asyncio.create_task(upd_kickPlayer(remid0, sid0, sessionID0, gameId, i['id'], reason)))
        for j in pl['2']:
            tasks.append(asyncio.create_task(upd_kickPlayer(remid0, sid0, sessionID0, gameId, j['id'], reason)))
        await asyncio.gather(*tasks)
        await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + f'已踢出{len(pl["1"])+len(pl["2"])}个玩家,理由: {reason}')          
    else:
        await BF1_KICKALL.finish(MessageSegment.reply(event.message_id) + '已取消操作。')

@BF1_BAN.handle()
async def bf1_ban(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',maxsplit=2)
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        if reply_message_id(event) == None:
            server_id = check_server_id(session,arg[0])
            personaName = arg[1]
            try:
                reason = zhconv.convert(arg[2], 'zh-tw')
            except:
                reason = '违反规则'
            with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
                serverBL = json.load(f)
                serverId = serverBL['result']['rspInfo']['server']['serverId']
                gameId = serverBL['result']['serverInfo']['gameId']
                try:
                    remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
                except:
                    await BF1_BAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
                try:
                    personaId,personaName,_ = await getPersonasByName(access_token, personaName)
                except:
                    await BF1_BAN.finish(MessageSegment.reply(event.message_id) + '无效id')
            res = await upd_kickPlayer(remid0, sid0, sessionID0, gameId, personaId, reason)
            res = await upd_banPlayer(remid0, sid0, sessionID0, serverId, personaName)

            if 'error' in res:
                await BF1_BAN.send(MessageSegment.reply(event.message_id) + f'封禁玩家：{personaName}失败，理由：无法处置管理员')
            else:
                await BF1_BAN.send(MessageSegment.reply(event.message_id) + f'已封禁玩家：{personaName}，理由：{reason}')
        else:
            try:
                with open(BF1_SERVERS_DATA/f'{session}_pl'/f'{reply_message_id(event)}.txt','r') as f:
                    pl_json = json.load(f)
                    pl = pl_json['pl']
                    server_id = pl_json['id']
            except:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '请回复正确的消息')
            else:
                with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
                    serverBL = json.load(f)
                    serverId = serverBL['result']['rspInfo']['server']['serverId']
                    gameId = serverBL['result']['serverInfo']['gameId']
                try:
                    reason = zhconv.convert(arg[1], 'zh-tw')
                except:
                    reason = '违反规则'
                personaIds = []
                for i in pl:
                    if int(i['slot']) == int(arg[0]):
                        personaId = i['id']
                        personaIds.append(personaId)
                        break
                try:  
                    remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
                except:
                    await BF1_BAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
                res = await upd_getPersonasByIds(remid, sid, sessionID, personaIds)
                personaName = res['result'][f'{personaId}']['displayName']
                
                res = await upd_kickPlayer(remid0, sid0, sessionID0, gameId, personaId, reason)
                res = await upd_banPlayer(remid0, sid0, sessionID0, serverId, personaName)

                if 'error' in res:
                    await BF1_BAN.send(MessageSegment.reply(event.message_id) + f'封禁玩家：{personaName}失败，理由：无法处置管理员')
                else:
                    await BF1_BAN.send(MessageSegment.reply(event.message_id) + f'已封禁玩家：{personaName}，理由：{reason}')
    else:
        await BF1_BAN.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_BANALL.handle()
async def bf1_banall(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        personaName = arg[0]
        try:
            reason = zhconv.convert(arg[1], 'zh-tw')
        except:
            reason = '违反规则'
        files = get_server_num(session)
        tasks = []
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
        except:
            await BF1_BANALL.finish(MessageSegment.reply(event.message_id) + '无效id')
        for i in files:
            with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{i}','r', encoding='utf-8') as f:
                serverBL = json.load(f)
                serverId = serverBL['result']['rspInfo']['server']['serverId']
                gameId = serverBL['result']['serverInfo']['gameId']
            try:    
                remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
                tasks.append(asyncio.create_task(upd_banPlayer(remid0, sid0, sessionID0, serverId, personaName)))
            except:
                continue
        await asyncio.gather(*tasks)
        await BF1_BANALL.send(MessageSegment.reply(event.message_id) + f'已封禁玩家：{personaName}，理由：{reason}')
    else:
        await BF1_BANALL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_UNBANALL.handle()
async def bf1_unbanall(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        personaName = arg[0]

        files = get_server_num(session)
        tasks = []
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
        except:
            await BF1_UNBANALL.finish(MessageSegment.reply(event.message_id) + '无效id')
        for i in files:
            with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{i}','r', encoding='utf-8') as f:
                serverBL = json.load(f)
                serverId = serverBL['result']['rspInfo']['server']['serverId']
                gameId = serverBL['result']['serverInfo']['gameId']
            try:                 
                remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
                tasks.append(asyncio.create_task(upd_unbanPlayer(remid0, sid0, sessionID0, serverId, personaId)))
            except:
                continue
        await asyncio.gather(*tasks)
        await BF1_UNBANALL.send(MessageSegment.reply(event.message_id) + f'已解封玩家：{personaName}')
    else:
        await BF1_UNBANALL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_UNBAN.handle()
async def bf1_unban(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = check_server_id(session,arg[0])
        personaName = arg[1]
    #    reason = zhconv.convert(arg[2], 'zh-tw')

        with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverBL = json.load(f)
            serverId = serverBL['result']['rspInfo']['server']['serverId']
            gameId = serverBL['result']['serverInfo']['gameId']
            try:
                remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
            except:
                await BF1_UNBAN.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
            try:
                personaId,personaName,_ = await getPersonasByName(access_token, personaName)
            except:
                await BF1_UNBAN.finish(MessageSegment.reply(event.message_id) + '无效id')

        res = await upd_unbanPlayer(remid0, sid0, sessionID0, serverId, personaId)

        if 'error' in res:
            await BF1_UNBAN.send(MessageSegment.reply(event.message_id) + f'解封玩家：{personaName}失败')
        else:
            await BF1_UNBAN.send(MessageSegment.reply(event.message_id) + f'已解封玩家：{personaName}')
    else:
        await BF1_UNBAN.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_MOVE.handle()
async def bf1_move(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        if reply_message_id(event) == None:
            server_id = check_server_id(session,arg[0])
            personaName = arg[1]

            with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
                serverBL = json.load(f)
                gameId = serverBL['result']['serverInfo']['gameId']     
                try:
                    remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
                except:
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
                    else:
                        continue 

                for j in pl['2']:
                    if int(j['id']) == int(personaId):
                        teamId = 2
                        break
                    else:
                        continue 

                if teamId == 1:
                    teamName = pl['team2']
                elif teamId == 2:
                    teamName = pl['team1']
                else : await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + '移动失败,玩家不在服务器中')

                res = await upd_movePlayer(remid0, sid0, sessionID0, gameId, personaId, teamId)

                if 'error' in res:
                    await BF1_MOVE.send(MessageSegment.reply(event.message_id) + '移动失败，可能是sessionID过期')
                else:
                    await BF1_MOVE.send(MessageSegment.reply(event.message_id) + f'已移动玩家{personaName}至队伍{3-teamId}：{teamName}')

            except:
                await BF1_MOVE.send(MessageSegment.reply(event.message_id) + 'API HTTP ERROR，请稍后再试')
        else:
            try:
                with open(BF1_SERVERS_DATA/f'{session}_pl'/f'{reply_message_id(event)}.txt','r') as f:
                    pl_json = json.load(f)
                    pl = pl_json['pl']
                    server_id = pl_json['id']
            except:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '请回复正确的消息')
            else:
                teamIds = []
                personaIds = []
                for i in pl:
                    for j in arg:
                        if int(i['slot']) == int(j):
                            personaIds.append(i['id'])
                            if int(j) < 33:
                                teamIds.append(1)
                            else:
                                teamIds.append(2)

                with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
                    serverBL = json.load(f)
                    gameId = serverBL['result']['serverInfo']['gameId']
                    try:
                        remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
                    except:
                        await BF1_MOVE.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
                for i in range(len(personaIds)):
                    res = await upd_movePlayer(remid0, sid0, sessionID0, gameId, personaIds[i], teamIds[i])

                await BF1_MOVE.send(MessageSegment.reply(event.message_id) + f'已移动{len(arg)}个玩家。')
    else:
        await BF1_MOVE.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_VIP.handle()
async def bf1_vip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        if reply_message_id(event) == None:
            server_id = check_server_id(session,arg[0])
            personaName = arg[1]
            try:
                personaId,personaName,_ = await getPersonasByName(access_token, personaName)
            except:
                await BF1_VIP.finish(MessageSegment.reply(event.message_id) + '无效id')
            day = int(arg[2])

            (BF1_SERVERS_DATA/f'{session}_vip').mkdir(exist_ok=True)
            vipfile =  os.listdir(BF1_SERVERS_DATA/f'{session}_vip')
            j = 0
            for i in vipfile:
                if i.startswith(f'{session}_{server_id}_{personaId}'):
                    j = 1
                    break
            if j == 1:
                current_date = i.split('_')
                try:
                    current_date = datetime.datetime.strptime(current_date[len(current_date)-1], "%Y-%m-%d")
                    nextday = current_date + timedelta(days=day)
                    current_date = str(current_date).split(' ')[0]
                    nextday = str(nextday).split(' ')[0]
                    print(f'{session}_{server_id}_{personaId}_{current_date}')
                    os.remove(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{current_date}')
                    with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}','w', encoding='utf-8') as f:
                        f.write(personaName)
                    await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})')
                except:
                    current_date = datetime.datetime.strptime(current_date[len(current_date)-2], "%Y-%m-%d")
                    nextday = current_date + timedelta(days=day)
                    current_date = str(current_date).split(' ')[0]
                    nextday = str(nextday).split(' ')[0]
                    print(f'{session}_{server_id}_{personaId}_{current_date}')
                    os.remove(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{current_date}_unabled')
                    with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}_unabled','w', encoding='utf-8') as f:
                        f.write(personaName)
                    await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})(未生效)')

            else:
                current_date = datetime.date.today()

                nextday = current_date + timedelta(days=day)

                with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
                    serverBL = json.load(f)
                    serverId = serverBL['result']['rspInfo']['server']['serverId']
                    gameId = serverBL['result']['serverInfo']['gameId']
                    try:
                        remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
                    except:
                        await BF1_VIP.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
                if serverBL['result']['serverInfo']['mapMode'] == 'BreakthroughLarge':
                    with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}_unabled','w', encoding='utf-8') as f:
                        f.write(personaName)
                    await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})(未生效)')
                else:        
                    res = await upd_vipPlayer(remid0, sid0, sessionID0, serverId, personaName)

                    if 'error' in res:
                        await BF1_VIP.send(MessageSegment.reply(event.message_id) + '添加失败：可能玩家已经是vip了，且在本地没有记录')
                    else:
                        with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}','w', encoding='utf-8') as f:
                            f.write(personaName)
                        await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})')
        else:
            try:
                with open(BF1_SERVERS_DATA/f'{session}_pl'/f'{reply_message_id(event)}.txt','r') as f:
                    pl_json = json.load(f)
                    pl = pl_json['pl']
                    server_id = pl_json['id']
            except:
                await BF1_KICK.finish(MessageSegment.reply(event.message_id) + '请回复正确的消息')
            else:
                personaIds = []
                for i in pl:
                    if int(i['slot']) == int(arg[0]):
                        personaId = i['id']
                        personaIds.append(personaId)
                        break
                res = await upd_getPersonasByIds(remid, sid, sessionID, personaIds)
                personaName = res['result'][f'{personaId}']['displayName']

                day = int(arg[1])

                (BF1_SERVERS_DATA/f'{session}_vip').mkdir(exist_ok=True)
                vipfile =  os.listdir(BF1_SERVERS_DATA/f'{session}_vip')
                j = 0
                for i in vipfile:
                    if i.startswith(f'{session}_{server_id}_{personaId}'):
                        j = 1
                        break
                if j == 1:
                    current_date = i.split('_')
                    try:
                        current_date = datetime.datetime.strptime(current_date[len(current_date)-1], "%Y-%m-%d")
                        nextday = current_date + timedelta(days=day)
                        current_date = str(current_date).split(' ')[0]
                        nextday = str(nextday).split(' ')[0]
                        print(f'{session}_{server_id}_{personaId}_{current_date}')
                        os.remove(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{current_date}')
                        with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}','w', encoding='utf-8') as f:
                            f.write(personaName)
                        await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})')
                    except:
                        current_date = datetime.datetime.strptime(current_date[len(current_date)-2], "%Y-%m-%d")
                        nextday = current_date + timedelta(days=day)
                        current_date = str(current_date).split(' ')[0]
                        nextday = str(nextday).split(' ')[0]
                        print(f'{session}_{server_id}_{personaId}_{current_date}')
                        os.remove(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{current_date}_unabled')
                        with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}_unabled','w', encoding='utf-8') as f:
                            f.write(personaName)
                        await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})(未生效)')

                else:
                    current_date = datetime.date.today()

                    nextday = current_date + timedelta(days=day)

                    with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
                        serverBL = json.load(f)
                        serverId = serverBL['result']['rspInfo']['server']['serverId']
                        gameId = serverBL['result']['serverInfo']['gameId']
                        try:
                            remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
                        except:
                            await BF1_VIP.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
                    if serverBL['result']['serverInfo']['mapMode'] == 'BreakthroughLarge':
                        with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}_unabled','w', encoding='utf-8') as f:
                            f.write(personaName)
                        await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})(未生效)')
                    else:        
                        res = await upd_vipPlayer(remid0, sid0, sessionID0, serverId, personaName)

                        if 'error' in res:
                            await BF1_VIP.send(MessageSegment.reply(event.message_id) + '添加失败：可能玩家已经是vip了，且在本地没有记录')
                        else:
                            with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}','w', encoding='utf-8') as f:
                                f.write(personaName)
                            await BF1_VIP.send(MessageSegment.reply(event.message_id) + f'已为玩家{personaName}添加{day}天的vip({nextday})')
    else:
        await BF1_VIP.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_VIPLIST.handle()
async def bf1_vip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = check_server_id(session,arg[0])

        (BF1_SERVERS_DATA/f'{session}_vip').mkdir(exist_ok=True)
        vipfile =  os.listdir(BF1_SERVERS_DATA/f'{session}_vip')
        mess = '只展示通过本bot添加的vip:\n'
        count = 0
        for i in vipfile:
            with open(BF1_SERVERS_DATA/f'{session}_vip'/i,'r', encoding='utf-8') as f:
                personaName = f.read()
                nextday = i.split('_')
                if nextday[1] != server_id:
                    continue
                else:
                    if nextday[len(nextday)-1] == 'unabled':
                        mess += f'{count+1}. {personaName}(未生效)\n'
                    else: 
                        nextday = datetime.datetime.strptime(nextday[len(nextday)-1], "%Y-%m-%d")
                        if nextday+timedelta(days=1) < datetime.datetime.now():
                            mess += f'{count+1}. {personaName}(已过期)\n'
                        else:
                            mess += f'{count+1}. {personaName}({nextday.strftime("%Y-%m-%d")})\n'
                    count +=1

        mess = mess.rstrip("\n")
        await BF1_VIPLIST.send(MessageSegment.reply(event.message_id) + mess)
    else:
        await BF1_VIPLIST.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_CHECKVIP.handle()
async def bf1_vip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = check_server_id(session,arg[0])

        (BF1_SERVERS_DATA/f'{session}_vip').mkdir(exist_ok=True)
        vipfile =  os.listdir(BF1_SERVERS_DATA/f'{session}_vip')
        add = 0
        remove = 0
        f = open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8')
        serverBL = json.load(f)
        serverId = serverBL['result']['rspInfo']['server']['serverId']
        gameId = serverBL['result']['serverInfo']['gameId']
        try:
            remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
        except:
            await BF1_CHECKVIP.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        tasks = []
        for i in vipfile:
            with open(BF1_SERVERS_DATA/f'{session}_vip'/i,'r', encoding='utf-8') as f:
                personaName = f.read()
                nextday = i.split('_')
                personaId = int(nextday[2])
                if nextday[1] != server_id:
                    f.close()
                    continue
                else:
                    if nextday[len(nextday)-1] == 'unabled':
                        tasks.append(asyncio.create_task(upd_vipPlayer(remid0, sid0, sessionID0, serverId, personaName)))
                        nextday = nextday[len(nextday)-2]
                        f.close()
                        os.remove(BF1_SERVERS_DATA/f'{session}_vip'/i)
                        with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}','w', encoding='utf-8') as f:
                            f.write(personaName)
                        add +=1
                    else:
                        nextday = datetime.datetime.strptime(nextday[len(nextday)-1], "%Y-%m-%d")
                        if nextday+timedelta(days=1) < datetime.datetime.now():
                            tasks.append(asyncio.create_task(upd_unvipPlayer(remid0, sid0, sessionID0, serverId, personaId)))
                            f.close()
                            os.remove(BF1_SERVERS_DATA/f'{session}_vip'/i)
                            remove += 1
        await asyncio.gather(*tasks)
        await BF1_CHECKVIP.send(MessageSegment.reply(event.message_id) + f'已添加{add}个vip，删除{remove}个vip')
    else:
        await BF1_CHECKVIP.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')     


@BF1_UNVIP.handle()
async def bf1_unvip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = check_server_id(session,arg[0])
        personaName = arg[1]
        try:
            personaId,personaName,_ = await getPersonasByName(access_token, personaName)
        except:
            await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + '无效id')

        (BF1_SERVERS_DATA/f'{session}_vip').mkdir(exist_ok=True)
        vipfile = os.listdir(BF1_SERVERS_DATA/f'{session}_vip')
        j = 0
        for i in vipfile:
            if i.startswith(f'{session}_{server_id}_{personaId}'):
                j = 1
                break
        if j == 1:
            current_date = i.split('_')
            current_date = current_date[len(current_date)-1]
            os.remove(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{current_date}')

        with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverBL = json.load(f)
            serverId = serverBL['result']['rspInfo']['server']['serverId']
            gameId = serverBL['result']['serverInfo']['gameId']
            try:
                remid0,sid0,sessionID0 = getsid(gameId,remid,remid1,sid,sid1,sessionID,sessionID1,remid2,sid2,sessionID2,remid3,sid3,sessionID3,remid4,sid4,sessionID4,remid5,sid5,sessionID5,remid6,sid6,sessionID6)
            except:
                await BF1_UNVIP.finish(MessageSegment.reply(event.message_id) + 'bot没有权限，输入.bot查询服管情况。')
        res = await upd_unvipPlayer(remid0, sid0, sessionID0, serverId, personaId)

        if 'error' in res:
            await BF1_UNVIP.send(MessageSegment.reply(event.message_id) + '移除失败，可能是sessionID失效')
        else:
            await BF1_UNVIP.send(MessageSegment.reply(event.message_id) + f'已移除玩家{personaName}的vip')
    else:
        await BF1_UNVIP.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')

@BF1_PL.handle()
async def bf_pl(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = check_server_id(session,arg[0])
        with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverBL = json.load(f)
            gameId = serverBL['result']['serverInfo']['gameId']

        try:
            file_dir = await asyncio.wait_for(draw_pl1(session,server_id, gameId, remid, sid, sessionID), timeout=20)
            reply = await BF1_PL.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
            os.rename(BF1_SERVERS_DATA/f'{session}_pl'/f'{server_id}_pl.txt', BF1_SERVERS_DATA/f'{session}_pl'/f'{reply["message_id"]}.txt')
        except asyncio.TimeoutError:
            await BF1_PL.send(MessageSegment.reply(event.message_id) + '连接超时')
        except:
            await BF1_PL.send(MessageSegment.reply(event.message_id) + '服务器未开启。')
    else:
        await BF1_PL.send(MessageSegment.reply(event.message_id) + '你不是本群组的管理员')  

@BF1_ADMINPL.handle()
async def bf_pl(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    server = html.unescape(message.extract_plain_text())
    session = event.group_id

    if session == 609250652:
        try:
            result = await upd_servers(remid2, sid2, sessionID2, server)
            gameId = result['result']['gameservers'][0]['gameId']
        except: 
            await BF1_ADMINPL.finish('无法获取到服务器数据。')

        try:
            file_dir = await asyncio.wait_for(draw_pl1(session,99, gameId, remid, sid, sessionID), timeout=20)
            reply = await BF1_ADMINPL.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
            os.rename(BF1_SERVERS_DATA/f'{session}_pl'/f'99_pl.txt', BF1_SERVERS_DATA/f'{session}_pl'/f'{reply["message_id"]}.txt')
        except asyncio.TimeoutError:
            await BF1_ADMINPL.send(MessageSegment.reply(event.message_id) + '连接超时')
        except:
            await BF1_ADMINPL.send(MessageSegment.reply(event.message_id) + '服务器未开启。')
 

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

    print(arg)
    if len(arg) == 1:
        searchmode = arg[0]
        mode = 2
    else:
        searchmode = arg[0]
        playerName = arg[1]
        mode = 1

    print(f'mode={mode}')

    session = check_session(event.group_id)
    user_id = event.user_id
    usercard = event.sender.card

    msg = []

    if mode == 1:
        try:
            personaId,playerName,_ = await getPersonasByName(access_token, playerName)
        except:
            await BF1_SA.send(MessageSegment.reply(event.message_id) + '无效id')
        else:
            num,name = search_a(personaId,searchmode)
            if num == 0:
                if searchmode == 'o':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{playerName}共拥有{num}个服务器')
                elif searchmode == 'a':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{playerName}共拥有{num}个服务器的管理')
                elif searchmode == 'v':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{playerName}共拥有{num}个服务器的vip')
                elif searchmode == 'b':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{playerName}共拥有{num}个服务器的ban位')
                else:
                    return 0
                return 0
            else:
                if searchmode == 'o':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{playerName}共拥有{num}个服务器：')
                elif searchmode == 'a':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{playerName}共拥有{num}个服务器的管理：')
                elif searchmode == 'v':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{playerName}共拥有{num}个服务器的vip：')
                elif searchmode == 'b':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{playerName}共拥有{num}个服务器的ban位：')
                else:
                    return 0                            
                file_dir = await draw_a(num,name,personaId)
                await BF1_SA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))

    if mode == 2:
        if f'{user_id}.txt' in os.listdir(BF1_PLAYERS_DATA):
            with open(BF1_PLAYERS_DATA/f'{user_id}.txt','r') as f:
                personaId= int(f.read())
                personaIds = []
                personaIds.append(personaId)
                res = await upd_getPersonasByIds(remid, sid, sessionID, personaIds)
                userName = res['result'][f'{personaId}']['displayName']
                (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                    f.write(userName)                 
            num,name = search_a(personaId,searchmode)
            if num == 0:
                if searchmode == 'o':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器')
                elif searchmode == 'a':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的管理')
                elif searchmode == 'v':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的vip')
                elif searchmode == 'b':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的ban位')
                else:
                    return 0
                return 0
            else:
                if searchmode == 'o':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器：')
                elif searchmode == 'a':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的管理：')
                elif searchmode == 'v':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的vip：')
                elif searchmode == 'b':
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的ban位：')
                else:
                    return 0                            
                file_dir = await draw_a(num,name,personaId)
                await BF1_SA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))

        else:
            await BF1_SA.send(MessageSegment.reply(event.message_id) + f'您还未绑定，将尝试绑定: {usercard}')
            try:
                playerName = usercard
                personaId,userName,_ = await getPersonasByName(access_token, playerName)
            except:
                await BF1_SA.send(MessageSegment.reply(event.message_id) + '绑定失败')
            else:
                personaId = res['id']
                num,name = search_a(personaId,searchmode) 
                if num == 0:
                    if searchmode == 'o':
                        await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器')
                    elif searchmode == 'a':
                        await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的管理')
                    elif searchmode == 'v':
                        await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的vip')
                    elif searchmode == 'b':
                        await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的ban位')
                    else:
                        return 0
                    return 0
                else:
                    if searchmode == 'o':
                        await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器：')
                    elif searchmode == 'a':
                        await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的管理：')
                    elif searchmode == 'v':
                        await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的vip：')
                    elif searchmode == 'b':
                        await BF1_SA.send(MessageSegment.reply(event.message_id) + f'玩家{userName}共拥有{num}个服务器的ban位：')
                    else:
                        return 0                            
                    file_dir = await draw_a(num,name,personaId)
                    await BF1_SA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                    with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
                        f.write(str(personaId))
                    (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                    with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                        f.write(userName)

@BF1_INFO.handle()
async def bf1_info(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    print(message.extract_plain_text())

    serverName = message.extract_plain_text()
    serverName = html.unescape(serverName)

    try:
        res = await upd_servers(remid1, sid1, sessionID1, serverName)
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
        res_0 = await upd_detailedServer(remid1, sid1, sessionID1, gameId)
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
        res1 = await upd_getPersonasByIds(remid1, sid1, sessionID1, personaIds)
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

@BF1_PID.handle()
async def bf1_pid(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    user_id = event.user_id
    session = check_session(event.group_id)
    usercard = event.sender.card

    if reply_message_id(event) == None:
        mode = 0
        if message.extract_plain_text().startswith(f'{PREFIX}'):
            mode = 2
        else:
            playerName = message.extract_plain_text()
            mode = 1

        if mode == 1:
            try:
                id,name,pidid = await getPersonasByName(access_token, playerName)
            except:
                await BF1_PID.send(MessageSegment.reply(event.message_id) + '无效id')
            else:
                msg = await tyc(remid2,sid2,sessionID2,id,name,pidid)
                await BF1_PID.send(MessageSegment.reply(event.message_id) + msg)
        
        if mode == 2:
            if f'{user_id}.txt' in os.listdir(BF1_PLAYERS_DATA):
                with open(BF1_PLAYERS_DATA/f'{user_id}.txt','r') as f:
                    personaId= int(f.read())
                    personaIds = []
                    personaIds.append(personaId)
                    res1 = await upd_getPersonasByIds(remid1, sid1, sessionID1, personaIds)
                    userName = res1['result'][f'{personaId}']['displayName']
                    pidid = res1['result'][f'{personaId}']['platformId']
                    (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                    with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                        f.write(userName)                 
                msg = await tyc(remid2,sid2,sessionID2,personaId,userName,pidid)
                await BF1_PID.send(MessageSegment.reply(event.message_id) + msg)
            else:
                await BF1_PID.send(MessageSegment.reply(event.message_id) + f'您还未绑定，将尝试绑定: {usercard}')
                playerName = usercard
                try:
                    id,name,pidid = await getPersonasByName(access_token, playerName)
                except:
                    await BF1_PID.send(MessageSegment.reply(event.message_id) + '绑定失败')
                else:
                    msg = await tyc(remid2,sid2,sessionID2,id,name,pidid)
                    await BF1_PID.send(MessageSegment.reply(event.message_id) + msg)
                    with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
                        f.write(str(id))
                    (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                    with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{id}.txt','w') as f:
                        f.write(playerName)
    else:
        try:
            with open(BF1_SERVERS_DATA/f'{session}_pl'/f'{reply_message_id(event)}.txt','r') as f:
                pl_json = json.load(f)
                pl = pl_json['pl']
        except:
            await BF1_PID.finish(MessageSegment.reply(event.message_id) + '请回复正确的消息')
        else:
            personaIds = []
            for i in pl:
                if int(i['slot']) == int(arg[0]):
                    personaId = i['id']
                    personaIds.append(personaId)
                    break
    
            res1 = await upd_getPersonasByIds(remid1, sid1, sessionID1, personaIds)
            userName = res1['result'][f'{personaId}']['displayName']
            pidid = res1['result'][f'{personaId}']['platformId']
            
            msg = await tyc(remid2,sid2,sessionID2,personaId,userName,pidid)
            await BF1_PID.send(MessageSegment.reply(event.message_id) + msg)

@BF1_F.handle()
async def bf1_fuwuqi(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    print(message.extract_plain_text())
    mode = 0
    if message.extract_plain_text().startswith(f'{PREFIX}'):
        mode = 2
    else:
        serverName = message.extract_plain_text()
        serverName = html.unescape(serverName)
        mode = 1

    print(f'mode={mode}')

    if mode == 1:
        res = await upd_servers(remid1, sid1, sessionID1, serverName)
        try:
            if len(res['result']['gameservers']) == 0:
                1/0
            else:
                try:
                    file_dir = await asyncio.wait_for(draw_server(remid1, sid1, sessionID1, serverName,res), timeout=15)
                    await BF1_F.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                except:
                    await BF1_F.send(MessageSegment.reply(event.message_id) + '连接超时')
        except: await BF1_F.send(MessageSegment.reply(event.message_id) + '未查询到数据')

    if mode == 2:
        session = event.group_id
        session = check_session(session)
        server_id = get_server_num(session)
        #try:
        file_dir = await asyncio.wait_for(draw_f(server_id,session,remid1, sid1, sessionID1), timeout=15)
        await BF1_F.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        #except:
        #    await BF1F.send(MessageSegment.reply(event.message_id) + '连接超时')

@BF1_S.handle()
async def bf1_statimage(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = check_session(event.group_id)
    usercard = event.sender.card
    user_id = event.user_id

    if reply_message_id(event) == None:
        mode = 0
        if message.extract_plain_text().startswith(f'{PREFIX}'):
            mode = 2
        else:
            playerName = message.extract_plain_text()
            mode = 1
    
        print(f'mode={mode}')

        if mode == 1:
            try:
                personaId,playerName,_ = await getPersonasByName(access_token, playerName)
            except:
                await BF1_S.send(MessageSegment.reply(event.message_id) + '无效id')
            else:
                try:
                    file_dir = await asyncio.wait_for(draw_stat(remid1, sid1, sessionID1, personaId, playerName), timeout=15)
                    await BF1_S.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                except asyncio.TimeoutError:
                    await BF1_S.send(MessageSegment.reply(event.message_id) + '连接超时')

        if mode == 2:
            if f'{user_id}.txt' in os.listdir(BF1_PLAYERS_DATA):
                with open(BF1_PLAYERS_DATA/f'{user_id}.txt','r') as f:
                    personaId= int(f.read())
                    personaIds = []
                    personaIds.append(personaId)
                    res1 = await upd_getPersonasByIds(remid1, sid1, sessionID1, personaIds)
                    userName = res1['result'][f'{personaId}']['displayName']
                (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                    f.write(userName)                 
                try:
                    file_dir = await asyncio.wait_for(draw_stat(remid1, sid1, sessionID1, personaId, userName), timeout=15)
                    await BF1_S.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                except asyncio.TimeoutError:
                    await BF1_S.send(MessageSegment.reply(event.message_id) + '连接超时')
            else:
                await BF1_S.send(MessageSegment.reply(event.message_id) + f'您还未绑定，将尝试绑定: {usercard}')
                try:
                    playerName = usercard
                    personaId,userName,_ = await getPersonasByName(access_token, playerName)
                except:
                    await BF1_S.send(MessageSegment.reply(event.message_id) + '绑定失败')
                else:
                    try:
                        file_dir = await asyncio.wait_for(draw_stat(remid1, sid1, sessionID1, personaId, userName), timeout=15)
                        await BF1_S.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                    except asyncio.TimeoutError:
                        await BF1_S.send(MessageSegment.reply(event.message_id) + '连接超时')
                    with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
                        f.write(str(personaId))
                    (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                    with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                        f.write(userName)
    else:
        try:
            with open(BF1_SERVERS_DATA/f'{session}_pl'/f'{reply_message_id(event)}.txt','r') as f:
                pl_json = json.load(f)
                pl = pl_json['pl']
        except:
            await BF1_S.finish(MessageSegment.reply(event.message_id) + '请回复正确的消息')
        else:
            personaIds = []
            for i in pl:
                if int(i['slot']) == int(arg[0]):
                    personaId = i['id']
                    personaIds.append(personaId)
                    break
    
            res1 = await upd_getPersonasByIds(remid1, sid1, sessionID1, personaIds)
            userName = res1['result'][f'{personaId}']['displayName']
            try:
                file_dir = await asyncio.wait_for(draw_stat(remid1, sid1, sessionID1, personaId, userName), timeout=15)
                await BF1_S.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
            except asyncio.TimeoutError:
                await BF1_S.send(MessageSegment.reply(event.message_id) + '连接超时')

@BF1_WP.handle()
async def bf1_wp(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message() 
    message = message.extract_plain_text()
    session = check_session(event.group_id)
    usercard = event.sender.card
    user_id = event.user_id

    if message.endswith("行") or message.endswith("列"):
        row = int(re.findall(r'(\d+)行', message)[0])
        col = int(re.findall(r'(\d+)列', message)[0])
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

    if reply_message_id(event) == None:
        mode = 0
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
    
        print(f'mode={mode},wpmode={wpmode}')

        if mode == 1:
            
            try:
                personaId,playerName,_ = await getPersonasByName(access_token, playerName)
            except:
                await BF1_WP.send(MessageSegment.reply(event.message_id) + '无效id')
            else:
                try:
                    file_dir = await asyncio.wait_for(draw_wp(remid2, sid2, sessionID2, personaId, playerName, wpmode, col, row), timeout=15)
                    await BF1_WP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                except asyncio.TimeoutError:
                    await BF1_WP.send(MessageSegment.reply(event.message_id) + '连接超时')

        if mode == 2:
            if f'{user_id}.txt' in os.listdir(BF1_PLAYERS_DATA):
                with open(BF1_PLAYERS_DATA/f'{user_id}.txt','r') as f:
                    personaId = int(f.read())
                    personaIds = []
                    personaIds.append(personaId)
                    res1 = await upd_getPersonasByIds(remid2, sid2, sessionID2, personaIds)
                    userName = res1['result'][f'{personaId}']['displayName']
                (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                    f.write(userName)                
                try:
                    file_dir = await asyncio.wait_for(draw_wp(remid2, sid2, sessionID2, personaId, userName, wpmode, col, row), timeout=15)
                    await BF1_WP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                except asyncio.TimeoutError:
                    await BF1_WP.send(MessageSegment.reply(event.message_id) + '连接超时')
            else:
                await BF1_WP.send(MessageSegment.reply(event.message_id) + f'您还未绑定，将尝试绑定: {usercard}')
                try:
                    playerName = usercard
                    personaId,userName,_ = await getPersonasByName(access_token, playerName)
                except:
                    await BF1_WP.send(MessageSegment.reply(event.message_id) + '绑定失败')
                else:
                    try:
                        file_dir = await asyncio.wait_for(draw_wp(remid2, sid2, sessionID2, personaId, userName, wpmode, col, row), timeout=15)
                        await BF1_WP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                    except asyncio.TimeoutError:
                        await BF1_WP.send(MessageSegment.reply(event.message_id) + '连接超时')
                    with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
                        f.write(str(personaId))
                    (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                    with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                        f.write(userName)
    else:
        try:
            with open(BF1_SERVERS_DATA/f'{session}_pl'/f'{reply_message_id(event)}.txt','r') as f:
                pl_json = json.load(f)
                pl = pl_json['pl']
        except:
            await BF1_WP.finish(MessageSegment.reply(event.message_id) + '请回复正确的消息')
        else:
            if len(message.split(' ')) == 1:
                [playerName,wpmode,mode] = get_wp_info(message,user_id)
            else:
                playerName = message.split(' ')[1]
                mode = 1
                wpmode = get_wp_info(message.split(' ')[0],user_id)[1]
            
            personaIds = []
            for i in pl:
                if int(i['slot']) == int(arg[-1]):
                    personaId = i['id']
                    personaIds.append(personaId)
                    break
    
            res1 = await upd_getPersonasByIds(remid2, sid2, sessionID2, personaIds)
            userName = res1['result'][f'{personaId}']['displayName']
            try:
                file_dir = await asyncio.wait_for(draw_wp(remid2, sid2, sessionID2, personaId, userName, wpmode, col, row), timeout=15)
                await BF1_WP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
            except asyncio.TimeoutError:
                await BF1_WP.send(MessageSegment.reply(event.message_id) + '连接超时')

@BF1_R.handle()
async def bf1_recent(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    session = check_session(event.group_id)
    usercard = event.sender.card
    user_id = event.user_id

    mode = 0
    if message.extract_plain_text().startswith(f'{PREFIX}'):
        mode = 2
    else:
        playerName = message.extract_plain_text()
        mode = 1
    
    print(f'mode={mode}')

    if mode == 1:
        try:
            personaId,playerName,_ = await getPersonasByName(access_token, playerName)  
        except:
            await BF1_R.send(MessageSegment.reply(event.message_id) + '无效id')
        else:
            try:
                file_dir = await asyncio.wait_for(draw_r(remid2, sid2, sessionID2, personaId, playerName), timeout=35)
                if str(file_dir) != '0':
                    await BF1_R.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                else:
                    await BF1_R.send(MessageSegment.reply(event.message_id) + "暂无有效对局信息，请检查BTR服务器是否正常。")
            except: 
                await BF1_R.send(MessageSegment.reply(event.message_id) + '连接超时')

    if mode == 2:
        if f'{user_id}.txt' in os.listdir(BF1_PLAYERS_DATA):
            with open(BF1_PLAYERS_DATA/f'{user_id}.txt','r') as f:
                personaId = int(f.read())
                personaIds = []
                personaIds.append(personaId)
                res1 = await upd_getPersonasByIds(remid2, sid2, sessionID2, personaIds)
                userName = res1['result'][f'{personaId}']['displayName']
            (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
            with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                f.write(userName)  
            try:
                file_dir = await asyncio.wait_for(draw_r(remid2, sid2, sessionID2, personaId, userName), timeout=35)
                if str(file_dir) != '0':
                    await BF1_R.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                else:
                    await BF1_R.send(MessageSegment.reply(event.message_id) + "暂无有效对局信息，请检查BTR服务器是否正常。")
            except: 
                await BF1_R.send(MessageSegment.reply(event.message_id) + '连接超时')

        else:
            await BF1_R.send(MessageSegment.reply(event.message_id) + f'您还未绑定，将尝试绑定: {usercard}')
            try:
                playerName = usercard
                personaId,userName,_ = await getPersonasByName(access_token, playerName)
            except:
                await BF1_R.send(MessageSegment.reply(event.message_id) + '绑定失败')
            else:
                try:
                    file_dir = await asyncio.wait_for(draw_r(remid2, sid2, sessionID2, personaId, userName), timeout=35)
                    if str(file_dir) != '0':
                        await BF1_R.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                    else:
                        await BF1_R.send(MessageSegment.reply(event.message_id) + "暂无有效对局信息，请检查BTR服务器是否正常。")
                except: 
                    await BF1_R.send(MessageSegment.reply(event.message_id) + '连接超时')
                with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
                    f.write(str(personaId))
                (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                    f.write(playerName)

@BF1_RE.handle()
async def bf1_recent1(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    session = check_session(event.group_id)
    usercard = event.sender.card
    user_id = event.user_id

    mode = 0
    if message.extract_plain_text().startswith(f'{PREFIX}'):
        mode = 2
    else:
        playerName = message.extract_plain_text()
        mode = 1
    
    print(f'mode={mode}')

    if mode == 1:
        try:
            personaId,playerName,_ = await getPersonasByName(access_token, playerName)  
        except:
            await BF1_RE.send(MessageSegment.reply(event.message_id) + '无效id')
        else:
            try:
                file_dir = await asyncio.wait_for(draw_re(remid2, sid2, sessionID2, personaId, playerName), timeout=35)
                if str(file_dir) != '0':
                    await BF1_RE.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                else:
                    await BF1_RE.send(MessageSegment.reply(event.message_id) + "暂无有效对局信息，请检查BTR服务器是否正常。")
            except: 
                await BF1_RE.send(MessageSegment.reply(event.message_id) + '连接超时')

    if mode == 2:
        if f'{user_id}.txt' in os.listdir(BF1_PLAYERS_DATA):
            with open(BF1_PLAYERS_DATA/f'{user_id}.txt','r') as f:
                personaId = int(f.read())
                personaIds = []
                personaIds.append(personaId)
                res1 = await upd_getPersonasByIds(remid2, sid2, sessionID2, personaIds)
                userName = res1['result'][f'{personaId}']['displayName']
            (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
            with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                f.write(userName)  
            try:
                file_dir = await asyncio.wait_for(draw_re(remid2, sid2, sessionID2, personaId, userName), timeout=35)
                if str(file_dir) != '0':
                    await BF1_RE.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                else:
                    await BF1_RE.send(MessageSegment.reply(event.message_id) + "暂无有效对局信息，请检查BTR服务器是否正常。")
            except: 
                await BF1_RE.send(MessageSegment.reply(event.message_id) + '连接超时')

        else:
            await BF1_RE.send(MessageSegment.reply(event.message_id) + f'您还未绑定，将尝试绑定: {usercard}')
            try:
                playerName = usercard
                personaId,userName,_ = await getPersonasByName(access_token, playerName)
            except:
                await BF1_RE.send(MessageSegment.reply(event.message_id) + '绑定失败')
            else:
                try:
                    file_dir = await asyncio.wait_for(draw_re(remid2, sid2, sessionID2, personaId, userName), timeout=35)
                    if str(file_dir) != '0':
                        await BF1_RE.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
                    else:
                        await BF1_RE.send(MessageSegment.reply(event.message_id) + "暂无有效对局信息，请检查BTR服务器是否正常。")
                except: 
                    await BF1_RE.send(MessageSegment.reply(event.message_id) + '连接超时')
                with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
                    f.write(str(personaId))
                (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
                with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
                    f.write(playerName)

@BF1_BIND_MAG.handle()
async def bf1_bindplayer(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    user_id = event.user_id
    session = check_session(event.group_id)
    usercard = event.sender.card

    if message.extract_plain_text().startswith(f'{PREFIX}'):
        playerName = usercard
    else:
        playerName = message.extract_plain_text()

    try:
        personaId,userName,_ = await getPersonasByName(access_token, playerName)
    except:
        await BF1_BIND_MAG.send(MessageSegment.reply(event.message_id) + '绑定失败，无效id或http error')
    else:
        with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
            f.write(str(personaId))
        await BF1_BIND_MAG.send(MessageSegment.reply(event.message_id) + f'绑定成功:{userName}')
        (BF1_PLAYERS_DATA/f'{session}').mkdir(exist_ok=True)
        with open(BF1_PLAYERS_DATA/f'{session}'/f'{user_id}_{personaId}.txt','w') as f:
            f.write(userName)

@BF1_EX.handle()
async def bf1_ex(event:GroupMessageEvent, state:T_State):
    try:
        file_dir = await asyncio.wait_for(draw_exchange(remid2, sid2, sessionID2), timeout=35)
        await BF1_EX.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except: 
        await BF1_EX.send(MessageSegment.reply(event.message_id) + '连接超时')


@BF_BIND.handle()
async def bf1_bindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',1)
    server_id = arg[0]
    server = html.unescape(arg[1])
    session = event.group_id
    print(str(server))
    try:
        result = await upd_servers(remid2, sid2, sessionID2, server)
        server_name = result['result']['gameservers'][0]['name']
        gameId = result['result']['gameservers'][0]['gameId']
        detailedresult = await get_detailedServer_databyid(gameId)
        detailedServer = await upd_detailedServer(remid2, sid2, sessionID2, gameId)
    except: 
        await BF1_BIND.finish('无法获取到服务器数据。')
    
    lens = len(result['result']['gameservers'])
    if lens > 1:
        await BF1_BIND.finish('搜索到的服务器数量大于1。')
    else:
        try:
            (BF1_SERVERS_DATA/f'{session}').mkdir(exist_ok=True)
            (BF1_SERVERS_DATA/f'{session}_jsonBL').mkdir(exist_ok=True)
            (BF1_SERVERS_DATA/f'{session}_jsonGT').mkdir(exist_ok=True)
            with open(BF1_SERVERS_DATA/f'{session}_jsonGT'/f'{session}_{server_id}.json','w', encoding='utf-8') as f:
                json.dump(detailedresult, f, indent=4, ensure_ascii=False)
            with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','w', encoding='utf-8') as f:
                json.dump(detailedServer, f, indent=4, ensure_ascii=False)
            with open(BF1_SERVERS_DATA/f'{session}'/f'{session}_{server_id}.json','w', encoding='utf-8') as f:
                f.write(server)
            await BF1_BIND.finish(f'本群已绑定服务器:{server_name}，编号为{server_id}')
        except FileNotFoundError:
            await BF1_BIND.finish(f'请联系管理员处理')

@BF_REBIND.handle()
async def bf1_rebindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',1)
    server_id = arg[0]
    new_server_id = html.unescape(arg[1])
    session = check_session(event.group_id)
 
    (BF1_SERVERS_DATA/f'{session}').mkdir(exist_ok=True)
    (BF1_SERVERS_DATA/f'{session}_jsonBL').mkdir(exist_ok=True)
    (BF1_SERVERS_DATA/f'{session}_jsonGT').mkdir(exist_ok=True)
    (BF1_SERVERS_DATA/f'{session}_vip').mkdir(exist_ok=True)

    os.rename(BF1_SERVERS_DATA/f'{session}'/ f'{session}_{server_id}.json',BF1_SERVERS_DATA/f'{session}'/ f'{session}_{new_server_id}.json')
    os.rename(BF1_SERVERS_DATA/f'{session}_jsonBL'/ f'{session}_{server_id}.json',BF1_SERVERS_DATA/f'{session}_jsonBL'/ f'{session}_{new_server_id}.json')
    os.rename(BF1_SERVERS_DATA/f'{session}_jsonGT'/ f'{session}_{server_id}.json',BF1_SERVERS_DATA/f'{session}_jsonGT'/ f'{session}_{new_server_id}.json')

    vipfile =  os.listdir(BF1_SERVERS_DATA/f'{session}_vip')

    for i in vipfile:
        nextday = i.split('_')
        if nextday[1] == server_id:
            newvip = ""
            nextday[1] = new_server_id
            for j in nextday:
                newvip += f"{j}_"
            os.rename(BF1_SERVERS_DATA/f'{session}_vip'/i,BF1_SERVERS_DATA/f'{session}_vip'/newvip.rstrip("_"))
    await BF_REBIND.finish(f'已将"{server_id}"改绑为"{new_server_id}"')

@BF_ADDBIND.handle()
async def bf1_addbindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ',1)
    server_id = arg[0]
    new_server_id = html.unescape(arg[1])
    session = check_session(event.group_id)

    with open(BF1_SERVERS_DATA/f'{session}'/ f'{session}_{new_server_id}.json',"w") as f:
        f.write(server_id)
    await BF_ADDBIND.finish(f'已为"{server_id}"添加别名："{new_server_id}"')

@BF1_SERVER_ALARM.handle()
async def bf1_server_alarm(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    try:
        arg = message.extract_plain_text().split(' ')
        session = int(arg[0])
    except:
        session = event.group_id
    user_id = event.user_id

    if(check_admin(check_session(session), user_id)):
        global job_cnt
        global alarm_session
        global alarm_mode

        job_cnt = job_cnt + 1
        job_num = alarm_session.count(session)

        if job_num == 0:
            job_id = alarm_mode.index(0)
            if job_id != job_cnt - 1:
                job_cnt = job_cnt - 1
            alarm_session[job_id] = session
            alarm_mode[job_id] = 1

            print(job_cnt)
            print(alarm_session)
            print(alarm_mode)
            await BF1_SERVER_ALARM.send(f'已打开预警，请注意接收消息')
        else:await BF1_SERVER_ALARM.send(f'请不要重复打开')
    else:
        await BF1_SERVER_ALARM.send('你不是本群组的管理员')

@BF1_SERVER_ALARMOFF.handle()
async def bf1_server_alarmoff(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    session = event.group_id
    user_id = event.user_id
    
    if(check_admin(session, user_id)):
        global job_cnt
        global alarm_session
        global alarm_mode   

        job_num = alarm_session.count(event.group_id)
        if job_num == 0:
            await BF1_SERVER_ALARM.send(f'预警未打开')
        else:
            job_id = alarm_session.index(event.group_id)
            alarm_session[job_id] = 0
            alarm_mode[job_id] = 0
            if job_id == job_cnt - 1 and job_cnt != 1:
                job_cnt = job_cnt - 1
            await BF1_SERVER_ALARM.send(f'已关闭预警')

            print(job_cnt)
            print(alarm_session)
            print(alarm_mode)
    else:
        await BF1_SERVER_ALARM.send('你不是本群组的管理员')


@BF1_BIND.handle()
async def bf1_binding(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    player = message.extract_plain_text().strip()
    user = event.get_user_id()
    session = event.group_id
    try:
        result = await get_player_data(player)
    except:
        await BF1_BIND.send('无法获取到玩家数据，请检查玩家id是否正确。')
        return
    
    result['__update_time'] = time.time()
    try:
        with open(BF1_PLAYERS_DATA/f'{session}'/f'{user}.json','w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        
        await BF1_BIND.send(f'已绑定玩家id {player}，输入"{PREFIX}bf1 me"可查看战绩。')
    except FileNotFoundError:
        await BF1_BIND.send(f'该群未初始化bf1 me功能，请联系管理员使用{PREFIX}bf1 init 初始化')

@BF1_LS.handle()
async def bf1_ls(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    session = event.group_id
    dlist = []
    for fp in (BF1_PLAYERS_DATA/f'{session}').iterdir():
        with open(fp,encoding='utf-8') as f:
            dlist.append(json.load(f))

    md_result = f"""# 本群已绑定战地一玩家数据

按等级排序

{get_group_list(dlist)}"""

    pic = await md_to_pic(md_result, css_path=CODE_FOLDER/"github-markdown-dark.css",width=700)
    await BF1F.send(MessageSegment.image(pic))
    
@BF1_SERVER.handle()
async def bf1_server(event:MessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    server_name = message.extract_plain_text().strip()
    server_data = await get_server_data(server_name)

    md_result = f"""# 搜索服务器：{server_name}
已找到符合要求的服务器 {len(server_data['servers'])} 个，最多显示20个
{get_server_md(server_data)}"""

    pic = await md_to_pic(md_result, css_path=CODE_FOLDER/"github-markdown-dark.css",width=700)
    await BF1F.send(MessageSegment.image(pic))

@BF1_DRAW.handle()
async def bf1_draw_server_array(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    server_id = check_server_id(session,arg[0])
        
    with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
        serverBL = json.load(f)
        gameId = serverBL['result']['serverInfo']['gameId']
        
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
    session = event.group_id

    if session == 609250652:
        try:
            result = await upd_servers(remid2, sid2, sessionID2, server)
            gameId = result['result']['gameservers'][0]['gameId']
        except: 
            await BF1_ADMINDRAW.finish('无法获取到服务器数据。')
        
        try:
            img = draw_server_array2(str(gameId))
            await BF1_ADMINDRAW.send(MessageSegment.reply(event.message_id) + MessageSegment.image(img))
        except:
            await BF1_ADMINDRAW.send(MessageSegment.reply(event.message_id) + traceback.format_exc(2))


@BF1F.handle()
async def bf1_handler(event:MessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    args = message.extract_plain_text().strip().split(' ')
    player = args[0]
    if player == 'me' and isinstance(event, GroupMessageEvent):
        user = event.get_user_id()
        session = event.group_id
        try:
            with open(BF1_PLAYERS_DATA/f'{session}'/f'{user}.json','r', encoding='utf-8') as f:
                result = json.load(f)
        except FileNotFoundError:
            if (BF1_PLAYERS_DATA/f'{session}').exists():
                await BF1F.send(f'未找到绑定玩家数据，请使用"{PREFIX}bf1 bind [玩家id]"进行绑定')
            else:
                await BF1F.send(f'该群未初始化bf1 me功能，请联系管理员使用{PREFIX}bf1 init 初始化')
            return

        
        player = result['userName']
        if time.time() - result['__update_time'] > 3600:
            result = await get_player_data(player)
            result['__update_time'] = time.time()
            with open(BF1_PLAYERS_DATA/f'{session}'/f'{user}.json','w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4) 
    else:
        result = await get_player_data(player)
        result['__update_time'] = time.time()



    if len(args)==1:
        html = apply_template(result,'bf1',PREFIX)
        pic = await html_to_pic(html, viewport={"width": 700,"height":10})
        # md_result = mdtemplate(result)
        # print(md_result)
    elif args[1] == 'weapons':
        md_result = f"""## {player} 武器数据

仅展示击杀数前50数据

{get_weapons_data_md(result,50)}"""
        pic = await md_to_pic(md_result, css_path=CODE_FOLDER/"github-markdown-dark.css",width=700)
    elif args[1] == 'vehicles':
        md_result = f"""## {player} 载具数据

仅展示击杀数前50数据

{get_vehicles_data_md(result,50)}"""        


        pic = await md_to_pic(md_result, css_path=CODE_FOLDER/"github-markdown-dark.css",width=700)
    

    await BF1F.send(MessageSegment.image(pic))

alarm_amount = numpy.zeros((100,100))

#@scheduler.scheduled_job("interval", minutes=5, id=f"job_1")
def check_alarm():
    global alarm_amount
    for i in range(100):
        for j in range(100):
            alarm_amount[i][j] = 0

async def get_server_status(session:int,num,X,i,bot): 
    with open(BF1_SERVERS_DATA/f'{check_session(session)}_jsonBL'/f'{num[i]}','r', encoding='utf-8') as f:
        serverBL= json.load(f)
        gameId = serverBL['result']['serverInfo']['gameId']
        serverName = re.findall(r'_(\w+).json',num[i])[0]
    try:
        async_result = await upd_detailedServer(remid2, sid2, sessionID2, gameId)
        status = async_result['result']['serverInfo']['slots']['Soldier']
        playerAmount = status['current']
        maxPlayers = status['max']
        map = async_result['result']['serverInfo']['mapNamePretty']
        #print(f'{bot}{session}群{i+1}服人数{playerAmount}')
        if max(maxPlayers-34,maxPlayers/3) < playerAmount < maxPlayers-10:
            await bot.send_group_msg(group_id=session, message=f'第{int(alarm_amount[X][i]+1)}次警告：{serverName}服人数大量下降到{playerAmount}人，请注意。当前地图为：{map}。')
            alarm_amount[X][i] = alarm_amount[X][i] + 1
    except:
        print('获取失败')

@scheduler.scheduled_job("interval", minutes=1, id=f"job_0")
async def bf1_alarm():
    global alarm_amount
    global sessionID,access_token,res_access_token,remid,sid
    global sessionID1,access_token1,res_access_token1,remid1,sid1
    global sessionID2,access_token2,res_access_token2,remid2,sid2
    global sessionID3,access_token3,res_access_token3,remid3,sid3
    global sessionID4,access_token4,res_access_token4,remid4,sid4
    global sessionID5,access_token5,res_access_token5,remid5,sid5
    global sessionID6,access_token6,res_access_token6,remid6,sid6

    if time.localtime().tm_min % 15 == 0 :
        check_alarm()
    if time.localtime().tm_hour % 2 == 0 and time.localtime().tm_min == 0:
        res_access_token,access_token = await upd_token(remid,sid)
        res_access_token1,access_token1 = await upd_token(remid1,sid1)
        res_access_token2,access_token2 = await upd_token(remid2,sid2)
        res_access_token3,access_token3 = await upd_token(remid3,sid3)
        res_access_token4,access_token4 = await upd_token(remid4,sid4)
        res_access_token5,access_token5 = await upd_token(remid5,sid5)
        res_access_token6,access_token6 = await upd_token(remid6,sid6)
    if time.localtime().tm_hour % 12 == 0 and time.localtime().tm_min == 0:
        remid,sid,sessionID = await upd_sessionId(res_access_token, remid, sid, 0)
        remid1,sid1,sessionID1 = await upd_sessionId(res_access_token1, remid1, sid1, 1)
        remid2,sid2,sessionID2 = await upd_sessionId(res_access_token2, remid2, sid2, 2)
        remid3,sid3,sessionID3 = await upd_sessionId(res_access_token3, remid3, sid3, 3)
        remid4,sid4,sessionID4 = await upd_sessionId(res_access_token4, remid4, sid4, 4)
        remid5,sid5,sessionID5 = await upd_sessionId(res_access_token5, remid5, sid5, 5)
        remid6,sid6,sessionID6 = await upd_sessionId(res_access_token6, remid6, sid6, 6)
    tasks = []
    for X in range(job_cnt):
        mode = alarm_mode[X]
        session = alarm_session[X]
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
        if mode == 1:
            num = get_server_num(check_session(session))
            for Y in range(len(num)):
                if alarm_amount[X][Y] < 3:
                    tasks.append(asyncio.create_task(get_server_status(session,num,X,Y,bot)))
    if len(tasks) != 0:
        await asyncio.wait(tasks)