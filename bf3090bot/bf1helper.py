import asyncio
import logging
import json
import datetime
import traceback
from random import randint

from nonebot.adapters import Event
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import (
    Bot, GroupMessageEvent, GroupDecreaseNoticeEvent, GroupIncreaseNoticeEvent, GroupRequestEvent
)
from typing import Tuple, List
from sqlalchemy.future import select
from sqlalchemy import func, or_

from .bf1rsp import *
from .rdb import *
from .redis_helper import redis_client
from .utils import (
    BF1_SERVERS_DATA, SUPERUSERS, SUDOGROUPS,
    request_GT_API
)

GAME = 'bf1'
LANG = 'zh-tw'

async def token_helper():
    async with async_db_session() as session:
        # Fetch admins from db
        admins = [row[0] for row in (await session.execute(select(Bf1Admins))).all()]
        tasks_token = [asyncio.create_task(upd_token(admin.remid, admin.sid)) for admin in admins]
        list_cookies_tokens = await asyncio.gather(*tasks_token, return_exceptions=True) # Update tokens
        for i, lct in enumerate(list_cookies_tokens):
            if not isinstance(lct, Exception):
                admins[i].remid, admins[i].sid, admins[i].token = lct
        session.add_all(admins) # Write into db
        await session.commit()
        logger.info('Token updates complete')

async def session_helper():
    async with async_db_session() as session:
        admins = [row[0] for row in (await session.execute(select(Bf1Admins))).all()]
        tasks_session = [
            asyncio.create_task(upd_sessionId(admin.remid, admin.sid)) for admin in admins
        ]
        list_cookies_sessionIDs = await asyncio.gather(*tasks_session, return_exceptions=True)
        logger.debug('\n'.join([str(t) if isinstance(t, Exception) else t[2] for t in list_cookies_sessionIDs]))

        for i, lcs in enumerate(list_cookies_sessionIDs):
            if not isinstance(lcs, Exception):
                admins[i].remid, admins[i].sid, admins[i].sessionid = lcs
        session.add_all(admins)
        await session.commit()
        logger.info('SessionID updates complete')

async def get_one_random_bf1admin() -> Tuple[str, str, str, str]:
    async with async_db_session() as session:
        admin = (await session.execute(select(Bf1Admins).order_by(func.random()).limit(1))).one()[0]
    return admin.remid, admin.sid, admin.sessionid, admin.token

async def get_bf1admin_by_serverid(serverid: int, gameid : int = 0) -> Tuple[str, str, str, str] | None:
    async with async_db_session() as session:
        server_admin = (await session.execute(select(ServerBf1Admins).filter_by(serverid=serverid))).first()
        if server_admin:
            admin_pid = server_admin[0].pid
            admin = (await session.execute(select(Bf1Admins).filter_by(pid=admin_pid))).first()
            return admin[0].remid, admin[0].sid, admin[0].sessionid, admin[0].token
        else:
            if gameid:
                remid, sid, sessionID, access_token = await get_one_random_bf1admin()
                res = await upd_detailedServer(remid, sid, sessionID, gameid)
                server = res["result"]
                rspInfo = server.get("rspInfo", {})
                if not rspInfo:
                    return None, None, None, None
                else:
                    rsp_admins = (await session.execute(select(Bf1Admins))).all()
                    rsp_pids = [r[0].pid for r in rsp_admins]
                    server_adminList = rspInfo.get("adminList", [])
                    admin_pid = 0

                    for server_admin in server_adminList:
                        if int(server_admin["personaId"]) in rsp_pids:
                            admin_pid = int(server_admin["personaId"])
                            continue
                    
                    if admin_pid:
                        admin = (await session.execute(select(Bf1Admins).filter_by(pid=admin_pid))).first()
                        session.add(ServerBf1Admins(
                            serverid = serverid, pid = admin_pid
                        ))
                        await session.commit()
                        return admin[0].remid, admin[0].sid, admin[0].sessionid, admin[0].token
                    else:
                        return None, None, None, None
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
    
async def check_session(groupqq: int) -> int | None:
    async with async_db_session() as session:
        group_rec = (await session.execute(select(ChatGroups).filter_by(groupqq=int(groupqq)))).first()
    return int(group_rec[0].bind_to_group) if group_rec else None

async def check_server_id(groupqq: int, server_ind: str) -> Tuple[str, int] | Tuple[None, None]:
    """
    Return the true server_ind, serverid from group server alias
    """
    if not groupqq:
        return None, None
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
        logger.warning(f'gameid for {serverid} not find!')

async def upd_cache_StatsByPersonaId(remid, sid, sessionid, personaId):
    """
    Get players stats by pid, then store it in Redis (only those needed for playerlist)
    """
    res = await upd_StatsByPersonaId(remid, sid, sessionid, personaId)
    try:
        stt = res["result"]
        await redis_client.set(
            f'pstats:{personaId}',
            json.dumps({
                'win': stt['basicStats']['wins'],
                'loss': stt['basicStats']['losses'],
                'acc': stt['accuracyRatio'],
                'hs': stt['headShots'],
                'kd': stt['kdr'], 
                'k': stt['basicStats']['kills'],
                'kpm': stt["basicStats"]["kpm"],
                'spm': stt['basicStats']['spm'],
                'secondsPlayed': stt["basicStats"]["timePlayed"]}),
            ex=3600 + randint(0, 600)
        )
    except:
        logger.warning(traceback.format_exc())
    return res

async def read_or_get_StatsByPersonaId(remid, sid, sessionid, personaId):
    """
    Get playerlist stats (by pid) from Redis, if not found call upd_cache_StatsByPersonaId
    """
    stats = await redis_client.get(f'pstats:{personaId}')
    if stats is None:
        stt = (await upd_cache_StatsByPersonaId(remid, sid, sessionid, personaId))['result']
        return {
            'win': stt['basicStats']['wins'],
            'loss': stt['basicStats']['losses'],
            'acc': stt['accuracyRatio'],
            'hs': stt['headShots'],
            'kd': stt['kdr'], 
            'k': stt['basicStats']['kills'],
            'kpm': stt["basicStats"]["kpm"],
            'spm': stt['basicStats']['spm'],
            'secondsPlayed': stt["basicStats"]["timePlayed"]
        }
    else:
        return json.loads(stats)


async def add_vban(personaId: int, groupqq: int, serverId: int, reason: str, user_id: int):
    """
    Update: vban now records serverid(from Battlefield) instead group server code(1, 2, 3, etc.)
    """
    async with async_db_session() as session:
        async with session.begin():
            stmt = select(ServerVBans).filter_by(pid=int(personaId), serverid=int(serverId)).with_for_update(read=True)
            exist_vban = (await session.execute(stmt)).first()
            if not exist_vban:
                session.add(ServerVBans(
                    pid = int(personaId), serverid = int(serverId),
                    time = datetime.datetime.now(), reason = reason,
                    processor = user_id, notify_group = groupqq
                ))
            else:
                exist_vban[0].reason = str(reason)
                exist_vban[0].processor = int(user_id)
                exist_vban[0].time = datetime.datetime.now()
                session.add(exist_vban[0])
            await session.commit()

async def del_vban(personaId: int, serverId: int):
    """
    Update: vban now records serverid(from Battlefield) instead group server code(1, 2, 3)
    """
    async with async_db_session() as session:
        async with session.begin():
            stmt = select(ServerVBans).filter_by(pid=int(personaId), serverid=int(serverId)).with_for_update(read=True)
            vban_rec = (await session.execute(stmt)).first()
            if vban_rec:
                await session.delete(vban_rec[0])
                await session.commit()

async def search_vban(personaId):
    with open(BF1_SERVERS_DATA/'info.json','r',encoding='UTF-8') as f:
        info = json.load(f)
    
    reason = []
    name = []

    async with async_db_session() as session:
        vban_rows = (await session.execute(select(ServerVBans).filter_by(pid=int(personaId)))).all()
        for vban_row in vban_rows:
            reason.append(vban_row[0].reason)
            serverId = vban_row[0].serverid
            try:
                name.append(info[f"{serverId}"]["server_name"])
            except:
                name.append(f"serverId:{serverId}")
    num = len(name)
    return num,name,reason

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
    if not groupqq:
        ret_dict['err'] = '该群组未初始化'
        return ret_dict
    if mode == 1:
        try:
            personaId,userName,pidid = await getPersonasByName(access_token, playerName)
        except RSPException as rsp_exc:
            ret_dict['err'] = rsp_exc.echo()
            return ret_dict
        except:
            logger.warning(traceback.format_exc())
            ret_dict['err'] = '无效id'
            return ret_dict
    if mode == 2:
        async with async_db_session() as session:
            gm = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq, qq=user_id))).first()
            player = (await session.execute(select(Players).filter_by(qq=user_id))).first()
            if gm:
                personaId = gm[0].pid
                try:
                    res = await upd_getPersonasByIds(remid, sid, sessionID, [personaId])
                except Exception as e:
                    ret_dict['err'] = e.echo() if isinstance(e, RSPException) else str(e)
                    return ret_dict
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
                except Exception as e:
                    ret_dict['err'] = f'您还未绑定，尝试绑定{usercard}失败\n请使用.bind加游戏用户名手动绑定\n' + \
                        (e.echo() if isinstance(e, RSPException) else str(e))
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
    return await request_GT_API(game,'status',{"platform":"pc"})

async def get_player_id(player_name:str)->dict:
    return await request_GT_API(GAME,'player',{'name':player_name})

async def get_pl(gameID:str)->dict:
    response = await httpx_client.get(
        url="https://api.gametools.network/bf1/players",
        params = {
            "gameid": f"{gameID}"
	    }
    )
    return response.json()

async def get_player_data(player_name:str)->dict:
    return await request_GT_API(GAME,'all',{'name':player_name,'lang':LANG})

async def get_player_databyID(personaId)->dict:
    return await request_GT_API(GAME,'all',{'playerid':personaId,'lang':LANG})

async def get_server_data(server_name:str)->dict:
    return await request_GT_API(GAME,'servers',{'name':server_name,'lang':LANG,"platform":"pc","limit":20})

async def get_detailedServer_data(server_name:str)->dict:
    return await request_GT_API(GAME,'detailedserver',{'name':server_name})

async def get_detailedServer_databyid(server_name)->dict:
    return await request_GT_API(GAME,'detailedserver',{'gameid':server_name})

async def _is_del_user(event: Event) -> bool:
    return isinstance(event, GroupDecreaseNoticeEvent)

async def _is_get_user(event: Event) -> bool:
    return isinstance(event, GroupIncreaseNoticeEvent)

async def _is_add_user(event: Event) -> bool:
    return isinstance(event, GroupRequestEvent)

async def getbotforAps(bots,session:int) -> Bot | None:
    ret_bot = None
    for bot in bots.values():
        botlist = await bot.get_group_list()
        for i in botlist:
            if int(i["group_id"]) == session:
                ret_bot = bot
                break
        if ret_bot:
            break
    return ret_bot
    
async def load_alarm_session_from_db():
    async with async_db_session() as session:
        stmt = select(ChatGroups).filter_by(alarm=True)
        alarm_groups = [int(r[0].groupqq) for r in (await session.execute(stmt)).all()]
        if len(alarm_groups):
            await redis_client.sadd("alarmsession", *alarm_groups)
        return alarm_groups

async def search_all(personaId):

    with open(BF1_SERVERS_DATA/'vip.json','r',encoding='UTF-8') as f:
        vip_dict = json.load(f)
    with open(BF1_SERVERS_DATA/'ban.json','r',encoding='UTF-8') as f:
        ban_dict = json.load(f)
    with open(BF1_SERVERS_DATA/'admin.json','r',encoding='UTF-8') as f:
        admin_dict = json.load(f)
    with open(BF1_SERVERS_DATA/'owner.json','r',encoding='UTF-8') as f:
        owner_dict = json.load(f)
    
    num,name,reason = await search_vban(personaId)

    owner = 0
    ban = num
    admin = 0
    vip = 0

    for i in owner_dict.values():
        for dict in i:
            if int(dict["personaId"]) == personaId:
                owner+=1
    for i in ban_dict.values():
        for dict in i:
            if int(dict["personaId"]) == personaId:
                ban+=1
    for i in admin_dict.values():
        for dict in i:
            if int(dict["personaId"]) == personaId:
                admin+=1
    for i in vip_dict.values():
        for dict in i:
            if int(dict["personaId"]) == personaId:
                vip+=1
    return owner,ban,admin,vip

def search_a(personaId,mode):
    num = 0
    serverIds = []
    name = []

    if mode == 'v':
        with open(BF1_SERVERS_DATA/'vip.json','r',encoding='UTF-8') as f:
            res = json.load(f)
    elif mode == 'b':
        with open(BF1_SERVERS_DATA/'ban.json','r',encoding='UTF-8') as f:
            res = json.load(f)
    elif mode == 'a':
        with open(BF1_SERVERS_DATA/'admin.json','r',encoding='UTF-8') as f:
            res = json.load(f)
    elif mode == 'o':
        with open(BF1_SERVERS_DATA/'owner.json','r',encoding='UTF-8') as f:
            res = json.load(f)
    else:
        return num,name
    
    with open(BF1_SERVERS_DATA/'info.json','r',encoding='UTF-8') as f:
        info = json.load(f)

    for key,value in res.items():
        for dict in value:
            if int(dict["personaId"]) == personaId:
                num+=1
                serverIds.append(key)
    
    for serverId in serverIds:
        name.append(info[f"{serverId}"]["server_name"])
    return num,name

async def update_diff(remid, sid, sessionID, pid):
    newdiff = {}
    async with async_db_session() as session:
        async with session.begin():
            stmt_stat = select(playerStats).filter_by(pid=int(pid)).with_for_update(read=True)
            exist_stat = (await session.execute(stmt_stat)).first()
            
            stmt_diff = select(playerStatsDiff).filter_by(pid=int(pid)).with_for_update(read=True)
            exist_diff = (await session.execute(stmt_diff)).first()
            
            res_stat = await upd_StatsByPersonaId(remid, sid, sessionID, pid)
            win = res_stat['result']['basicStats']['wins']
            loss = res_stat['result']['basicStats']['losses']
            acc = res_stat['result']['accuracyRatio']
            hs = res_stat['result']['headShots']
            secondsPlayed = res_stat['result']['basicStats']['timePlayed']
            k = res_stat['result']['basicStats']['kills']
            d = res_stat['result']['basicStats']['deaths']
            rounds = res_stat['result']["roundsPlayed"]
            spm = res_stat['result']['basicStats']['spm']
            score = 0         
            
            results = await blaze_stat_renew([pid])
            stat_list = results[str(pid)]
            shot = int(float(stat_list[3]))
            hit = int(float(stat_list[4]))

            if not exist_stat:
                session.add(playerStats(
                    pid = int(pid), kills = k, deaths = d, playtimes = secondsPlayed,
                    wins = win, losses = loss, rounds = rounds, headshots = hs,
                    updatetime = datetime.datetime.timestamp(datetime.datetime.now()),
                    acc = acc, score = score, shot = shot, hit = hit
                ))
            else:
                oldtime = exist_stat[0].playtimes
                if oldtime < secondsPlayed:
                    killsdiff = k - exist_stat[0].kills
                    deathsdiff = d - exist_stat[0].deaths
                    winsdiff =  win - exist_stat[0].wins
                    lossesdiff = loss - exist_stat[0].losses
                    timediff = secondsPlayed - oldtime
                    hsdiff = hs - exist_stat[0].headshots
                    roundsdiff = rounds - exist_stat[0].rounds
                    scorediff = score - exist_stat[0].score
                    shotdiff = shot - exist_stat[0].shot
                    hitdiff = hit - exist_stat[0].hit
                    updatetime_old = exist_stat[0].updatetime
                    updatetime_new = int(datetime.datetime.timestamp(datetime.datetime.now()))

                    differ = {
                        "k" : killsdiff,
                        "d" : deathsdiff,
                        "w" : winsdiff,
                        "l" : lossesdiff,
                        "time" : timediff,
                        "hs" : hsdiff,
                        "round" : roundsdiff,
                        "score" : scorediff,
                        "shot" : shotdiff,
                        "hit" : hitdiff,
                        "oldtime" : updatetime_old,
                        "newtime" : updatetime_new
                    }
                    if exist_diff:
                        olddiff = exist_diff[0].diff
                        if len(olddiff) == 5:
                            newdiff = {
                                "1": olddiff["2"],
                                "2": olddiff["3"],
                                "3": olddiff["4"],
                                "4": olddiff["5"],
                                "5": differ
                            }
                        else:
                            for i in range(len(olddiff)):
                                newdiff[f"{i+1}"] = olddiff[f"{i+1}"]
                            newdiff[f"{len(olddiff)+1}"] = differ 
                        exist_diff[0].diff = newdiff
                        session.add(exist_diff[0])
                    else:
                        newdiff = {
                            "1": differ
                        }
                        session.add(playerStatsDiff(
                            pid = int(pid), diff = newdiff
                        ))
                else:
                    if exist_diff:
                        newdiff = exist_diff[0].diff 
                
                exist_stat[0].kills = k
                exist_stat[0].deaths = d
                exist_stat[0].playtimes = secondsPlayed
                exist_stat[0].wins = win
                exist_stat[0].losses = loss
                exist_stat[0].rounds = rounds
                exist_stat[0].headshots = hs
                exist_stat[0].updatetime = int(datetime.datetime.timestamp(datetime.datetime.now()))
                exist_stat[0].acc = acc
                exist_stat[0].score = score
                exist_stat[0].shot = shot
                exist_stat[0].hit = hit
                session.add(exist_stat[0])

            await session.commit() 

    return newdiff,res_stat

async def get_group_stats(groupqq):
    async with async_db_session() as session:
        member_row = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq))).all()
        personaIds = [r[0].pid for r in member_row]
        
        stats = []
        stmt_stat = select(playerStats).filter(playerStats.pid.in_(personaIds)).with_for_update(read=True)
        exist_stat = (await session.execute(stmt_stat)).all()
    
        if exist_stat:
            for r in exist_stat:
                if r[0].rounds > 10:
                    stat = {
                        "pid": r[0].pid,
                        "kills": r[0].kills,
                        "deaths": r[0].deaths,
                        "wins": r[0].wins,
                        "losses": r[0].losses,
                        "headshots": r[0].headshots,
                        "playtimes": r[0].playtimes,
                        "rounds": r[0].rounds,
                        "acc": r[0].acc,
                        "score": r[0].score,
                        'kd': round(r[0].kills / r[0].deaths if r[0].deaths != 0 else r[0].kills, 2),
                        'kpm': round(r[0].kills * 60 / r[0].playtimes if r[0].playtimes != 0 else 0, 2),
                        'winloss': r[0].wins / r[0].rounds if r[0].rounds != 0 else 0,
                        'hs': r[0].headshots / r[0].kills if r[0].kills != 0 else 0
                    }
                stats.append(stat)

    return stats

__all__ =[
    'token_helper', 'session_helper',
    'get_one_random_bf1admin', 'get_bf1admin_by_serverid',
    'reply_message_id',
    'admin_logging_helper',
    'check_admin', 'check_sudo',
    'check_session', 'check_server_id',
    'get_gameid_from_serverid',
    'upd_cache_StatsByPersonaId', 'read_or_get_StatsByPersonaId',
    'get_user_pid',
    'add_vban', 'del_vban', 'search_vban',
    'search_a', 'search_all', 'update_diff', 'get_group_stats',
    'get_server_num',
    'update_or_bind_player_name',
    '_is_del_user', '_is_get_user', '_is_add_user',
    'get_bf1status',
    'getbotforAps',
    'load_alarm_session_from_db',
    # Depreacated
    'get_player_id', 'get_pl', 'get_player_data', 'get_player_databyID',
    'get_server_data', 'get_detailedServer_data', 'get_detailedServer_databyid'
]