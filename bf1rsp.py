import json
import requests
import uuid
from pathlib import Path
import zhconv
from datetime import timedelta
from .utils import BF1_SERVERS_DATA
import httpx
import asyncio
import bs4
import re
from typing import Union

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

def upd_remid_sid(res: requests.Response, remid, sid):
    res_cookies = requests.utils.dict_from_cookiejar(res.cookies)
    if 'sid' in res_cookies:
        sid = res_cookies['sid']
    if 'remid' in res_cookies:
        remid = res_cookies['remid']
    return remid, sid

def upd_sessionId(remid, sid):
    res_access_token = requests.get(
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

    with open(BF1_SERVERS_DATA/'Caches'/'id.txt','w' ,encoding='UTF-8') as f:
        f.write(f'{remid},{sid}')
        
    res_authcode = requests.get(
        url="https://accounts.ea.com/connect/auth",
        params= {
            'client_id': 'sparta-backend-as-user-pc',
            'response_type': 'code',
            'release_type': 'none'
        },
        headers= {
            'Cookie': f'remid={remid};sid={sid}'
        },
        allow_redirects=False
    )
    # 这个请求默认会重定向，所以要禁用重定向，并且重定向地址里的code参数就是我们想要的authcode
    authcode = str.split(res_authcode.next.path_url, "=")[1]
    remid, sid = upd_remid_sid(res_authcode, remid, sid)

    res_session = requests.post(
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
    print(res_session.json())
    return sessionID

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
        )
    return response.json()

#通过玩家数字Id获取玩家相关信息
def upd_getPersonasByIds(remid, sid, sessionID, personaIds):
        response = requests.post(
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
                "limit": 30,
                "protocolVersion": "3779779"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
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
        )
    return response.json()