import asyncio
import logging
import json
import datetime
import traceback
from random import randint

from nonebot.adapters import Event
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent, GroupDecreaseNoticeEvent, GroupIncreaseNoticeEvent, GroupRequestEvent
)
from typing import Tuple, List
from sqlalchemy.future import select
from sqlalchemy import func, or_

from .bf1rsp import *
from .rdb import *
from .redis_helper import redis_client
from .utils import (
    BF1_SERVERS_DATA, SUPERUSERS, SUDOGROUPS,
    request_API
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
    stats = redis_client.get(f'pstats:{personaId}')
    if stats is None:
        stt = (await upd_cache_StatsByPersonaId(remid, sid, sessionid, personaId))['result']
        return {
            'win': stt['basicStats']['wins'],
            'loss': stt['basicStats']['losses'],
            'acc': stt['accuracyRatio'],
            'hs': stt['headShots'],
            'kd': stt['kdr'], 
            'k': stt['basicStats']['kills'],
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

async def search_vban(personaId):
    with open(BF1_SERVERS_DATA/'info.json','r',encoding='UTF-8') as f:
        info = json.load(f)
    
    reason = []
    name = []

    async with async_db_session() as session:
        vban_rows = (await session.execute(select(ServerVBans).filter_by(pid=personaId))).all()
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
                    ret_dict['err'] = f'您还未绑定，尝试绑定{usercard}失败\n' + \
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
    return await request_API(game,'status',{"platform":"pc"})

async def get_player_id(player_name:str)->dict:
    return await request_API(GAME,'player',{'name':player_name})

async def get_pl(gameID:str)->dict:
    response = await httpx_client.get(
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
    'search_a', 'search_all',
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