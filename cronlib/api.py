import httpx
import uuid

async def upd_servers(remid, sid, sessionID, PROXY_HOST):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=f"http://{PROXY_HOST}:8000/proxy/gateway/",
            json = {
	            "jsonrpc": "2.0",
	            "method": "GameServer.searchServers",
	            "params": {
		        "filterJson": "{\"serverType\":{\"OFFICIAL\": \"off\"}}",
                "game": "tunguska",
                "limit": 200,
                "protocolVersion": "3779779"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=5
        )
    res_json = response.json()
    if 'error' in res_json:
        if "session expired" in res_json['error']['message'] or res_json['error']['code'] == -32501:
            raise Exception(f'sessionID expired: {sessionID}')
        raise Exception(res_json['error']['message'])
    return res_json

async def upd_detailedServer(remid, sid, sessionID, gameId, PROXY_HOST):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=f"http://{PROXY_HOST}:8000/proxy/gateway/",
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
            timeout=5
        )
    res_json = response.json()
    if 'error' in res_json:
        if "session expired" in res_json['error']['message'] or res_json['error']['code'] == -32501:
            raise Exception(f'sessionID expired: {sessionID}')
        raise Exception(res_json['error']['message'])
    return res_json


async def upd_kickPlayer(remid, sid, sessionID, gameId, personaId, reason, PROXY_HOST):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=f"http://{PROXY_HOST}:8000/proxy/gateway/",
            json = {
	            "jsonrpc": "2.0",
	            "method": 'RSP.kickPlayer',
	            "params": {
		        "game": "tunguska",
                "gameId": str(gameId),
                "personaId": str(personaId),
                "reason": reason
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=5
        )
    res_json = response.json()
    if 'error' in res_json:
        if "session expired" in res_json['error']['message'] or res_json['error']['code'] == -32501:
            raise Exception(f'sessionID expired: {sessionID}')
        raise Exception(res_json['error']['message'])
    return res_json

async def upd_getPersonasByIds(remid, sid, sessionID, personaId, PROXY_HOST):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=f"http://{PROXY_HOST}:8000/proxy/gateway/",
            json = {
	            "jsonrpc": "2.0",
	            "method": 'RSP.getPersonasByIds',
	            "params": {
		        "game": "tunguska",
                "personaIds": personaId,
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=5
        )
    res_json = response.json()
    if 'error' in res_json:
        if "session expired" in res_json['error']['message'] or res_json['error']['code'] == -32501:
            raise Exception(f'sessionID expired: {sessionID}')
        raise Exception(res_json['error']['message'])
    return res_json


def upd_remid_sid(res: httpx.Response, remid, sid):
    res_cookies = res.cookies
    if 'sid' in res_cookies:
        sid = res_cookies['sid']
    if 'remid' in res_cookies:
        remid = res_cookies['remid']
    return remid, sid

async def upd_token(remid, sid, PROXY_HOST):
    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=3)) as client:
        res_access_token = await client.get(
            url=f"http://{PROXY_HOST}:8000/proxy/ea/token/",
            params= {'remid': remid, 'sid': sid}, 
            timeout=5,
        )
    access_token = res_access_token.json()['access_token']
    remid, sid = upd_remid_sid(res_access_token, remid, sid)
    return remid, sid, access_token

async def upd_sessionId(remid, sid, PROXY_HOST):
    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=3)) as client:
        res_authcode = await client.get(       
            url=f"http://{PROXY_HOST}:8000/proxy/ea/authcode/",
            params= {'remid': remid, 'sid': sid}, timeout=5
        )
        authcode = res_authcode.json()['authcode']
        remid, sid = upd_remid_sid(res_authcode, remid, sid)
        res_session = await client.post( 
            url=f"http://{PROXY_HOST}:8000/proxy/gateway/",
            json= {
                'jsonrpc': '2.0',
                'method': 'Authentication.getEnvIdViaAuthCode',
                'params': {
                    'authCode': authcode,
                    "locale": "zh-tw",
                },
                "id": str(uuid.uuid4())
            },
            timeout=5
        )
    sessionID = res_session.json()['result']['sessionId']
    return remid,sid,sessionID



__all__ = [
    'upd_servers', 'upd_detailedServer',
    'upd_remid_sid', 'upd_token', 'upd_sessionId',
    'upd_kickPlayer',
    'upd_getPersonasByIds'
]