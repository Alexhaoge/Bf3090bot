import json
import requests
import aiohttp
import uuid
from pathlib import Path
import zhconv
from datetime import timedelta
import datetime,time
from .utils import BF1_SERVERS_DATA,MapTeamDict,CURRENT_FOLDER
import httpx
import asyncio
import bs4
import re
import IPy
import geoip2.database
from typing import Union

reader = geoip2.database.Reader(CURRENT_FOLDER/"GeoLite2-City.mmdb")

async def getPersonasByName(access_token, player_name) -> dict:
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
            async with aiohttp.ClientSession() as session:
                response = await session.get(
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
        except:
            return "网络超时!"

async def fetch_data(url,headers):
    async with httpx.AsyncClient() as client:
        response = await client.get(url=url,headers=headers,timeout=20)
        return response
    
async def post_data(url,json,headers):
    async with httpx.AsyncClient() as client:
        response = await client.post(url=url,json=json,headers=headers,timeout=20)
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

async def async_bftracker_recent(origin_id: str, top_n: int = 3) -> Union[list, str]:
    headers = {
        "Connection": "keep-alive",
        "User-Agent": "ProtoHttp 1.3/DS 15.1.2.1.0 (Windows)",
    }
    url=f'https://battlefieldtracker.com/bf1/profile/pc/{origin_id}/matches'

    games_req = await fetch_data(url,headers)
  
    soup = bs4.BeautifulSoup(games_req.text, 'html.parser')
    if soup.select('.alert.alert-danger.alert-dismissable'):
        return 'player not found'
    games = soup.select('.bf1-profile .profile-main .content .matches a')[:top_n]
    tasks = []
    for i in range(top_n):
        tasks.append(asyncio.create_task(process_top_n(games[i]['href'], headers)))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

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
    async with aiohttp.ClientSession(headers=header) as session:
        async with session.get(url) as response:
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
                    time.mktime(time.strptime(time_item, "%Y-%m-%dT%H:%M:%S.000Z")))+datetime.timedelta(hours=10)
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
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url="https://api.gametools.network/bf1/servers",
            params={'name':serverName,
                    'lang':'zh-tw',
                    "platform":"pc",
                    "limit":20}
                    )
        return response.text


error_code_dict = {
    -32501: "Session无效",
    -32600: "请求格式错误",
    -32601: "请求参数错误",
    -32602: "请求参数错误/不存在",
    -32603: "所用账号没有进行该操作的权限",
    -32855: "Sid不存在",
    -32856: "玩家不存在,请检查玩家名字",
    -32850: "服务器栏位已满/玩家已在栏位",
    -32857: "所用账号没有进行该操作的权限",
    # -32858: "服务器未开启!"
}

async def upd_remid_sid(res: httpx.Response, remid, sid):
    res_cookies = httpx.Cookies.extract_cookies(res.cookies,res)
    res_cookies = json.dumps(res_cookies)
    if 'sid' in res_cookies:
        sid = res_cookies['sid']
    if 'remid' in res_cookies:
        remid = res_cookies['remid']
    return remid, sid

async def upd_token(remid, sid):
    async with httpx.AsyncClient() as client:
        res_access_token = await client.get(
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
    return res_access_token,access_token

async def upd_sessionId(res_access_token, remid, sid, num):
    remid, sid = await upd_remid_sid(res_access_token, remid, sid)

    async with httpx.AsyncClient() as client:
        res_authcode = await client.get(       
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
    remid, sid = await upd_remid_sid(res_authcode, remid, sid)
    
    if num == 0:
        with open(BF1_SERVERS_DATA/'Caches'/'id.txt','w' ,encoding='UTF-8') as f:
            f.write(f'{remid},{sid}')
    else:
        with open(BF1_SERVERS_DATA/'Caches'/f'id{num}.txt','w' ,encoding='UTF-8') as f:
            f.write(f'{remid},{sid}')

    async with httpx.AsyncClient() as client:
        res_session = await client.post( 
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
async def upd_welcome(remid, sid, sessionID):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url = "https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
                'jsonrpc': '2.0',
                'method': 'Onboarding.welcomeMessage',
                'params': {
                    'game' : "tunguska",
                    'minutesToUTC' : "-480"
                },
                "id": str(uuid.uuid4())
            },            
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
                },
            timeout=10
        )
    return response.json()

#获取行动
async def upd_campaign(remid, sid, sessionID):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "CampaignOperations.getPlayerCampaignStatus",
	            "params": {
		        "game": "tunguska"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },    
            timeout=10       
        )
        return response.json()


#获取交换
async def upd_exchange(remid, sid, sessionID):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "ScrapExchange.getOffers",
	            "params": {
		        "game": "tunguska"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )

    return response.json()

#获取服务器详细信息
async def upd_detailedServer(remid, sid, sessionID, gameId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "GameServer.getFullServerDetails",
	            "params": {
		        "game": "tunguska",
                "gameId": f"{gameId}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )

    return response.json()

async def upd_platoons(remid, sid, sessionID, personaId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "Platoons.getPlatoons",
	            "params": {
		        "game": "tunguska",
                "personaId": personaId
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

async def upd_reserveSlot(remid, sid, sessionID, gameId) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json={
                "jsonrpc": "2.0",
                "method": "Game.reserveSlot",
                "params": {
                    "game": "tunguska",
                    "gameId": f"{gameId}",
                    "gameProtocolVersion": "3779779",
                    "currentGame": "tunguska",
                    "settings": {"role": "spectator"}
                },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

#离开服务器
async def upd_leaveServer(remid, sid, sessionID, gameId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "Game.leaveGame",
	            "params": {
		        "game": "tunguska",
                "gameId": f"{gameId}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )

    return response.json()

#换边
async def upd_movePlayer(remid, sid, sessionID, gameId, personaId, teamId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "RSP.movePlayer",
	            "params": {
		        "game": "tunguska",
                "gameId": f"{gameId}",
                "personaId": f"{personaId}",
                "teamId": f"{teamId}",
                "forceKill": "true",
                "moveParty": "false"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10        
        )

    return response.json()

#解ban
async def upd_unbanPlayer(remid, sid, sessionID, serverId, personaId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "RSP.removeServerBan",
	            "params": {
		        "game": "tunguska",
                "serverId": f"{serverId}",
                "personaId": f"{personaId}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )

    return response.json()

#加ban
async def upd_banPlayer(remid, sid, sessionID, serverId, personaName):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "RSP.addServerBan",
	            "params": {
		        "game": "tunguska",
                "serverId": f"{serverId}",
                "personaName": f"{personaName}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )

    return response.json()

#切图
async def upd_chooseLevel(remid, sid, sessionID, persistedGameId, levelIndex):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "RSP.chooseLevel",
	            "params": {
		        "game": "tunguska",
                "persistedGameId": f"{persistedGameId}",
                "levelIndex": f"{levelIndex}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

#踢人
async def upd_kickPlayer(remid, sid, sessionID, GameId, personaId, reason):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "RSP.kickPlayer",
	            "params": {
		        "game": "tunguska",
                "gameId": f"{GameId}",
                "personaId": f"{personaId}",
                "reason": f"{reason}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

#加v
async def upd_vipPlayer(remid, sid, sessionID, serverId, personaName):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "RSP.addServerVip",
	            "params": {
		        "game": "tunguska",
                "serverId": f"{serverId}",
                "personaName": f"{personaName}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

#下v
async def upd_unvipPlayer(remid, sid, sessionID, serverId, personaId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "RSP.removeServerVip",
	            "params": {
		        "game": "tunguska",
                "serverId": f"{serverId}",
                "personaId": f"{personaId}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

async def upd_getServersByPersonaIds(remid, sid, sessionID, personaIds):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "GameServer.getServersByPersonaIds",
	            "params": {
		        "game": "tunguska",
                "personaIds": personaIds
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

async def upd_mostRecentServers(remid, sid, sessionID, personaId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "ServerHistory.mostRecentServers",
	            "params": {
		        "game": "tunguska",
                "personaId": personaId
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

#通过玩家数字Id获取玩家相关信息
async def upd_getPersonasByIds(remid, sid, sessionID, personaIds):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "RSP.getPersonasByIds",
	            "params": {
		        "game": "tunguska",
                "personaIds": personaIds
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

async def upd_getActiveTagsByPersonaIds(remid, sid, sessionID, personaIds):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "Platoons.getActiveTagsByPersonaIds",
	            "params": {
		        "game": "tunguska",
                "personaIds": personaIds
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

async def upd_WeaponsByPersonaId(remid, sid, sessionID, personaId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "Progression.getWeaponsByPersonaId",
	            "params": {
		        "game": "tunguska",
                "personaId": f"{personaId}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

async def upd_VehiclesByPersonaId(remid, sid, sessionID, personaId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "Progression.getVehiclesByPersonaId",
	            "params": {
		        "game": "tunguska",
                "personaId": f"{personaId}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

async def upd_StatsByPersonaId(remid, sid, sessionID, personaId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "Stats.detailedStatsByPersonaId",
	            "params": {
		        "game": "tunguska",
                "personaId": f"{personaId}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

async def upd_servers(remid, sid, sessionID, serverName):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "GameServer.searchServers",
	            "params": {
		        "filterJson": "{\"version\":6,\"name\":\"" + serverName + "\"}",
                "game": "tunguska",
                "limit": 7,
                "protocolVersion": "3779779"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()


async def upd_Stats(personaIds):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://api.gametools.network/bf1/multiple?raw=false&format_values=true",
            data= json.dumps(personaIds)
        )
    return response.json()

async def upd_Emblem(remid, sid, sessionID, personaId):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "Emblems.getEquippedEmblem",
	            "params":{
		        "platform": "pc",
                "personaId": f"{personaId}"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=10
        )
    return response.json()

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
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=header, data=json.dumps(data), timeout=5)
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
