import nonebot

from nonebot import get_driver
from nonebot import get_bot

from nonebot import on_command
from nonebot.params import CommandArg, Depends, _command_arg
from nonebot.adapters.onebot.v11 import GROUP, Message, MessageEvent, MessageSegment, GroupMessageEvent
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER

import requests
import json
import os
import numpy
import zhconv
import asyncio

from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_htmlrender import md_to_pic, html_to_pic

from pathlib import Path

import time
from datetime import datetime, timedelta
import datetime

from .config import Config
from .template import apply_template, get_vehicles_data_md, get_weapons_data_md, get_group_list, get_server_md, sort_list_of_dicts
from .utils import PREFIX, BF1_PLAYERS_DATA, BF1_SERVERS_DATA, CODE_FOLDER, request_API, zhconvert, get_wp_info
from .bf1rsp import upd_sessionId, upd_detailedServer, upd_remid_sid, upd_chooseLevel, upd_kickPlayer, upd_banPlayer, upd_unbanPlayer, upd_movePlayer, upd_vipPlayer, upd_unvipPlayer
from .bf1draw import draw_f, draw_server, draw_stat, draw_wp

GAME = 'bf1'
LANG = 'zh-tw'

with open(BF1_SERVERS_DATA/'Caches'/'id.txt','r' ,encoding='UTF-8') as f:
    id_list = f.read().split(',')
    remid = id_list[0]
    sid = id_list[1]
sessionID = upd_sessionId(remid, sid)

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

def search_dicts_by_key_value(dict_list, key, value):
    for d in dict_list:
        if key in d and d[key] == value:
            return True
        else :
            return False

    
def get_bf1status():
    return request_API(GAME,'status',{"platform":"pc"})

def get_player_id(player_name:str)->dict:
    return request_API(GAME,'player',{'name':player_name})

def get_pl(gameID:str)->dict:
    return request_API(GAME,'players',{'gameid':gameID})

def get_player_data(player_name:str)->dict:
    return request_API(GAME,'all',{'name':player_name,'lang':LANG})

def get_server_data(server_name:str)->dict:
    return request_API(GAME,'servers',{'name':server_name,'lang':LANG,"platform":"pc","limit":20})

def get_detailedServer_data(server_name:str)->dict:
    return request_API(GAME,'detailedserver',{'name':server_name})

def get_server_num(session:int):      
    files = os.listdir(BF1_SERVERS_DATA/f'{session}')
    return len(files)

def get_server_status(session:int,num:int): 
    with open(BF1_SERVERS_DATA/f'{session}'/f'{session}_{num}.json','r') as f:
        server_name = f.read()
        return  get_server_data(server_name)['servers'][0]
    
alarm_mode = [0]*100
alarm_session = [0]*100
job_cnt = 0

#bf1 help
BF1_HELP = on_command(f"{PREFIX}help", block=True, priority=1)

#bf1rsp
BF1_ADDADMIN = on_command(f'{PREFIX}addadmin', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_INITMAP = on_command(f'{PREFIX}initmap', block=True, priority=1, permission=GROUP_OWNER | GROUP_ADMIN | SUPERUSER)
BF1_CHOOSELEVEL = on_command(f'{PREFIX}map', block=True, priority=1)
BF1_KICK = on_command(f'{PREFIX}k', block=True, priority=1)
BF1_BAN = on_command(f'{PREFIX}ban', block=True, priority=1)
BF1_UNBAN = on_command(f'{PREFIX}unban', block=True, priority=1)
BF1_MOVE = on_command(f'{PREFIX}move', block=True, priority=1)
BF1_VIP = on_command(f'{PREFIX}vip', block=True, priority=1)
BF1_UNVIP = on_command(f'{PREFIX}unvip', block=True, priority=1)

#bf1status
BF_STATUS = on_command(f'{PREFIX}bf status', block=True, priority=1)
BF1_STATUS = on_command(f'{PREFIX}bf1 status', aliases={f'{PREFIX}战地1', f'{PREFIX}status'}, block=True, priority=1)
BF1_MODE= on_command(f'{PREFIX}bf1 mode', block=True, priority=1)
BF1_MAP= on_command(f'{PREFIX}bf1 map', block=True, priority=1)
BF1_F= on_command(f'{PREFIX}f', block=True, priority=1)
BF1_WP= on_command(f'{PREFIX}武器', aliases={f'{PREFIX}w', f'{PREFIX}wp'}, block=True, priority=1)
BF1_S= on_command(f'{PREFIX}s', aliases={f'{PREFIX}stat', f'{PREFIX}战绩'}, block=True, priority=1)

BF1_BIND_MAG = on_command(f'{PREFIX}bind', aliases={f'{PREFIX}绑定', f'{PREFIX}绑id'}, block=True, priority=1)

#bf1 server alarm
BF_BIND = on_command(f'{PREFIX}绑服', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_SERVER_ALARM = on_command(f'{PREFIX}打开预警', block=True, priority=1)
BF1_SERVER_ALARMOFF = on_command(f'{PREFIX}关闭预警', block=True, priority=1)

#original bf1 chat
BF1_BIND = on_command(f'{PREFIX}bf1 bind', block=True, priority=1)
BF1_LS = on_command(f'{PREFIX}bf1 list', block=True, priority=1)
BF1_SERVER = on_command(f'{PREFIX}bf1 server', block=True, priority=1)
BF1F = on_command(f'{PREFIX}bf1', block=True, priority=1)

@BF1_HELP.handle()
async def bf_help(event:MessageEvent, state:T_State):
    with open(CODE_FOLDER/'Readme.md',encoding='utf-8') as f:
        md_help = f.read()
    
    md_help = md_help.format(p=PREFIX)

    pic = await md_to_pic(md_help, css_path=CODE_FOLDER/"github-markdown-dark.css",width=900)

    await BF1_HELP.send(MessageSegment.image(pic))


@BF1_ADDADMIN.handle()
async def bf1_admin(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    session = event.group_id
    session = check_session(session)
    arg = message.extract_plain_text().split(' ')
    with open(BF1_SERVERS_DATA/f'{session}_admin.txt','r') as f:
        admin = f.read()
        
    with open(BF1_SERVERS_DATA/f'{session}_admin.txt','a+') as f:
        if admin.find(arg[0]) != -1:
            await BF1_ADDADMIN.send(f'请不要重复添加')
        else:
            f.write(f',{arg[0]}')
            await BF1_ADDADMIN.send(f'本群组已添加管理：{int(arg[0])}')

@BF1_INITMAP.handle()
async def bf1_initmap(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    with open(BF1_SERVERS_DATA/f'{session}'/f'{session}_{int(arg[0])}.json','r') as f:
        server = f.read()
    try:
        result = get_server_data(server)
        detailedresult = get_detailedServer_data(server)
        gameId = result['servers'][0]['gameId']
        detailedServer = upd_detailedServer(remid, sid, sessionID, gameId)
    except: 
        await BF1_INITMAP.send('无法获取到服务器数据。')

    with open(BF1_SERVERS_DATA/f'{session}_jsonGT'/f'{session}_{int(arg[0])}.json','w', encoding='utf-8') as f:
        json.dump(detailedresult, f, indent=4, ensure_ascii=False)
    with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{int(arg[0])}.json','w', encoding='utf-8') as f:
        json.dump(detailedServer, f, indent=4, ensure_ascii=False)

        await BF1_INITMAP.send('获取服务器数据完成。')


@BF1_CHOOSELEVEL.handle()
async def bf1_chooseLevel(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id
    
    if(check_admin(session, user_id)):
        server_id = int(arg[0])
        mapName = arg[1]
        try:
            with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
                zh_cn = json.load(f)
                mapName = zh_cn[f'{mapName}']
                mapName_cn = zh_cn[f'{mapName}']
        except:
            await BF1_CHOOSELEVEL.send('请输入正确的地图名称')
            return
        
        with open(BF1_SERVERS_DATA/f'{session}'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            servername = f.read()
        
        serverGT = get_detailedServer_data(servername)
        persistedGameId = serverGT['serverId']
        rotation = serverGT['rotation']
    
        try:
            levelIndex = 0
            while levelIndex<30:
                if rotation[levelIndex]['mapname'] == mapName:
                    break
                else:
                    levelIndex = levelIndex+1
        except:
            await BF1_CHOOSELEVEL.send('未找到此地图，请更新图池')
    
        res = upd_chooseLevel(remid, sid, sessionID, persistedGameId, levelIndex)
        if 'error' in res:
            if res['error']['message'] == 'ServerNotRestartableException':
                await BF1_CHOOSELEVEL.send('服务器未开启')
            elif res['error']['message'] == 'LevelIndexNotSetException':
                await BF1_CHOOSELEVEL.send('sessionId失效')
        else:
            await BF1_CHOOSELEVEL.send(f'地图已切换到：{mapName_cn}')

    else:
        await BF1_CHOOSELEVEL.send('你不是本群组的管理员')

@BF1_KICK.handle()
async def bf1_kick(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = int(arg[0])
        name = arg[1]
        reason = zhconvert(arg[2])

        with open(BF1_SERVERS_DATA/f'{session}_jsonGT'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverGT = json.load(f)
            GameId = serverGT['gameId']

        personaId = get_player_id(name)['id']
        res = upd_kickPlayer(remid, sid, sessionID, GameId, personaId, reason)

        if 'error' in res:
            await BF1_KICK.send(f'踢出玩家：{name}失败，理由：无法处置管理员')
        else:
            await BF1_KICK.send(f'已踢出玩家：{name}，理由：{reason}')
    else:
        await BF1_CHOOSELEVEL.send('你不是本群组的管理员')

@BF1_BAN.handle()
async def bf1_ban(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = int(arg[0])
        personaName = arg[1]
    #    reason = zhconv.convert(arg[2], 'zh-tw')

        with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverBL = json.load(f)
            serverId = serverBL['result']['rspInfo']['server']['serverId']

        res = upd_banPlayer(remid, sid, sessionID, serverId, personaName)

        if 'error' in res:
            await BF1_BAN.send(f'封禁玩家：{personaName}失败，理由：无法处置管理员')
        else:
            await BF1_BAN.send(f'已封禁玩家：{personaName}')
    else:
        await BF1_CHOOSELEVEL.send('你不是本群组的管理员')

@BF1_UNBAN.handle()
async def bf1_unban(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = int(arg[0])
        personaName = arg[1]
    #    reason = zhconv.convert(arg[2], 'zh-tw')

        with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverBL = json.load(f)
            serverId = serverBL['result']['rspInfo']['server']['serverId']
            personaId = get_player_id(personaName)['id']

        res = upd_unbanPlayer(remid, sid, sessionID, serverId, personaId)

        if 'error' in res:
            await BF1_UNBAN.send(f'解封玩家：{personaName}失败')
        else:
            await BF1_UNBAN.send(f'已解封玩家：{personaName}')
    else:
        await BF1_CHOOSELEVEL.send('你不是本群组的管理员')

@BF1_MOVE.handle()
async def bf1_move(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = int(arg[0])
        personaName = arg[1]

        with open(BF1_SERVERS_DATA/f'{session}_jsonGT'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverGT = json.load(f)
            gameId = serverGT['gameId']
            personaId = get_player_id(personaName)['id']
        try:
            pl = get_pl(gameId)
            pl_1 = pl['teams'][0]['players']
            pl_2 = pl['teams'][1]['players']
 
            team1 = search_dicts_by_key_value(pl_1, 'player_id', personaId)
            team2 = search_dicts_by_key_value(pl_2, 'player_id', personaId)

            if team1:
                teamId = 1
                teamName = pl['teams'][1]['name']
            elif team2:
                teamId = 2
                teamName = pl['teams'][0]['name']
            else : BF1_MOVE.send(f'移动失败,玩家不在服务器中')

            res = upd_movePlayer(remid, sid, sessionID, gameId, personaId, teamId)

            if 'error' in res:
                await BF1_MOVE.send(f'移动失败，可能是sessionId过期')
            else:
                await BF1_MOVE.send(f'已移动玩家{personaName}至队伍{3-teamId}：{teamName}')

        except:
            BF1_MOVE.send(f'API HTTP ERROR，请稍后再试')
    else:
        await BF1_CHOOSELEVEL.send('你不是本群组的管理员')

@BF1_VIP.handle()
async def bf1_vip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = int(arg[0])
        personaName = arg[1]
        personaId = get_player_id(personaName)['id']
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
            current_date = datetime.datetime.strptime(current_date[len(current_date)-1], "%Y-%m-%d")
            nextday = current_date + timedelta(days=day)
            current_date = str(current_date).split(' ')[0]
            nextday = str(nextday).split(' ')[0]
            print(f'{session}_{server_id}_{personaId}_{current_date}')
            os.remove(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{current_date}')
            with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}','w', encoding='utf-8') as f:
                f.write('1')
            await BF1_VIP.send(f'已为玩家{personaName}添加{day}天的vip({nextday})')

        else:
            current_date = datetime.date.today()

            nextday = current_date + timedelta(days=day)
            with open(BF1_SERVERS_DATA/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{nextday}','w', encoding='utf-8') as f:
                f.write('1')

            with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
                serverBL = json.load(f)
                serverId = serverBL['result']['rspInfo']['server']['serverId']


            res = upd_vipPlayer(remid, sid, sessionID, serverId, personaName)

            if 'error' in res:
                await BF1_VIP.send('添加失败：可能玩家已经是vip了，且在本地没有记录')
            else:
                await BF1_VIP.send(f'已为玩家{personaName}添加{day}天的vip({nextday})')
    else:
        await BF1_CHOOSELEVEL.send('你不是本群组的管理员')

@BF1_UNVIP.handle()
async def bf1_unvip(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    session = event.group_id
    session = check_session(session)
    user_id = event.user_id

    if(check_admin(session, user_id)):
        server_id = int(arg[0])
        personaName = arg[1]
        personaId = get_player_id(personaName)['id']

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
            os.remove(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_vip'/f'{session}_{server_id}_{personaId}_{current_date}')

        with open(BF1_SERVERS_DATA/f'{session}_jsonBL'/f'{session}_{server_id}.json','r', encoding='utf-8') as f:
            serverBL = json.load(f)
            serverId = serverBL['result']['rspInfo']['server']['serverId']

        res = upd_unvipPlayer(remid, sid, sessionID, serverId, personaId)

        if 'error' in res:
            await BF1_VIP.send('移除失败，可能是sessionId失效')
        else:
            await BF1_VIP.send(f'已移除玩家{personaName}的vip')
    else:
        await BF1_CHOOSELEVEL.send('你不是本群组的管理员')

@BF_STATUS.handle()
async def bf_status(event:GroupMessageEvent, state:T_State):
    try:
        bf1942_json = request_API('bf1942','status')
        bf1942 = bf1942_json['regions'][0]['soldierAmount']
        bf1942_s = bf1942_json['regions'][0]['serverAmount']
        bf2_json = request_API('bf2','status',{'service':'all'})
        bf2 = bf2_json['regions'][0]['soldierAmount']
        bf2_s = bf2_json['regions'][0]['serverAmount']
        bf3_json = request_API('bf3','status')
        bf3 = bf3_json['regions']['ALL']['amounts']['soldierAmount']
        bf3_s = bf3_json['regions']['ALL']['amounts']['serverAmount']
        bf4_json = request_API('bf4','status',{"platform":"pc"})
        bf4 = bf4_json['regions']['ALL']['amounts']['soldierAmount']
        bf4_s = bf4_json['regions']['ALL']['amounts']['serverAmount'] 
        bf1_json = request_API(GAME,'status',{"platform":"pc"})       
        bf1 = bf1_json['regions']['ALL']['amounts']['soldierAmount']
        bf1_s = bf1_json['regions']['ALL']['amounts']['serverAmount']
        bf5_json = request_API('bfv','status',{"platform":"pc"})
        bf5 = bf5_json['regions']['ALL']['amounts']['soldierAmount']
        bf5_s = bf5_json['regions']['ALL']['amounts']['serverAmount']
        bf2042_json = request_API('bf4','status')
        bf2042 = bf2042_json['regions']['ALL']['amounts']['soldierAmount']
        bf2042_s = bf2042_json['regions']['ALL']['amounts']['serverAmount']
        await BF_STATUS.send(f'战地pc游戏人数统计：\n格式：<服数> | <人数>\nbf1942：{bf1942_s} | {bf1942}\nbf2：{bf2_s} | {bf2}\nbf3：{bf3_s} | {bf3}\nbf4：{bf4_s} | {bf4}\nbf1：{bf1_s} | {bf1}\nbfv：{bf5_s} | {bf5}\nbf2042：{bf2042_s} | {bf2042}')
    except: 
        await BF_STATUS.send('无法获取到服务器数据。')

@BF1_STATUS.handle()
async def bf1_status(event:GroupMessageEvent, state:T_State):
    try:
        result = get_bf1status()
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
        await BF1_STATUS.send(f'开启服务器：{server_amount_all}({server_amount_dice})\n游戏中人数：{amount_all}({amount_all_dice})\n排队/观战中：{amount_all_queue}/{amount_all_spe}\n亚服：{amount_asia}({amount_asia_dice})\n欧服：{amount_eu}({amount_eu_dice})')
    except: 
        await BF1_STATUS.send('无法获取到服务器数据。')

@BF1_MODE.handle()
async def bf1_mode(event:GroupMessageEvent, state:T_State):
    try:
        result = get_bf1status()['regions']['ALL']['modePlayers']
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
        await BF1_MODE.send(f'模式人数统计：\n征服：{Conquest}\n行动：{BreakthroughLarge}\n小模式：{TeamDeathMatch+AirAssault+Breakthrough+Domination+Possession+Rush+TugOfWar+ZoneControl}')
    except: 
        await BF1_MODE.send('无法获取到服务器数据。')

@BF1_MAP.handle()
async def bf1_map(event:GroupMessageEvent, state:T_State):
    try:
        result = get_bf1status()['regions']['ALL']['mapPlayers']
        result = sorted(result.items(), key=lambda item:item[1], reverse=True)
        print(result)
        with open(BF1_SERVERS_DATA/'zh-cn.json','r', encoding='utf-8') as f:
            zh_cn = json.load(f)
        for i in range(10):
            result[i] = list(result[i])
            result[i][0] = zh_cn[f'{result[i][0]}']
        await BF1_MAP.send(f'地图游玩情况：\n1.{result[0][0]}：{result[0][1]}\n2.{result[1][0]}：{result[1][1]}\n3.{result[2][0]}：{result[2][1]}\n4.{result[3][0]}：{result[3][1]}\n5.{result[4][0]}：{result[4][1]}\n6.{result[5][0]}：{result[5][1]}\n7.{result[6][0]}：{result[6][1]}\n8.{result[7][0]}：{result[7][1]}\n9.{result[8][0]}：{result[8][1]}\n10.{result[9][0]}：{result[9][1]}')
    except: 
        await BF1_MAP.send('无法获取到服务器数据。')

@BF1_F.handle()
async def bf1_fuwuqi(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    print(message.extract_plain_text())
    mode = 0
    if message.extract_plain_text().startswith(f'{PREFIX}'):
        mode = 2
    else:
        serverName = message.extract_plain_text()
        mode = 1

    print(f'mode={mode}')

    if mode == 1:
        try:
            res = get_server_data(serverName)
            if len(res['result']['gameservers']) == 0:
                1/0
            else:
                try:
                    await asyncio.wait_for(draw_server(serverName,res), timeout=15)
                    await BF1F.send(MessageSegment.image(f'file:///C:\\Users\\pengx\\Desktop\\1\\bf1\\bfchat_data\\bf1_servers\\Caches\\{serverName}.jpg'))
                except:
                    await BF1F.send('连接超时')
        except: await BF1F.send('未查询到数据')

    if mode == 2:
        session = event.group_id
        session = check_session(session)
        server_id = get_server_num(session)
        try:
            await asyncio.wait_for(draw_f(server_id,session,remid, sid, sessionID), timeout=15)
            await BF1F.send(MessageSegment.image(f'file:///C:\\Users\\pengx\\Desktop\\1\\bf1\\bfchat_data\\bf1_servers\\Caches\\{serverName}.jpg'))
        except:
            await BF1F.send('连接超时')

@BF1_S.handle()
async def bf1_statimage(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    print(message.extract_plain_text())
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
            res = get_player_data(playerName)
        except:
            await BF1_S.send('无效id')
        try:
            await asyncio.wait_for(draw_stat(remid, sid, sessionID, res, playerName), timeout=15)
            await BF1_S.send(MessageSegment.image(f'file:///C:\\Users\\pengx\\Desktop\\1\\bf1\\bfchat_data\\bf1_servers\\Caches\\{playerName}.jpg'))
        except asyncio.TimeoutError:
            await BF1_S.send('连接超时')
    if mode == 2:
        if f'{user_id}.txt' in os.listdir(BF1_PLAYERS_DATA):
            with open(BF1_PLAYERS_DATA/f'{user_id}.txt','r') as f:
                playerName = str(f.read())
                res = get_player_data(playerName)
            try:
                await asyncio.wait_for(draw_stat(remid, sid, sessionID, res, playerName), timeout=15)
                await BF1_S.send(MessageSegment.image(f'file:///C:\\Users\\pengx\\Desktop\\1\\bf1\\bfchat_data\\bf1_servers\\Caches\\{playerName}.jpg'))
            except asyncio.TimeoutError:
                await BF1_S.send('连接超时')
        else:
            await BF1_S.send(f'您还未绑定，将尝试绑定: {usercard}')
            try:
                playerName = usercard
                res = get_player_data(playerName)
            except:
                await BF1_S.send('绑定失败')
            else:
                try:
                    await asyncio.wait_for(draw_stat(remid, sid, sessionID, res, playerName), timeout=15)
                    await BF1_S.send(MessageSegment.image(f'file:///C:\\Users\\pengx\\Desktop\\1\\bf1\\bfchat_data\\bf1_servers\\Caches\\{playerName}.jpg'))
                except asyncio.TimeoutError:
                    await BF1_S.send('连接超时')
                with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
                    f.write(playerName)

@BF1_WP.handle()
async def bf1_wp(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()   
    message = message.extract_plain_text()
    print(message)
    usercard = event.sender.card
    user_id = event.user_id

    mode = 0
    if message.startswith(f'{PREFIX}'):
        wpmode = 0
        mode = 2
    else:
        if len(message.split(' ')) == 1:
            [playerName,wpmode,mode] = get_wp_info(message,user_id)
        else:
            playerName = message.split(' ')[0]
            mode = 1
            wpmode = get_wp_info(message.split(' ')[1],user_id)[1]
    
    print(f'mode={mode},wpmode={wpmode}')

    if mode == 1:
        try:
            res = get_player_data(playerName)
        except:
            await BF1_WP.send('无效id')
        try:
            await asyncio.wait_for(draw_wp(remid, sid, sessionID, res, playerName, wpmode), timeout=15)
            await BF1_WP.send(MessageSegment.image(f'file:///C:\\Users\\pengx\\Desktop\\1\\bf1\\bfchat_data\\bf1_servers\\Caches\\{playerName}_wp.jpg'))
        except asyncio.TimeoutError:
            await BF1_WP.send('连接超时')
    if mode == 2:
        if f'{user_id}.txt' in os.listdir(BF1_PLAYERS_DATA):
            with open(BF1_PLAYERS_DATA/f'{user_id}.txt','r') as f:
                playerName = str(f.read())
                res = get_player_data(playerName)
            try:
                await asyncio.wait_for(draw_wp(remid, sid, sessionID, res, playerName, wpmode), timeout=15)
                await BF1_WP.send(MessageSegment.image(f'file:///C:\\Users\\pengx\\Desktop\\1\\bf1\\bfchat_data\\bf1_servers\\Caches\\{playerName}_wp.jpg'))
            except asyncio.TimeoutError:
                await BF1_WP.send('连接超时')
        else:
            await BF1_WP.send(f'您还未绑定，将尝试绑定: {usercard}')
            try:
                playerName = usercard
                res = get_player_data(playerName)
            except:
                await BF1_S.send('绑定失败')
            else:
                try:
                    await asyncio.wait_for(draw_wp(remid, sid, sessionID, res, playerName, wpmode), timeout=15)
                    await BF1_WP.send(MessageSegment.image(f'file:///C:\\Users\\pengx\\Desktop\\1\\bf1\\bfchat_data\\bf1_servers\\Caches\\{playerName}_wp.jpg'))
                except asyncio.TimeoutError:
                    await BF1_WP.send('连接超时')
                with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
                    f.write(playerName)



@BF1_BIND_MAG.handle()
async def bf1_bindplayer(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    playerName = message.extract_plain_text()
    user_id = event.user_id

    try:
        res = get_player_data(playerName)
    except:
        await BF1_BIND_MAG.send('绑定失败，无效id或http error')
    else:
        with open(BF1_PLAYERS_DATA/f'{user_id}.txt','w') as f:
            f.write(playerName)
        await BF1_BIND_MAG.send('绑定成功')

@BF_BIND.handle()
async def bf1_bindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    server_id = arg[0]
    server = arg[1]
    session = event.group_id
    try:
        result = get_server_data(server)
        detailedresult = get_detailedServer_data(server)
        server_name = result['servers'][0]['prefix']
        gameId = result['servers'][0]['gameId']
        detailedServer = upd_detailedServer(remid, sid, sessionID, gameId)
    except: 
        await BF1_BIND.send('无法获取到服务器数据。')
        return
    
    lens = len(result['servers'])
    if lens > 1:
        await BF1_BIND.send('搜索到的服务器数量大于1。')
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
            await BF1_BIND.send(f'本群已绑定服务器:{server_name}，编号为{server_id}')
        except FileNotFoundError:
            await BF1_BIND.send(f'请联系管理员处理')

@BF1_SERVER_ALARM.handle()
async def bf1_server_alarm(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    try:
        arg = message.extract_plain_text().split(' ')
        session = int(arg[0])
    except:
        session = event.group_id
    user_id = event.user_id

    if(check_admin(session, user_id)):
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
        await BF1_CHOOSELEVEL.send('你不是本群组的管理员')

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
        await BF1_CHOOSELEVEL.send('你不是本群组的管理员')


@BF1_BIND.handle()
async def bf1_binding(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    player = message.extract_plain_text().strip()
    user = event.get_user_id()
    session = event.group_id
    try:
        result = get_player_data(player)
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
    server_data = get_server_data(server_name)

    md_result = f"""# 搜索服务器：{server_name}
已找到符合要求的服务器 {len(server_data['servers'])} 个，最多显示20个
{get_server_md(server_data)}"""

    pic = await md_to_pic(md_result, css_path=CODE_FOLDER/"github-markdown-dark.css",width=700)
    await BF1F.send(MessageSegment.image(pic))




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
            result = get_player_data(player)
            result['__update_time'] = time.time()
            with open(BF1_PLAYERS_DATA/f'{session}'/f'{user}.json','w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4) 
    else:
        result = get_player_data(player)
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

@scheduler.scheduled_job("interval", minutes=1, id=f"job_0")
async def bf1_alarm():
    global alarm_amount
    global sessionID

    print(alarm_amount)
    if time.localtime().tm_min % 15 == 0  :
        check_alarm()
    elif time.localtime().tm_hour == 0 and time.localtime().tm_min == 0 :
        sessionID = upd_sessionId(remid, sid)
    bot = nonebot.get_bot()
    for X in range(job_cnt):
        mode = alarm_mode[X]
        session = alarm_session[X]
        if mode == 1:
            num = get_server_num(session)
            for i in range(num):
                if alarm_amount[X][i] < 3:
                    try:
                        status = get_server_status(session,i+1)
                    except:
                        print('获取失败')
                    playerAmount = status['playerAmount']
                    maxPlayers = status['maxPlayers']
                    print(f'{session}群{i+1}服人数{playerAmount}')
                    map = status['currentMap']
                    if max(maxPlayers/3,maxPlayers-34) < playerAmount < maxPlayers - 10:
                        await bot.send_group_msg(group_id=session, message=f'第{int(alarm_amount[X][i]+1)}次警告：{i+1}服人数大量下降到{playerAmount}人，请注意。当前地图为：{map}。')
                        alarm_amount[X][i] = alarm_amount[X][i] + 1