from nonebot.log import logger
from nonebot.params import CommandArg, _command_arg, Arg
from nonebot.adapters.onebot.v11 import Message, MessageSegment, GroupMessageEvent, Bot
from nonebot.typing import T_State


import httpx,html
import json

import zhconv
import asyncio
import random
import datetime
import traceback

from sqlalchemy.future import select
from sqlalchemy import func
from random import choice
from io import BytesIO
from PIL import Image

from ..utils import BF1_PLAYERS_DATA, BF1_SERVERS_DATA, CURRENT_FOLDER, request_API
from ..bf1rsp import *
from ..bf1draw import *
from ..bf1draw2 import draw_server_array2,upd_draw
from ..secret import *
from ..image import upload_img
from ..rdb import *
from ..bf1helper import *
from .matcher import (
    BF1_CODE,BF1_REPORT,BF1_BOT,
    BF1_PLA,BF1_PLAA,
    BF_STATUS,BF1_STATUS,BF1_MODE,BF1_MAP,BF1_INFO,
    BF1_EX,BF1_DRAW,BF1_ADMINDRAW
)

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
    except RSPException as rsp_exc:
        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
    except:
        logger.warning(traceback.format_exc())
        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + traceback.format_exception_only())
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

@BF1_BOT.handle()
async def bf1_init_botqq(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    
    async with async_db_session() as session:
        bf1admins = [row[0] for row in (await session.execute(select(Bf1Admins).order_by(Bf1Admins.id))).all()]
        pids = [admin.pid for admin in bf1admins]
        remid, sid, sessionID, _ = await get_one_random_bf1admin()
        try:
            userName_res = await upd_getPersonasByIds(remid, sid, sessionID, pids)
            names = [userName_res['result'][str(pid)]['displayName'] for pid in pids]
            num_res = (await session.execute(select(ServerBf1Admins, func.count()).group_by(ServerBf1Admins.pid))).all()
            nums = {r[0].pid:r[1] for r in num_res}
        except RSPException as rsp_exc:
            await BF1_BOT.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        except:
            logger.warning(traceback.format_exc())
            await BF1_BOT.finish(MessageSegment.reply(event.message_id) + traceback.format_exception_only())
    msg = ''
    for i in range(len(bf1admins)):
        admins = nums[bf1admins[i].pid] if bf1admins[i].pid in nums.keys() else 0
        if int(admins) < 20:
            msg = msg + f'{bf1admins[i].id}. {names[i]}: {admins}/20 \n'
    msg.rstrip()
    await BF1_BOT.send(MessageSegment.reply(event.message_id) + f'请选择未满的eaid添加服管：\n{msg}') 

@BF1_PLA.handle()
async def bf_pla(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    platoon = html.unescape(message.extract_plain_text())

    try:
        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
        file_dir = await asyncio.wait_for(draw_searchplatoons(remid, sid, sessionID,platoon), timeout=20)
        await BF1_PLA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except RSPException as rsp_exc:
        await BF1_PLA.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
    except:
        logger.warning(traceback.format_exc())
        await BF1_PLA.finish(MessageSegment.reply(event.message_id) + traceback.format_exception_only())

@BF1_PLAA.handle()
async def bf_plaa(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    platoon = html.unescape(message.extract_plain_text())

    try:
        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
        file_dir = await asyncio.wait_for(draw_detailplatoon(remid, sid, sessionID,platoon), timeout=20)
        await BF1_PLAA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except RSPException as rsp_exc:
        await BF1_PLAA.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
    except:
        logger.warning(traceback.format_exc())
        await BF1_PLAA.finish(MessageSegment.reply(event.message_id) + traceback.format_exception_only())

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
    except RSPException as rsp_exc:
        await BF1_INFO.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
    except:
        logger.warning(traceback.format_exc())
        await BF1_INFO.finish(MessageSegment.reply(event.message_id) + "未查询到数据\n" \
                                + traceback.format_exception_only())
    else:
        status1 = servermode + '-' +servermap
        status1 = zhconv.convert(status1,'zh-cn')
        status2 = f'{serveramount}/{servermaxamount}[{serverque}]({serverspect})'
        status3 = f'★{serverstar}'
        msg = f'{servername}\n人数: {status2} {status3}\n地图: {status1}\nGameId: {gameId}\nGuid: {guid}\nServerId: {serverid}\n创建时间: {createdDate}\n续费时间: {updatedDate}\n到期时间: {expirationDate}\n服主EAID: {userName}'
        await BF1_INFO.send(MessageSegment.reply(event.message_id) + msg)

@BF1_EX.handle()
async def bf1_ex(event:GroupMessageEvent, state:T_State):
    try:
        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
        file_dir = await asyncio.wait_for(draw_exchange(remid, sid, sessionID), timeout=35)
        await BF1_EX.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except RSPException as rsp_exc:
        await BF1_EX.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
    except:
        logger.warning(traceback.format_exc())
    await BF1_EX.finish(MessageSegment.reply(event.message_id) + traceback.format_exception_only())

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
    except RSPException as rsp_exc:
        await BF1_DRAW.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
    except:
        logger.warning(traceback.format_exc())
        await BF1_DRAW.finish(MessageSegment.reply(event.message_id) + traceback.format_exception_only())


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
            img = draw_server_array2(str(gameId))
            await BF1_ADMINDRAW.send(MessageSegment.reply(event.message_id) + MessageSegment.image(img))
        except RSPException as rsp_exc:
            await BF1_ADMINDRAW.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        except:
            logger.warning(traceback.format_exc())
            await BF1_ADMINDRAW.finish(MessageSegment.reply(event.message_id) + traceback.format_exception_only())
