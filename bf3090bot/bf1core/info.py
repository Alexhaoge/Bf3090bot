from nonebot.log import logger
from nonebot.params import CommandArg, _command_arg, Arg
from nonebot.adapters.onebot.v11 import Message, MessageSegment, GroupMessageEvent, Bot
from nonebot.typing import T_State


import html
import json
import re
import zhconv
import asyncio
import random
import datetime
import traceback

from sqlalchemy.future import select
from sqlalchemy import func
from io import BytesIO
from PIL import Image

from ..utils import PREFIX, BF1_PLAYERS_DATA, BF1_SERVERS_DATA, CURRENT_FOLDER, request_GT_API
from ..bf1rsp import *
from ..bf1draw import *
from ..bf1draw2 import draw_server_array2
from ..secret import *
from ..image import upload_img
from ..rdb import *
from ..bf1helper import *
from .matcher import (
    BF1_CODE, BF1_ADMIN_ADD_CODE, BF1_ADMIN_DEL_CODE,
    BF1_REPORT,
    BF1_BOT,
    BF1_PLA,BF1_PLAA,
    BF_STATUS,BF1_STATUS,BF1_MODE,BF1_MAP,
    BF1_EX,
    BF1_DRAW,BF1_ADMINDRAW,
    BF1_F, BF1_INFO, BF1_GAMEID_INFO, BF1_FADMIN, BF1_F_RET_TXT
)

code_file_lock = asyncio.Lock()

@BF1_CODE.handle()
async def cmd_receive(event: GroupMessageEvent, state: T_State, pic: Message = CommandArg()):
    message = _command_arg(state) or event.get_message()
    user_id = event.user_id
    code = message.extract_plain_text().split()[0]
    groupqq = await check_session(event.group_id)

    async with code_file_lock:
        with open(CURRENT_FOLDER/'code.txt','r') as f:
            codearg = re.split('\r|\n', f.read())
    async with async_db_session() as session:
        player_r = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq, qq=user_id))).first()
        if player_r:
            personaId = player_r[0].pid
            code_r = (await session.execute(select(BotVipCodes).filter_by(code=code).with_for_update())).first()
            if code_r: 
                exist_pid = code_r[0].pid
                valid = False
                if int(exist_pid) == int(personaId):
                    if not code_r[0].qq:
                        valid = True
                        code_r[0].qq = user_id
                        session.add(code_r[0])
                        await session.commit()
                    elif player_r[0].qq == code_r[0].qq:
                        valid = True
                if valid:
                    state["personaId"] = personaId
                else:
                    remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
                    try:
                        res = await upd_getPersonasByIds(remid, sid, sessionID, [exist_pid])
                        userName = res['result'][f'{exist_pid}']['displayName']
                    except Exception as e:
                        await BF1_CODE.finish(MessageSegment.reply(event.message_id) + f'这个code已被他人使用，使用者pid为{exist_pid}' \
                                              + (f'({code_r[0].qq})' if code_r[0].qq else ''))
                    await BF1_CODE.finish(MessageSegment.reply(event.message_id) + f'这个code已经被使用过，使用者id为：{userName}' \
                                              + (f'({code_r[0].qq})' if code_r[0].qq else ''))
            else:        
                if code in codearg:
                    session.add(BotVipCodes(code=code, pid=personaId, qq=user_id))
                    await session.commit()
                    state["personaId"] = personaId

                    codearg.remove(code)
                    async with code_file_lock:
                        with open(CURRENT_FOLDER/'code.txt','w') as f:
                            f.write('\n'.join(codearg))
                else:
                    await BF1_CODE.finish(MessageSegment.reply(event.message_id) + '请输入正确的code。')
        else:
            await BF1_CODE.finish(MessageSegment.reply(event.message_id) + '请先绑定eaid。')

@BF1_ADMIN_ADD_CODE.handle()
async def bf1_admin_add_code(event: GroupMessageEvent, state: T_State):
    message = _command_arg(state) or event.get_message()
    code = message.extract_plain_text()
    async with code_file_lock:
        with open(CURRENT_FOLDER/'code.txt', 'a') as f:
            f.write('\n' + code)
    await BF1_ADMIN_ADD_CODE.send(MessageSegment.reply(event.message_id) + f'已添加背景图片码{code}')

@BF1_ADMIN_DEL_CODE.handle()
async def bf1_admin_del_code(event: GroupMessageEvent, state: T_State):
    message = _command_arg(state) or event.get_message()
    code = message.extract_plain_text()
    async with code_file_lock:
        with open(CURRENT_FOLDER/'code.txt', 'r') as f:
            codes = re.split('\r|\n', f.read())
    if code in codes:
        codes.remove(code)
        async with code_file_lock:
            with open(CURRENT_FOLDER/'code.txt', 'w') as f:
                f.write('\n'.join(codes))
        await BF1_ADMIN_DEL_CODE.send(MessageSegment.reply(event.message_id) + f'已删除背景图片码{code}')
    else:
        async with async_db_session() as session:
            code_r = (await session.execute(select(BotVipCodes).filter_by(code=code))).first()
            msg = f'背景图片码{code}已被使用' if code_r else f'背景图片码{code}从未被添加'
        await BF1_ADMIN_DEL_CODE.send(MessageSegment.reply(event.message_id) + msg)

@BF1_CODE.got("Message_pic", prompt="请发送你的背景图片，最好为正方形jpg格式。如果发现发送一切违反相关法律规定的图片的行为，将永久停止你的bot使用权限！")
async def get_pic(bot: Bot, event: GroupMessageEvent, state: T_State, msgpic: Message = Arg("Message_pic")):
    for segment in msgpic:
        if segment.type == "image":
            pic_url: str = segment.data["url"]  # 图片链接
            logger.success(f"获取到图片: {pic_url}")
            response = await httpx_client.get(pic_url,timeout=20)
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
        state['pid'] = personaId
        state['status'] = ''
        state['bfban_status'] = 0
        state['case_body'] = ''
        state['case_num'] = 0
        state['case_video_num'] = 0
        state['target_EAID'] = name
        state['txturl'] = []
        state['videourl'] = ""
        await BF1_REPORT.send(MessageSegment.reply(event.message_id) + f'请选择举报渠道(1或2): \n1.BFEAC\n2.BFBAN\n其他视为放弃举报')
    except RSPException as rsp_exc:
        await BF1_REPORT.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + '获取玩家id出错\n' + traceback.format_exception_only(e))

@BF1_REPORT.got("Message")
async def get_bfban_or_bfeac(bot: Bot, event: GroupMessageEvent, state: T_State, msgpic: Message = Arg("Message")):    
    personaId = state['pid']
    name = state['target_EAID']
    
    if not state['status']:
        for segment in msgpic:
            if segment.is_text():
                if str(segment) == "1" or str(segment) == "bfeac" or str(segment) == "BFEAC":
                    bfeac = await bfeac_checkBan(personaId)
                    if bfeac['stat'] == '无':
                        state['status'] = 'bfeac'
                        state['case_body'] = ''
                        state['case_num'] = 0
                        state['target_EAID'] = name
                        state['txturl'] = []
                        await BF1_REPORT.reject(f'开始举报(BFEAC): {name}\n可以发送图片/文字/链接\n图片和文字请分开发送\n共计可以接收5次举报消息\n声明: 每次举报都会在后台记录举报者的qq号码，仅作为留档用。恶意举报将永久封停你的bot使用权限，情节严重者将封停群内所有成员的bot使用权。\n学习如何鉴挂: https://bitly.ws/YQAg')
                    elif bfeac['stat'] == '已封禁':
                        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'该玩家已被bfeac封禁，案件链接: {bfeac["url"]}')
                    else:
                        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'该玩家在bfeac已经有案件，但是没有被封禁，案件链接: {bfeac["url"]}。\n如果想要补充证据请直接注册账号并在case下方回复，管理员会看到并处理你的回复。')    
                elif str(segment) == "2" or str(segment) == "bfban" or str(segment) == "BFBAN":
                    bfban = await bfban_checkBan(personaId)
                    if bfban['stat'] == '无':
                        state['status'] = 'bfban'
                        state['case_body'] = ''
                        state['case_num'] = 0
                        state['case_video_num'] = 0
                        state['target_EAID'] = name
                        state['txturl'] = []
                        state['videourl'] = ""
                        await BF1_REPORT.reject(f'开始举报(BFBAN): {name}\n请输入举报类型\n1.隐身 2.透视 3.自瞄\n4.传送 5.魔法子弹\n6.改装备 7.改伤 8.炸服\n示例: 17——隐身+改伤')
                    elif bfban['stat'] == '实锤':
                        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'该玩家已被bfban封禁，案件链接: {bfban["url"]}')
                    else:
                        await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'该玩家在bfban已经有案件，但是没有被封禁，案件链接: {bfeac["url"]}。\n如果想要补充证据请直接注册账号并在case下方回复，管理员会看到并处理你的回复。')    
                else:
                    await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'已取消举报。')
            else:
                await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'已取消举报。')
    else:
        if state['status'] == 'bfeac':
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
                        if state['case_num'] <= 5:
                            state['case_num'] += 1
                            state['case_body'] += "<p>" + str(segment) + "</p>"
                            state['txturl'].append(segment)
                            await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'文字上传完成\n发送确认以结束举报\n发送取消以取消举报\n发送预览以预览举报\n你还可以发送{5-state["case_num"]}条证据')
                        else:
                            await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'能够发送的证据数量已满。')
                elif segment.type == "image":
                    if state['case_num'] <= 5:    
                        pic_url: str = segment.data["url"]  # 图片链接
                        logger.success(f"获取到图片: {pic_url}")
                        response = await httpx_client.get(pic_url,timeout=20)
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
        else:
            if not state['bfban_status']:
                for segment in msgpic:
                    if segment.is_text():
                        try:
                            state['cheat_number'] = int(str(segment))
                            state['bfban_status'] = 1
                        except:
                            await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + "发送举报类型的格式不合法。\n示例: \n1——隐身\n17——隐身+改伤\n123——隐身+透视+自瞄") 
                        else:
                            await BF1_REPORT.reject(f'进入举报流程: \n可以发送图片/文字/链接\n请分开发送链接和图片\n可以接收5次举报消息\n可以接收3次视频链接\n声明: 每次举报都会在后台记录举报者的qq号码，仅作为留档用。恶意举报将永久封停你的bot使用权限，情节严重者将封停群内所有成员的bot使用权。\n学习如何鉴挂: https://bitly.ws/YQAg')
                    else:
                        await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + "发送举报类型的格式不合法。\n示例: \n1——隐身\n17——隐身+改伤\n123——隐身+透视+自瞄") 
            else:
                for segment in msgpic:
                    if segment.is_text():
                        if str(segment) == "确认":
                            bg_url = "https://3090bot.oss-cn-beijing.aliyuncs.com/asset/3090.png"
                            state['case_body'] += "<p><img class=\"img-fluid\" src=\"" + bg_url + "\"/></p>"
                            with open(CURRENT_FOLDER/'code.txt','r') as f:
                                token = f.read()
                            res = await bfban_report(state['target_EAID'],state['case_body'],state['cheat_number'],state['videourl'].rstrip(","),token)
                            try:
                                case_code = res['code']
                                case_data = res['data']
                            except Exception as e:
                                print(e)
                                await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'举报失败，请联系作者处理。')
                            else:
                                if case_code == "report.success":
                                    with open(CURRENT_FOLDER/'bfban_case'/f'{state["pid"]}.txt','w') as f:
                                        string = "\"qq\":" + str(event.user_id) + "\n\"group\":" + str(event.group_id)
                                        f.write(string)
                                    await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'举报成功，案件链接: https://bfban.com/player/{state["pid"]}。')
                                else:
                                    await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'举报失败，请联系作者处理。')
                        elif str(segment) == "取消":
                            await BF1_REPORT.finish(MessageSegment.reply(event.message_id) + f'已取消举报。')
                            
                        elif str(segment) == "预览":
                            msg_show = ''
                            for body in state['txturl']:
                                if str(body).startswith('https://3090bot'):
                                    msg_show += (MessageSegment.image(body) +'\n')
                                else:
                                    msg_show += (body + '\n')
                            msg_show += "视频链接: " + state['videourl'].rstrip(",")
                            await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + msg_show)
                        elif str(segment).startswith("http") or str(segment).startswith("www"):
                            if state['case_video_num'] <= 3:
                                state['videourl'] += f'{segment},'
                                state['case_video_num'] += 1
                                await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'视频链接上传完成\n发送确认以结束举报\n发送取消以取消举报\n发送预览以预览举报\n你还可以发送{3-state["case_video_num"]}条链接\n你还可以发送{5-state["case_num"]}条图片/文字证据')
                            else:
                                await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'能够发送的链接数量已满。')     
                        else:
                            if state['case_num'] <= 5:
                                state['case_num'] += 1
                                state['case_body'] += "<p>" + str(segment) + "</p>"
                                state['txturl'].append(segment)
                                await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'文字上传完成\n发送确认以结束举报\n发送取消以取消举报\n发送预览以预览举报\n你还可以发送{3-state["case_video_num"]}条链接\n你还可以发送{5-state["case_num"]}条图片/文字证据')
                            else:
                                await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'能够发送的证据数量已满。')
                    elif segment.type == "image":
                        if state['case_num'] < 5:    
                            pic_url: str = segment.data["url"]  # 图片链接
                            logger.success(f"获取到图片: {pic_url}")
                            response = await httpx_client.get(pic_url,timeout=20)
                            image_data = response.content
                            image = Image.open(BytesIO(image_data))
                            
                            imageurl = upload_img(image,f"report{random.randint(1, 100000000000)}.png")
                            state['case_num'] += 1
                            state['case_body'] += "<p><img class=\"img-fluid\" src=\"" + imageurl + "\"/></p>"
                            state['txturl'].append(imageurl)
                            await BF1_REPORT.reject(MessageSegment.reply(event.message_id) + f'图片上传完成\n发送确认以结束举报\n发送取消以取消举报\n发送预览以预览举报\n你还可以发送{3-state["case_video_num"]}条链接\n你还可以发送{5-state["case_num"]}条图片/文字证据')
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
            num_res = (await session.execute(select(ServerBf1Admins.pid, func.count()).group_by(ServerBf1Admins.pid))).all()
            nums = {r[0]:r[1] for r in num_res}
        except RSPException as rsp_exc:
            await BF1_BOT.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_BOT.finish(MessageSegment.reply(event.message_id) + '获取玩家id出错\n' + traceback.format_exception_only(e))
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
        await BF1_PLAA.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_PLA.finish(MessageSegment.reply(event.message_id) + '无法获取战队信息\n' + traceback.format_exception_only(e))

@BF1_PLAA.handle()
async def bf_plaa(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    platoon = html.unescape(message.extract_plain_text())

    try:
        remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
        file_dir = await asyncio.wait_for(draw_detailplatoon(remid, sid, sessionID,platoon), timeout=20)
        await BF1_PLAA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except RSPException as rsp_exc:
        await BF1_PLAA.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_PLAA.finish(MessageSegment.reply(event.message_id) + '无法获取战队信息' + traceback.format_exception_only(e))

@BF_STATUS.handle()
async def bf_status(event:GroupMessageEvent, state:T_State):
    try:
        tasks = []
        tasks.append(asyncio.create_task(request_GT_API('bf1942','status')))
        tasks.append(asyncio.create_task(request_GT_API('bf2','status',{"platform":"pc"})))
        tasks.append(asyncio.create_task(request_GT_API('bf3','status')))
        tasks.append(asyncio.create_task(request_GT_API('bf4','status',{"platform":"pc"})))
        tasks.append(asyncio.create_task(request_GT_API('bf1','status',{"platform":"pc"})))
        tasks.append(asyncio.create_task(request_GT_API('bfv','status',{"platform":"pc"})))
        tasks.append(asyncio.create_task(request_GT_API('bf2042','status')))
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
        await BF1_INFO.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_INFO.finish(MessageSegment.reply(event.message_id) + "未查询到数据\n" \
                                + traceback.format_exception_only(e))
    else:
        status1 = servermode + '-' +servermap
        status1 = zhconv.convert(status1,'zh-cn')
        status2 = f'{serveramount}/{servermaxamount}[{serverque}]({serverspect})'
        status3 = f'★{serverstar}'
        msg = f'{servername}\n人数: {status2} {status3}\n地图: {status1}\nGameId: {gameId}\nGuid: {guid}\nServerId: {serverid}\n创建时间: {createdDate}\n续费时间: {updatedDate}\n到期时间: {expirationDate}\n服主EAID: {userName}'
        await BF1_INFO.send(MessageSegment.reply(event.message_id) + msg)

@BF1_GAMEID_INFO.handle()
async def bf1_gameid_info(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()

    gameid_str = message.extract_plain_text()
    if not gameid_str.isdigit():
        await BF1_GAMEID_INFO.finish(MessageSegment.reply(event.message_id) + '请输入数字gameid，服务器名称查询请使用.info')
    gameId = int(gameid_str)
    remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]
    try:
        res_0 = await upd_detailedServer(remid, sid, sessionID, gameId)
        rspInfo = res_0['result']['rspInfo']
        serverid = rspInfo['server']['serverId']
        ownerid = rspInfo['server']['ownerId']
        createdDate = rspInfo.get("server", {}).get("createdDate")
        createdDate = datetime.datetime.fromtimestamp(int(createdDate) / 1000)
        expirationDate = rspInfo.get("server", {}).get("expirationDate")
        expirationDate = datetime.datetime.fromtimestamp(int(expirationDate) / 1000)
        updatedDate = rspInfo.get("server", {}).get("updatedDate")
        updatedDate = datetime.datetime.fromtimestamp(int(updatedDate) / 1000)

        serverInfo = res_0['result']['serverInfo']
        serverstar = serverInfo['serverBookmarkCount']
        guid = serverInfo['guid']
        servername = serverInfo['name']
        servermode = serverInfo['mapModePretty']
        servermap = serverInfo['mapNamePretty']
        serveramount = serverInfo['slots']['Soldier']['current']
        serverspect = serverInfo['slots']['Spectator']['current']
        serverque = serverInfo['slots']['Queue']['current']
        servermaxamount = serverInfo['slots']['Soldier']['max']

        personaIds = [ownerid]
        res1 = await upd_getPersonasByIds(remid, sid, sessionID, personaIds)
        userName = res1['result'][f'{ownerid}']['displayName']
    except RSPException as rsp_exc:
        await BF1_GAMEID_INFO.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_GAMEID_INFO.finish(MessageSegment.reply(event.message_id) + "未查询到数据\n" \
                                + traceback.format_exception_only(e))
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
        await BF1_EX.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_EX.finish(MessageSegment.reply(event.message_id) + '未查询到数据\n' + traceback.format_exception_only(e))

@BF1_DRAW.handle()
async def bf1_draw_server_array(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split()
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    _, server_id = await check_server_id(groupqq,arg[0])
    gameId = await get_gameid_from_serverid(server_id)
        
        # server_array = await request_GT_API(GAME,'serverarray', {'gameid': GameId, 'days': days})
    try:
        img = draw_server_array2(str(gameId))
        await BF1_DRAW.send(MessageSegment.reply(event.message_id) + MessageSegment.image(img))
    except RSPException as rsp_exc:
        await BF1_DRAW.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_DRAW.finish(MessageSegment.reply(event.message_id) + '未知数据错误\n' + traceback.format_exception_only(e))


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
            await BF1_ADMINDRAW.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_ADMINDRAW.finish(MessageSegment.reply(event.message_id) + '未知数据错误\n' + traceback.format_exception_only(e))

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
        try:
            res = await upd_servers(remid, sid, sessionID, serverName)
            if len(res['result']['gameservers']) == 0:
                await BF1_F.send(MessageSegment.reply(event.message_id) + f'未查询到包含{serverName}关键字的服务器')
            else:
                file_dir = await asyncio.wait_for(draw_server(remid, sid, sessionID, serverName,res), timeout=15)
                await BF1_F.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        except RSPException as rsp_exc:
            await BF1_F.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_F.finish(MessageSegment.reply(event.message_id) + '未查询到数据\n' + traceback.format_exception_only(e))
    if mode == 2:
        groupqq = await check_session(event.group_id)
        if not groupqq:
            raise Exception('本群组未初始化')
        servers = await get_server_num(groupqq)
        gameids = []
        server_inds = []

        for server_ind, server_id in servers:
            gameid = await get_gameid_from_serverid(server_id)
            if gameid:
                server_inds.append(server_ind)
                gameids.append(gameid)
        try:
            file_dir = await asyncio.wait_for(draw_f(server_inds,gameids,groupqq,remid, sid, sessionID), timeout=15)
            await BF1_F.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
        except RSPException as rsp_exc:
            await BF1_F.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_F.finish(MessageSegment.reply(event.message_id) + '未查询到数据\n' + traceback.format_exception_only(e))

@BF1_FADMIN.handle()
async def bf1_fadmin(event:GroupMessageEvent, state:T_State):
    if not check_sudo(event.group_id, event.user_id):
        return

    message = _command_arg(state) or event.get_message()
    serverName = message.extract_plain_text()
    serverName = html.unescape(serverName)
    remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]

    try:
        res_search = await upd_servers(remid, sid, sessionID, serverName)
        res_servers = res_search['result']['gameservers']
        server_fullname = res_servers[0]['name']
        gameId = res_servers[0]['gameId']
        res = await upd_detailedServer(remid, sid, sessionID, gameId)
        adminlist = (i['displayName'] for i in res['result']['rspInfo']['adminList'])
    except RSPException as rsp_exc:
        await BF1_FADMIN.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_FADMIN.finish(MessageSegment.reply(event.message_id) + "未查询到数据\n" \
                                + traceback.format_exception_only(e))
    else:
        await BF1_FADMIN.send(MessageSegment.reply(event.message_id) + server_fullname + '\n' + '\n'.join(adminlist))

@BF1_F_RET_TXT.handle()
async def bf1_findserver_return_text(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    serverName = message.extract_plain_text()
    serverName = html.unescape(serverName)
    remid, sid, sessionID = (await get_one_random_bf1admin())[0:3]

    try:
        res_search = await upd_servers(remid, sid, sessionID, serverName)
        if len(res_search['result']['gameservers']) == 0:
            await BF1_F_RET_TXT.send(MessageSegment.reply(event.message_id) + f'未查询到包含{serverName}关键字的服务器')
        else:
            msg = '\n=================\n'.join([server['name'] for server in res_search['result']['gameservers']])
            await BF1_F_RET_TXT.send(MessageSegment.reply(event.message_id) + msg)
    except RSPException as rsp_exc:
        await BF1_F_RET_TXT.finish(MessageSegment.reply(event.message_id) + rsp_exc.echo())
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_F_RET_TXT.finish(MessageSegment.reply(event.message_id) + "未查询到数据\n" \
                                + traceback.format_exception_only(e))