from nonebot.log import logger
from nonebot.params import _command_arg, ShellCommandArgs
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent, ActionFailed
from nonebot.typing import T_State
from nonebot.exception import ParserExit
from nonebot.rule import Namespace
from typing import Annotated

import traceback
import json
import re
import asyncio
from sqlalchemy.future import select

from ..utils import PREFIX, get_wp_info
from ..bf1rsp import *
from ..bf1draw import *
from ..secret import *
from ..rdb import *
from ..redis_helper import redis_client
from ..bf1helper import *

from .matcher import (
    BF1_BIND_PID,BF1_SA,BF1_TYC,BF1_PID_INFO,
    BF1_WP,BF1_S,BF1_R,BF1_RE,BF1_RANK
)

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
    except RSPException as rsp_exc:
        await BF1_BIND_PID.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_BIND_PID.finish(MessageSegment.reply(event.message_id) + traceback.format_exception_only(e))
    
    async with async_db_session() as session:
        stmt_gm = select(GroupMembers).filter_by(groupqq=groupqq, qq=user_id).with_for_update(read=True)
        gm = (await session.execute(stmt_gm)).first()
        if gm:
            gm[0].pid = personaId
        else:
            session.add(GroupMembers(pid=personaId, groupqq=groupqq, qq=user_id))
        await session.commit()
        stmt_p = select(Players).filter_by(qq=user_id).with_for_update(read=True)
        player = (await session.execute(stmt_p)).first()
        if player:
            player[0].originid = userName
            player[0].pid = personaId
        else:
            session.add(Players(pid=personaId, originid=userName, qq=user_id))
        await session.commit()                          
    
    await BF1_BIND_PID.send(MessageSegment.reply(event.message_id) + f'已绑定: {userName}')

@BF1_PID_INFO.handle()
async def bf1_pid_info(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    pid_str = message.extract_plain_text()
    if not pid_str.isdigit():
        await BF1_PID_INFO.finish(MessageSegment.reply(event.message_id) + '请输入数字pid而非EAID')
    personaId = int(pid_str)
    try:
        remid, sid, sessionID, _ = await get_one_random_bf1admin()
        res1 = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
        userName = res1['result'][f'{personaId}']['displayName']
        pidid = res1['result'][f'{personaId}']['platformId']
        await BF1_PID_INFO.send(MessageSegment.reply(event.message_id) + f'玩家ID: {userName}\nPid: {personaId}\nUid: {pidid}')
    except RSPException as rsp_exc:
        await BF1_PID_INFO.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_PID_INFO.finish(MessageSegment.reply(event.message_id) + traceback.format_exception_only(e))

@BF1_SA.handle()
async def bf1_sa(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split()
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
        num,name,reason = await search_vban(personaId)
    else:
        num,name = search_a(personaId,searchmode)
        reason = []
    search_modes = {'o': '', 'a': '的管理', 'v': '的vip', 'b':'的封禁位', 'vban': '的虚拟封禁位'}
    if searchmode in search_modes:
        msg_title = f'玩家{userName}共拥有{num}个服务器' + search_modes[searchmode] + (':' if num else '')
        print(type(msg_title))
        await BF1_SA.send(msg_title)
        if num:
            file_dir = await draw_a(num,name,reason,personaId)
            await BF1_SA.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))

@BF1_TYC.handle()
async def bf1_tyc(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split()
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
            await BF1_TYC.send(MessageSegment.reply(event.message_id) + '回复消息错误或已过期')
            return
        pl_json = json.loads(redis_pl)
        for i in pl_json['pl']:
            if int(i['slot']) == int(arg[0]):
                personaId = i['id']
                break
        try:
            res1 = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
            userName = res1['result'][f'{personaId}']['displayName']
            pidid = res1['result'][f'{personaId}']['platformId']
        except RSPException as rsp_exc:
            await BF1_TYC.send(MessageSegment.reply(event.message_id) + '获取玩家id失败\n' + rsp_exc.echo())
            return
        except Exception as e:
            logger.warning(traceback.format_exc())
            await BF1_TYC.finish(MessageSegment.reply(event.message_id) + '获取玩家id失败\n' + traceback.format_exception_only(e))
            
    msg = await tyc(remid,sid,sessionID,personaId,userName,pidid)
    await BF1_TYC.send(MessageSegment.reply(event.message_id) + msg)

@BF1_S.handle()
async def bf1_statimage(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split()
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
            try:
                res1 = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
                userName = res1['result'][f'{personaId}']['displayName']
            except RSPException as rsp_exc:
                await BF1_S.send(MessageSegment.reply(event.message_id) + '获取玩家id失败\n' + rsp_exc.echo())
                return
            except Exception as e:
                logger.warning(traceback.format_exc())
                await BF1_S.finish(MessageSegment.reply(event.message_id) + '获取玩家id失败\n' + traceback.format_exception_only(e))
        else:
            await BF1_S.finish(MessageSegment.reply(event.message_id)+'请选择正确的玩家序号')
    try:
        file_dir = await asyncio.wait_for(draw_stat(remid, sid, sessionID, personaId, userName), timeout=15)
        await BF1_S.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except asyncio.TimeoutError:
        await BF1_S.send(MessageSegment.reply(event.message_id) + '连接超时')
    except RSPException as rsp_exc:
        await BF1_S.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except ActionFailed as nb_e:
        await BF1_S.send(MessageSegment.reply(event.message_id) + 'Nonebot前端出错，可能导致图片发送失败')
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_S.finish(MessageSegment.reply(event.message_id) + '获取玩家信息失败\n' + traceback.format_exception_only(e))

@BF1_WP.handle()
async def bf1_wp_wrongargs(event:GroupMessageEvent,
                           args: Annotated[ParserExit, ShellCommandArgs()]):
    if args.status == 0:
        if reply_message_id(event) == None:
            help_msg = '.w [类型] [EAID] [?行?列] [-n 武器名称搜索]\n' +\
            '类型，支持精英兵/配备/半自动/佩枪/手枪/机枪/轻机枪/近战/刀' +\
            '/霰弹枪/霰弹/步枪/狙击枪/手榴弹/驾驶员/制式步枪/冲锋枪/突击兵/侦察兵/支援兵/医疗兵/载具\n' +\
            'EAID不填则查询自己\n' +\
            '行列数选填，需为2-7的整数'
        else:
            help_msg = '回复pl武器查询模式：\n' +\
            '.w [类型] pl中玩家序号 [?行?列] [-n 武器名称搜索]\n' +\
            '类型，支持精英兵/配备/半自动/佩枪/手枪/机枪/轻机枪/近战/刀' +\
            '/霰弹枪/霰弹/步枪/狙击枪/手榴弹/驾驶员/制式步枪/冲锋枪/突击兵/侦察兵/支援兵/医疗兵/载具\n' +\
            '行列数选填，需为2-7的整数'
        await BF1_WP.finish(MessageSegment.reply(event.message_id) + help_msg)
    else:
        await BF1_WP.finish(MessageSegment.reply(event.message_id) + '参数格式错误，请使用.w -h查看帮助')

@BF1_WP.handle()
async def bf1_wp(event:GroupMessageEvent, state:T_State,
                 args: Annotated[Namespace, ShellCommandArgs()]):
    groupqq = await check_session(event.group_id)
    usercard = event.sender.card
    user_id = event.user_id
    raw_args = args.raw_args
    search_keyword = args.search

    if len(args.raw_args) and (raw_args[-1].endswith("行") or raw_args[-1].endswith("列")):
        row_arg = re.findall(r'(\d+)行', raw_args[-1])
        row = int(row_arg[0]) if len(row_arg) else 4
        col_arg = re.findall(r'(\d+)列', raw_args[-1])
        col = int(col_arg[0]) if len(col_arg) else 4
        if row > 7 or col < 2 or col > 7:
            await BF1_WP.finish(MessageSegment.reply(event.message_id) + '行列数设置不合法，允许1-7行和2-7列')
        arg = raw_args[:-1]
    else:
        row = 5
        col = 2
        arg = raw_args

    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    if reply_message_id(event) == None:
        mode = 0
        playerName = None
        if len(arg) == 0:
            wpmode = 0
            mode = 2
        else:
            if len(arg) == 1:
                [playerName,wpmode,mode] = get_wp_info(arg[0],user_id)
            else:
                playerName = arg[1]
                mode = 1
                wpmode = get_wp_info(arg[0],user_id)[1]
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
        if len(arg) == 0:
            await BF1_WP.finish(MessageSegment.reply(event.message_id) + '回复pl时玩家序号必填')
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
        
        wpmode = get_wp_info(arg[0],user_id)[1]
    
    try:
        res1 = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
        userName = res1['result'][f'{personaId}']['displayName']
        file_dir = await asyncio.wait_for(draw_wp(remid, sid, sessionID, personaId, userName, wpmode, col, row, search_keyword), timeout=15)
        await BF1_WP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))
    except asyncio.TimeoutError:
        await BF1_WP.send(MessageSegment.reply(event.message_id) + '连接超时')
    except RSPException as rsp_exc:
        await BF1_WP.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except ActionFailed as nb_e:
        await BF1_WP.send(MessageSegment.reply(event.message_id) + 'Nonebot前端出错，可能导致图片发送失败')
        return
    except Exception as e:
        logger.error(traceback.format_exc())
        await BF1_WP.finish(MessageSegment.reply(event.message_id) + '获取玩家信息失败\n' + traceback.format_exception_only(e))

@BF1_R.handle()
async def bf1_recent(event:GroupMessageEvent, state:T_State):
    await BF1_R.send(MessageSegment.reply(event.message_id) + f'此功能暂时关闭')    
    return
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
    except RSPException as rsp_exc:
        await BF1_R.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except Exception as e:
        logger.warning(traceback.format_exc())
        await BF1_R.finish(MessageSegment.reply(event.message_id) + '获取玩家信息失败\n' + traceback.format_exception_only(e))

@BF1_RE.handle()
async def bf1_recent1(event:GroupMessageEvent, state:T_State):
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
            await BF1_RE.send(MessageSegment.reply(event.message_id) + "对局功能暂时关闭，暂时调整为最近战绩\n" + MessageSegment.image(file_dir))
        else:
            await BF1_RE.send(MessageSegment.reply(event.message_id) + "暂无有效对局信息\n已记录本次战绩\n请等待下次查询生效")
    except RSPException as rsp_exc:
        await BF1_RE.send(MessageSegment.reply(event.message_id) + rsp_exc.echo())
        return
    except ActionFailed as nb_e:
        await BF1_RE.send(MessageSegment.reply(event.message_id) + 'Nonebot前端出错，可能导致图片发送失败')
        return
    except Exception as e:
        logger.error(traceback.format_exc())
        await BF1_RE.finish(MessageSegment.reply(event.message_id) + '暂无有效对局信息\n已记录本次战绩\n请等待下次查询生效\n' + traceback.format_exception_only(e))

@BF1_RANK.handle()
async def bf1_rank(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    arg = message.extract_plain_text().split()
    groupqq = await check_session(event.group_id)
    user_id = event.user_id

    stats = await get_group_stats(groupqq)
    if stats == []:
        await BF1_RANK.finish(MessageSegment.reply(event.message_id) + '本群组暂无有效战绩信息')
    
    async with async_db_session() as session:
        gm = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq, qq=user_id))).first()
        if gm:
            personaId = gm[0].pid
    
    remid, sid, sessionID, access_token = await get_one_random_bf1admin()
    file_dir = await asyncio.wait_for(draw_rank(remid, sid, sessionID, arg, stats, personaId), timeout=35)
    if str(file_dir) != '0':
        await BF1_RANK.send(MessageSegment.reply(event.message_id) + f'群组{arg[0]}排名(场次>10)：\n战绩记录存在延迟，仅供参考\n' + MessageSegment.image(file_dir))
    else:
        await BF1_RANK.send(MessageSegment.reply(event.message_id) + "查询参数错误。可用参数：kd kpm 击杀 死亡 场次 胜率 acc 爆头率")
