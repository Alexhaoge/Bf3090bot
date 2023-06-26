import json
import requests
import uuid
from pathlib import Path
import zhconv
import datetime
from datetime import timedelta
from .utils import BF1_SERVERS_DATA

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
def upd_welcome(remid, sid, sessionID):
    res = requests.post(
        url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
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
    return res.json()

#获取行动
def upd_campaign(remid, sid, sessionID):
    res = requests.post(
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
    return res.json()

#获取交换
def upd_exchange(remid, sid, sessionID):
    res = requests.post(
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
    return res.json()

#获取服务器详细信息
def upd_detailedServer(remid, sid, sessionID, gameId):
    res = requests.post(
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
    return res.json()

#离开服务器
def upd_leaveServer(remid, sid, sessionID, gameId):
    res = requests.post(
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
    return res.json()


#换边
def upd_movePlayer(remid, sid, sessionID, gameId, personaId, teamId):
    res = requests.post(
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
    return res.json()

#解ban
def upd_unbanPlayer(remid, sid, sessionID, serverId, personaId):
    res = requests.post(
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
    return res.json()

#加ban
def upd_banPlayer(remid, sid, sessionID, serverId, personaName):
    res = requests.post(
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
    return res.json()

#切图
def upd_chooseLevel(remid, sid, sessionID, persistedGameId, levelIndex):
    res = requests.post(
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
    return res.json()

#踢人
def upd_kickPlayer(remid, sid, sessionID, GameId, personaId, reason):
    res = requests.post(
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
    return res.json()

#加v
def upd_vipPlayer(remid, sid, sessionID, serverId, personaName):
    res = requests.post(
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
    return res.json()

#下v
def upd_unvipPlayer(remid, sid, sessionID, serverId, personaId):
    res = requests.post(
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
    return res.json()

#通过玩家数字Id获取玩家相关信息
def upd_getPersonasByIds(remid, sid, sessionID, personaIds):
    res = requests.post(
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
    return res.json()

def upd_StatsByPersonaId(remid, sid, sessionID, personaId):
    res = requests.post(
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
    return res.json()

def upd_servers(remid, sid, sessionID, serverName):
    res = requests.post(
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
    return res.json()


def upd_Stats(personaIds):
    res = requests.post(
        url="https://api.gametools.network/bf1/multiple?raw=false&format_values=true",
        data= json.dumps(personaIds)
    )
    return res.json()

def upd_Emblem(remid, sid, sessionID, personaId):
    res = requests.post(
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
    return res.json()


