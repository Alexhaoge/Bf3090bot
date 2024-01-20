import json
import aiohttp
import uuid
import datetime,time
from .utils import CURRENT_FOLDER
import httpx
import bs4
#import geoip2.database
from typing import Union

#reader = geoip2.database.Reader(CURRENT_FOLDER/"GeoLite2-City.mmdb")
httpx_client = httpx.AsyncClient()

async def getPersonasByName(access_token, player_name) -> tuple | Exception:
        """
        根据名字获取Personas
        :param player_name:
        :return:
        """
        url = f"https://gateway.ea.com/proxy/identity/personas?namespaceName=cem_ea_id&displayName={player_name}"
        # 头部信息
        head = {
            "Host": "gateway.ea.com",
            "Connection": "keep-alive",
            "Accept": "application/json",
            "X-Expand-Results": "true",
            "Authorization": f"Bearer {access_token}",
            "Accept-Encoding": "deflate"
        }
        try:
            response = await httpx_client.get(
                    url=url,
                    headers=head,
                    timeout=10,
                    ssl=False
                )
            res =  await response.json()
            id = res['personas']['persona'][0]['personaId']
            name = res['personas']['persona'][0]['displayName']
            pidid = res['personas']['persona'][0]['pidId']
            return id,name,pidid
        except KeyError:
            raise RSPException(error_code=-32856)

async def fetch_data(url,headers):
    response = await httpx_client.get(url=url,headers=headers,timeout=20)
    return response
    
async def post_data(url,json,headers):
    response = await httpx_client.post(url=url,json=json,headers=headers,timeout=20)
    return response.text
    
async def process_top_n(game: str, headers: dict, retry: int = 3):
    next_url = f"https://battlefieldtracker.com/{game}"
    for i in range(retry):
        try:
            game_req = await fetch_data(next_url,headers)
            soup = bs4.BeautifulSoup(game_req.text, 'html.parser')

            me = soup.select_one('.player.active')
            game_stat = {s.select_one('.name').text:s.select_one('.value').text for s in me.select('.quick-stats .stat')}
            break
        except AttributeError:
            continue
        except httpx.TimeoutException:
            continue
        except:
            return 'player not found'

    game_stat['Kills'] = int(game_stat['Kills'])
    game_stat['Deaths'] = int(game_stat['Deaths'])
    game_stat['kd'] = round(game_stat['Kills'] / game_stat['Deaths'] if game_stat['Deaths'] else game_stat['Kills'], 2)
    
    detail_general_card = me.findChild(name='h4', string='General').parent.parent
    game_stat['headshot'] = 0

    headshot_name_tag = detail_general_card.find_all(class_='name', string='Headshots')
    if len(headshot_name_tag):
        if len(headshot_name_tag) == 1:
            game_stat['headshot'] = int(headshot_name_tag[0].find_previous_sibling(class_='value').contents[0])
        else:
            game_stat['headshot'] = max(int(headshot_name_tag[0].find_previous_sibling(class_='value').contents[0]),int(headshot_name_tag[1].find_previous_sibling(class_='value').contents[0]))
    
    acc_name_tag = detail_general_card.findChild(class_='name', string='Accuracy')
    game_stat['acc'] = acc_name_tag.find_previous_sibling(class_='value').contents[0]

    duration_name_tag = detail_general_card.findChild(class_='name', string='Time Played')
    try:
        if duration_name_tag == None:
            game_stat['duration'] = '0s'
        else:
            game_stat['duration'] = duration_name_tag.find_previous_sibling(class_='value').contents[0].replace(' ','')
    except:
        game_stat['duration'] = '0s'
    
    team = me.findParents(class_="team")[0].select_one('.card-heading .card-title').contents[0]
    if team == 'No Team':
        game_stat['result'] = '未结算'
    else:
        team_win = soup.select('.card.match-attributes .stat .value')[1].contents[0]
        game_stat['result'] = '胜利' if team == team_win else '落败'

    map_info = soup.select_one('.match-header .activity-details')
    game_stat['map'] = map_info.select_one('.map-name').contents[0][0:-1]
    game_stat['mode'] = map_info.select_one('.type').contents[0]
    game_stat['server'] = map_info.select_one('.map-name small').contents[0]
    game_stat['matchDate'] = map_info.select_one('.date').contents[0]

    return game_stat    

async def BTR_get_recent_info(player_name: str) -> list[dict]:
    """
    从BTR获取最近的战绩
    :param player_name: 玩家名称
    :return: 返回一个列表，列表中的每个元素是一个字典，默认爬取全部数据，调用处决定取前几个
    """
    result = []
    # BTR玩家个人信息页面
    url = f"https://battlefieldtracker.com/bf1/profile/pc/{player_name}"
    header = {
        "Connection": "keep-alive",
        "User-Agent": "ProtoHttp 1.3/DS 15.1.2.1.0 (Windows)",
    }
    async with httpx_client.get(url, headers=header) as response:
        html = await response.text()
        # 处理网页获取失败的情况
        if not html:
            return None
        soup = bs4.BeautifulSoup(html, "html.parser")
        # 从<div class="card-body player-sessions">获取对局数量，如果找不到则返回None
        if not soup.select('div.card-body.player-sessions'):
            return None
        sessions = soup.select('div.card-body.player-sessions')[0].select('div.sessions')
        # 每个sessions由标题和对局数据组成，标题包含时间和胜率，对局数据包含spm、kdr、kpm、btr、gs、tp
        for item in sessions:
            time_item = item.select('div.title > div.time > h4 > span')[0]
            # 此时time_item =  <span data-livestamp="2023-03-22T14:00:00.000Z"></span>
            # 提取UTC时间转换为本地时间的时间戳
            time_item = time_item['data-livestamp']
            # 将时间戳转换为时间
            time_item = datetime.datetime.fromtimestamp(
                time.mktime(time.strptime(time_item, "%Y-%m-%dT%H:%M:%S.000Z")))+datetime.timedelta(hours=8)
            # 将时间转换为字符串
            time_item = time_item.strftime('%Y-%m-%d %H:%M')
            # 提取胜率
            win_rate = item.select('div.title > div.stat')[0].text
            # 提取spm、kdr、kpm、btr、gs、tp
            spm = item.select('div.session-stats > div:nth-child(1) > div:nth-child(1)')[0].text.strip()
            kd = item.select('div.session-stats > div:nth-child(2) > div:nth-child(1)')[0].text.strip()
            kpm = item.select('div.session-stats > div:nth-child(3) > div:nth-child(1)')[0].text.strip()
            score = item.select('div.session-stats > div:nth-child(5)')[0].text.strip().replace('Game Score', '')
            time_play = item.select('div.session-stats > div:nth-child(6)')[0].text.strip().replace('Time Played','')
            result.append({
                'time': time_item.strip(),
                'win_rate': win_rate.strip(),
                'spm': spm.strip(),
                'kd': kd.strip(),
                'kpm': kpm.strip(),
                'score': score.strip(),
                'time_play': time_play.strip()
            })
        return result

async def async_get_server_data(serverName):
    response = await httpx_client.get(
        url="https://api.gametools.network/bf1/servers",
        params={'name':serverName,
                'lang':'zh-tw',
                "platform":"pc",
                "limit":20}
    )
    return response.text

class RSPException(Exception):
    code_dict = {
        -32501: "Session失效",
        -32504: "连接超时",
        -32504: "EA服务器访问超时",
        -32601: "方法不存在",
        -32602: "参数缺失",
        -34501: "服务器已过期或不存在",
        -35150: "战队不存在",
        -35160: "无权限进行次操作",
        #-32603: "此code为多个错误共用,请查阅error_msg_dict",
        -32851: "服务器不存在/已过期",
        -32856: "玩家ID有误",
        -32857: "机器人无法处置管理员",
        -32858: "服务器未开启"  
    }

    def __init__(self, msg: str = None, error_code: int = None, request_error: bool = False, *args, **kwargs):
        self.msg = msg
        self.code = error_code
        self.request_error = request_error
        super(RSPException, self).__init__(*args, **kwargs)
    
    def __str__(self):
        return f"{self.code}:{self.msg}"
    
    def echo(self) -> str:
        if self.request_error:
            if self.code:
                return f"网络错误({self.code}):{self.msg}"
            else:
                return f"网络错误:{self.msg}"
        elif int(self.code) in RSPException.code_dict.keys():
            return RSPException.code_dict[self.code]
        else:
            msg_lower = self.msg.lower()
            if "session expired" in msg_lower or "no varlid session" in msg_lower:
                return f"服管账号的SessionID失效，请联系管理员刷新"
            elif 'internal error' in msg_lower:
                return "EA后端错误"
            elif "severnotrestartableexception" in msg_lower:
                return "服务器未开启"
            elif "org.apache.thrift.tapplicationexception" in msg_lower:
                return "机器人无权限操作"
            elif "rsperruserisalreadyvip" in msg_lower:
                return "玩家已是vip"
            elif "rsperrservervipmax" in msg_lower:
                return "服务器VIP位已满"
            elif "rsperrserverbanmax" in msg_lower:
                return "服务器Ban位已满"
            elif "rsperrinvalidmaprotationid" in msg_lower:
                return "无效地图轮换"
            elif "invalidlevelindexexception" in msg_lower:
                return "图池索引错误"
            elif "invalidserveridexception" in msg_lower:
                return "服务器ServerId错误"
            else:
                return f"未知错误{self.__str__()}"

def upd_remid_sid(res: httpx.Response, remid, sid):
    res_cookies = httpx.Cookies.extract_cookies(res.cookies,res)
    res_cookies = json.dumps(res_cookies)
    if 'sid' in res_cookies:
        sid = res_cookies['sid']
    if 'remid' in res_cookies:
        remid = res_cookies['remid']
    return remid, sid

async def upd_token(remid, sid):
    res_access_token = await httpx_client.get(
        url="https://accounts.ea.com/connect/auth",
        params= {
            'client_id': 'ORIGIN_JS_SDK',
            'response_type': 'token',
            'redirect_uri': 'nucleus:rest',
            'prompt': 'none',
            'release_type': 'prod'
        },
        headers= {
        'Cookie': f'remid={remid};sid={sid}',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36',
            'content-type': 'application/json'
        }
    )

    access_token = res_access_token.json()['access_token']
    remid, sid = upd_remid_sid(res_access_token, remid, sid)
    return remid, sid, access_token

async def upd_sessionId(remid, sid):
    res_authcode = await httpx_client.get(       
        url="https://accounts.ea.com/connect/auth",
        params= {
            'client_id': 'sparta-backend-as-user-pc',
            'response_type': 'code',
            'release_type': 'none'
        },
        headers= {
            'Cookie': f'remid={remid};sid={sid}'
        },
        follow_redirects=False
    )
    # 这个请求默认会重定向，所以要禁用重定向，并且重定向地址里的code参数就是我们想要的authcode
    authcode = str.split(res_authcode.headers.get("location"), "=")[1]
    remid, sid = upd_remid_sid(res_authcode, remid, sid)

    res_session = await httpx_client.post( 
        url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
        json= {
            'jsonrpc': '2.0',
            'method': 'Authentication.getEnvIdViaAuthCode',
            'params': {
                'authCode': authcode,
                "locale": "zh-tw",
            },
            "id": str(uuid.uuid4())
        }
    )
    sessionID = res_session.json()['result']['sessionId']
    return remid,sid,sessionID

#获取欢迎信息
async def upd_gateway(method_name, remid, sid, sessionID, **kwargs):
    """
    Gateway API request wrapper. `kwargs` will be passed to the "params" in POST json data.

    If the request completes successfully, return parsed json data. If a error message returns or a HTTP error occurrs, 
    throw a `RSPException` which can be converted into readable text by `RSPException.echo`. 
    Other exceptions will not be handled.
    """
    kwargs['game'] = 'tunguska'
    try:
        response = await httpx_client.post(
            url = "https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
                'jsonrpc': '2.0',
                'method': method_name,
                'params': kwargs,
                "id": str(uuid.uuid4())
            },            
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
                },
            timeout=10
        )
        res_json = response.json()
        if 'error' in res_json:
            raise RSPException(msg=res_json['error']['message'], error_code=res_json['error']['code'])
        else:
            return res_json
    except httpx.RequestError as exc:
        raise RSPException(msg=f"{exc.request.url!r}", request_error=True)
    except httpx.HTTPStatusError as exc:
        raise RSPException(msg=f"{exc.request.url!r}", error_code=exc.response.status_code, request_error=True)

async def upd_welcome(remid, sid, sessionID):
    return await upd_gateway('Onboarding.welcomeMessage', remid, sid, sessionID)

#获取行动
async def upd_campaign(remid, sid, sessionID):
    return await upd_gateway(
        'CampaignOperations.getPlayerCampaignStatus',
        remid, sid, sessionID
    )

#获取交换
async def upd_exchange(remid, sid, sessionID):
    return await upd_gateway('ScrapExchange.getOffers', remid, sid, sessionID, minutesToUTC='-480')

#获取服务器详细信息
async def upd_detailedServer(remid, sid, sessionID, gameId):
    return await upd_gateway(
        'GameServer.getFullServerDetails', 
        remid, sid, sessionID, gameId=str(gameId)
    )

async def upd_platoon(remid, sid, sessionID, guid):
    return await upd_gateway('Platoons.getPlatoon', remid, sid, sessionID, guid=guid)

async def upd_platoons(remid, sid, sessionID, personaId):
    return await upd_gateway(
        'Platoons.getPlatoons', remid, sid, sessionID, personaId=personaId
    )

async def upd_findplatoon(remid, sid, sessionID, partialName, pageSize: int = 10):
    return await upd_gateway(
        'Platoons.findByPartialName', remid, sid, sessionID,
        partialName=partialName, pageIndex=0, pageSize=pageSize
    )

async def upd_platoonMembers(remid, sid, sessionID, guid, pageSize: int = 100):
    return await upd_gateway(
        'Platoons.getMembers', remid, sid, sessionID,
        guid=guid, pageIndex=0, pageSize=pageSize
    )

async def upd_reserveSlot(remid, sid, sessionID, gameId) -> dict:
    return await upd_gateway(
        'Game.reserveSlot', remid, sid, sessionID,
        gameId=str(gameId), gameProtocolVersion='3779779',
        currentGame='tunguska', settings={'role': 'spectator'}
    )

#离开服务器
async def upd_leaveServer(remid, sid, sessionID, gameId):
    return await upd_gateway(
        'Game.leaveGame', remid, sid, sessionID, gameId=str(gameId)
    )

#换边
async def upd_movePlayer(remid, sid, sessionID, gameId, personaId, teamId):
    return await upd_gateway(
        'RSP.movePlayer', remid, sid, sessionID,
        gameId=str(gameId), personaId=str(personaId), teamId=str(teamId),
        forceKill='true', moveParty='false'
    )

#解ban
async def upd_unbanPlayer(remid, sid, sessionID, serverId, personaId):
    return await upd_gateway(
        'RSP.removeServerBan', remid, sid, sessionID,
        serverId=str(serverId), personaId=str(personaId)
    )

#加ban
async def upd_banPlayer(remid, sid, sessionID, serverId, personaId):
    return await upd_gateway(
        'RSP.addServerBan', remid, sid, sessionID,
        serverId=str(serverId), personaId=str(personaId)
    )

#切图
async def upd_chooseLevel(remid, sid, sessionID, persistedGameId, levelIndex):
    return await upd_gateway(
        'RSP.chooseLevel', remid, sid, sessionID,
        persistedGameId=str(persistedGameId), levelIndex=str(levelIndex)
    )

#踢人
async def upd_kickPlayer(remid, sid, sessionID, gameId, personaId, reason):
    return await upd_gateway(
        'RSP.kickPlayer', remid, sid, sessionID,
        gameId=str(gameId), personaId=str(personaId), reason=str(reason)
    )

#加v
async def upd_vipPlayer(remid, sid, sessionID, serverId, personaId):
    return await upd_gateway(
        'RSP.addServerVip', remid, sid, sessionID,
        serverId=str(serverId), personaId=str(personaId)
    )

#下v
async def upd_unvipPlayer(remid, sid, sessionID, serverId, personaId):
    return await upd_gateway(
        'RSP.removeServerVip', remid, sid, sessionID,
        serverId=str(serverId), personaId=str(personaId)
    )

async def upd_getServersByPersonaIds(remid, sid, sessionID, personaIds):
    return await upd_gateway(
        'GameServer.getServersByPersonaIds', remid, sid, sessionID, personaIds=personaIds
    )

async def upd_mostRecentServers(remid, sid, sessionID, personaId):
    return await upd_gateway(
        'ServerHistory.mostRecentServers', remid, sid, sessionID, personaId=personaId
    )

#通过玩家数字Id获取玩家相关信息
async def upd_getPersonasByIds(remid, sid, sessionID, personaIds):
    return await upd_gateway(
        'RSP.getPersonasByIds', remid, sid, sessionID, personaIds=personaIds
    )

async def upd_getActiveTagsByPersonaIds(remid, sid, sessionID, personaIds):
    return await upd_gateway(
        'Platoons.getActiveTagsByPersonaIds', remid, sid, sessionID, personaIds=personaIds
    )

async def upd_WeaponsByPersonaId(remid, sid, sessionID, personaId):
    return await upd_gateway(
        'Progression.getWeaponsByPersonaId', remid, sid, sessionID, personaId=str(personaId)
    )

async def upd_VehiclesByPersonaId(remid, sid, sessionID, personaId):
    return await upd_gateway(
        'Progression.getVehiclesByPersonaId', remid, sid, sessionID, personaId=str(personaId)
    )

async def upd_StatsByPersonaId(remid, sid, sessionID, personaId):
    return await upd_gateway(
        'Stats.detailedStatsByPersonaId', remid, sid, sessionID, personaId=str(personaId)
    )

async def upd_loadout(remid, sid, sessionID, personaId):
    return await upd_gateway(
        'Loadout.getPresetsByPersonaId', remid, sid, sessionID, personaId=str(personaId)
    )

async def upd_servers(remid, sid, sessionID, serverName, limit: int = 7):
    return await upd_gateway(
        'GameServer.searchServers', remid, sid, sessionID,
        filterJson="{\"version\":6,\"name\":\"" + serverName + "\"}",
        limit=limit, protocolVersion="3779779"
    )

async def upd_Stats(personaIds):
    response = await httpx_client.post(
        url="https://api.gametools.network/bf1/multiple?raw=false&format_values=true",
        data= json.dumps(personaIds)
    )
    return response.json()

async def upd_Emblem(remid, sid, sessionID, personaId):
    return await upd_gateway(
        'Emblems.getEquippedEmblem', remid, sid, sessionID, personaId=str(personaId), platform="pc"
    )

async def get_playerList_byGameid(server_gameid: Union[str, int, list]) -> Union[str, dict]:
    """
    :param server_gameid: 服务器gameid
    :return: 成功返回字典,失败返回信息
    """
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36',
        'ContentType': 'json',
    }
    api_url = "https://delivery.easb.cc/games/get_server_status"
    if type(server_gameid) != list:
        data = {
            "gameIds": [
                server_gameid
            ]
        }
    else:
        data = {
            "gameIds": server_gameid
        }

    try:
        response = await httpx_client.post(api_url, headers=header, data=json.dumps(data), timeout=5)
        response = eval(response.text)
    except:
        return "网络超时!"
    if type(server_gameid) != list:
        if str(server_gameid) in response["data"]:
            return response["data"][str(server_gameid)] if response["data"][str(server_gameid)] != '' else "服务器信息为空!"
        else:
            return f"获取服务器信息失败:{response}"
    else:
        return response["data"]

__all__ = [
    'httpx_client',
    'getPersonasByName',
    'fetch_data', 'post_data', 
    'process_top_n', 'BTR_get_recent_info',
    'async_get_server_data', 'RSPException', 
    'upd_remid_sid', 'upd_token', 'upd_sessionId',
    'upd_welcome',
    'upd_campaign', 'upd_exchange',
    'upd_detailedServer',
    'upd_platoon', 'upd_platoons', 'upd_findplatoon', 'upd_platoonMembers',
    'upd_reserveSlot', 'upd_leaveServer',
    'upd_movePlayer',
    'upd_unbanPlayer', 'upd_banPlayer',
    'upd_chooseLevel',
    'upd_kickPlayer',
    'upd_vipPlayer', 'upd_unvipPlayer',
    'upd_getServersByPersonaIds', 'upd_mostRecentServers',
    'upd_getPersonasByIds', 'upd_getActiveTagsByPersonaIds',
    'upd_WeaponsByPersonaId', 'upd_VehiclesByPersonaId', 'upd_StatsByPersonaId', 
    'upd_loadout',
    'upd_servers',
    'upd_Stats',
    'upd_Emblem',
    'get_playerList_byGameid'
]