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

from nonebot_plugin_apscheduler import scheduler

from nonebot_plugin_htmlrender import md_to_pic, html_to_pic

from pathlib import Path

import time

from .config import Config
from .template import apply_template, get_vehicles_data_md, get_weapons_data_md, get_group_list, get_server_md, sort_list_of_dicts
from .utils import PREFIX, BF1_PLAYERS_DATA, BF1_SERVERS_DATA, CODE_FOLDER, request_API

GAME = 'bf1'
LANG = 'zh-tw'

def get_bf1status():
    return request_API(GAME,'status',{"platform":"pc"})

def get_player_data(player_name:str)->dict:
    return request_API(GAME,'all',{'name':player_name,'lang':LANG})

def get_server_data(server_name:str)->dict:
    return request_API(GAME,'servers',{'name':server_name,'lang':LANG,"platform":"pc","limit":20})

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

BF1_STATUS = on_command(f'{PREFIX}bf1 status', block=True, priority=1)

BF1_MODE= on_command(f'{PREFIX}bf1 mode', block=True, priority=1)

BF1_MAP= on_command(f'{PREFIX}bf1 map', block=True, priority=1)

BF_BIND = on_command(f'{PREFIX}绑服', block=True, priority=1, permission=SUPERUSER)

BF1_SERVER_ALARM = on_command(f'{PREFIX}打开预警', block=True, priority=1, permission=GROUP_OWNER | GROUP_ADMIN | SUPERUSER)

BF1_SERVER_ALARMOFF = on_command(f'{PREFIX}关闭预警', block=True, priority=1, permission=GROUP_OWNER | GROUP_ADMIN | SUPERUSER)

BF1_BIND = on_command(f'{PREFIX}bf1 bind', block=True, priority=1)

BF1_LS = on_command(f'{PREFIX}bf1 list', block=True, priority=1)

BF1_SERVER = on_command(f'{PREFIX}bf1 server', block=True, priority=1)

BF1F = on_command(f'{PREFIX}bf1', block=True, priority=1)

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
        print(result[0][1])
        await BF1_MAP.send(f'地图游玩情况：\n{result[0][0]}：{result[0][1]}\n{result[1][0]}：{result[1][1]}\n{result[2][0]}：{result[2][1]}\n{result[3][0]}：{result[3][1]}\n{result[4][0]}：{result[4][1]}\n{result[5][0]}：{result[5][1]}\n{result[6][0]}：{result[6][1]}\n{result[7][0]}：{result[7][1]}')
    except: 
        await BF1_MAP.send('无法获取到服务器数据。')

@BF_BIND.handle()
async def bf1_bindserver(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split(' ')
    server_id = arg[0]
    server = arg[1]
    session = event.group_id
    try:
        result = get_server_data(server)
        server_name = result['servers'][0]['prefix']
    except: 
        await BF1_BIND.send('无法获取到服务器数据。')
        return
    
    lens = len(result['servers'])
    if lens > 1:
        await BF1_BIND.send('搜索到的服务器数量大于1。')
    else:
        try:
            (BF1_SERVERS_DATA/f'{session}').mkdir(exist_ok=True)
            with open(BF1_SERVERS_DATA/f'{session}'/f'{session}_{server_id}.json','w', encoding='utf-8') as f:
                f.write(server_name)

                await BF1_BIND.send(f'本群已绑定服务器:{server_name}，编号为{server_id}')
        except FileNotFoundError:
            await BF1_BIND.send(f'请联系管理员处理')

@BF1_SERVER_ALARM.handle()
async def bf1_server_alarm(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()

    global job_cnt
    global alarm_session
    global alarm_mode

    job_cnt = job_cnt + 1
    job_num = alarm_session.count(event.group_id)

    if job_num == 0:
        job_id = alarm_mode.index(0)
        if job_id != job_cnt - 1:
            job_cnt = job_cnt - 1
        alarm_session[job_id] = event.group_id
        alarm_mode[job_id] = 1

        print(job_cnt)
        print(alarm_session)
        print(alarm_mode)
        await BF1_SERVER_ALARM.send(f'已打开预警，请注意接收消息')
    else:await BF1_SERVER_ALARM.send(f'请不要重复打开')

@BF1_SERVER_ALARMOFF.handle()
async def bf1_server_alarmoff(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
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
    print(alarm_amount)
    if time.localtime().tm_min % 15 == 0  :
        check_alarm()
    bot = nonebot.get_bot()
    for X in range(job_cnt):
        mode = alarm_mode[X]
        session = alarm_session[X]
        if mode == 1:
            num = get_server_num(session)
            for i in range(num):
                if alarm_amount[X][i] < 3:
                    status = get_server_status(session,i+1)
                    playerAmount = status['playerAmount']
                    maxPlayers = status['maxPlayers']
                    print(f'{session}群{i+1}服人数{playerAmount}')
                    map = status['currentMap']
                    if max(maxPlayers/3,maxPlayers-34) < playerAmount < maxPlayers - 10:
                        await bot.send_group_msg(group_id=session, message=f'第{int(alarm_amount[X][i]+1)}次警告：{i+1}服人数大量下降到{playerAmount}人，请注意。当前地图为：{map}。')
                        alarm_amount[X][i] = alarm_amount[X][i] + 1