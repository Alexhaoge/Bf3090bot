import uvicorn
import httpx
import traceback
import aiohttp
import bs4
import asyncio
from typing import Union,Optional
import time
import datetime
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from btr import fetch_id, fetch_re

app=FastAPI()

@app.get("/")
async def index():
    return "This is Home Page."

class rItem(BaseModel):  
    origin_id: str = None  
    top_n: int = 3  

httpx_client_btr = httpx.AsyncClient(
    base_url='https://api.tracker.gg/api/v2', 
    transport=httpx.AsyncHTTPTransport(retries=3))

@app.post("/report/")
async def async_bftracker_recent(origin_id: str, pid: int, top_n: int = 3) -> dict:
    games_req = await fetch_re(origin_id, httpx_client_btr)
    
    tasks = []

    for i in range(min(top_n,len(games_req["data"]["matches"]))):
        report_id = games_req["data"]["matches"][i]["attributes"]["id"]
        tasks.append(fetch_id(report_id,pid, httpx_client_btr))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    data = {
        "data": results
    }
    return data


@app.post("/re/")
async def BTR_get_recent_info(player_name: str) -> Optional[list[dict]]:
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


httpx_client_gateway = httpx.AsyncClient(
    base_url='https://sparta-gw.battlelog.com/jsonrpc/pc/api',
    limits=httpx.Limits(max_connections=400),
    transport=httpx.AsyncHTTPTransport(retries=2))
httpx_client_ea = httpx.AsyncClient(
    base_url='https://accounts.ea.com/connect/auth',
    transport=httpx.AsyncHTTPTransport(retries=3))
httpx_client_ea_gt = httpx.AsyncClient(
    base_url='https://gateway.ea.com', 
    transport=httpx.AsyncHTTPTransport(retries=2))

@app.get('/proxy/ea/token/', status_code=200)
async def ea_token_proxy(remid: str, sid: str, response: Response):
    try:
        res = await httpx_client_ea.get(
            url="/",
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
    except Exception as e:
        print(traceback.format_exc(limit=1))
        response.status_code = 504
        return traceback.format_exc(limit=1)
    for k,v in res.cookies.items():
        response.set_cookie(key=k, value=v)
    return res.json()

@app.get('/proxy/ea/authcode/', status_code=200)
async def ea_authcode_proxy(remid: str, sid: str, response: Response):
    try:
        res = await httpx_client_ea.get(
            url="/",
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
    except Exception as e:
        print(traceback.format_exc(limit=1))
        response.status_code = 504
        return traceback.format_exc(limit=1)
    for k,v in res.cookies.items():
        response.set_cookie(key=k, value=v)
    return {'authcode': str.split(res.headers.get("location"), "=")[1]}

@app.get('/proxy/ea/gt/', status_code=200)
async def ea_gateway_proxy(player: str, token: str, response: Response):
    try:
        res = await httpx_client_ea_gt.get(
            url=f'/proxy/identity/personas?namespaceName=cem_ea_id&displayName={player}',
            headers={
                "Host": "gateway.ea.com",
                "Connection": "keep-alive",
                "Accept": "application/json",
                "X-Expand-Results": "true",
                "Authorization": f"Bearer {token}",
                "Accept-Encoding": "deflate",
            },
            timeout=10
        )
        res2 =  res.json()
        id = res2['personas']['persona'][0]['personaId']
        name = res2['personas']['persona'][0]['displayName']
        pidid = res2['personas']['persona'][0]['pidId']
        return {'pid': id, 'name': name, 'pidid': pidid}
    except httpx.HTTPError as e:
        print(traceback.format_exc(limit=1))
        response.status_code = 504
        return traceback.format_exc(limit=1)   
    except Exception as e:
        print(traceback.format_exc(limit=1))
        response.status_code = 404
        return traceback.format_exc(limit=1)    
        

@app.post('/proxy/gateway/', status_code=200)
async def battlelog_gateway_proxy(request: Request, response: Response):
    try:
        headers = {}
        if 'X-GatewaySession' in request.headers.keys():
            headers['X-GatewaySession'] = request.headers.get('X-GatewaySession')
        res = await httpx_client_gateway.post(
            url="/",
            json = await request.json(),
            headers = headers
        )
    except Exception as e:
        print(traceback.format_exc())
        response.status_code = 504
        return traceback.format_exc(limit=1)
    for k,v in res.cookies.items():
        response.set_cookie(key=k, value=v)
    return res.json()

@app.on_event("shutdown")
async def shutdown_event():
    await httpx_client_gateway.aclose()
    await httpx_client_ea.aclose()
    await httpx_client_ea_gt.aclose()
    await httpx_client_btr.aclose()
    print('Client closed!')

if __name__ == '__main__':
    uvicorn.run(app)