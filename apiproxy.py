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

@app.post("/report/")
async def async_bftracker_recent(origin_id: str, pid: int, top_n: int = 3) -> dict:
    games_req = await fetch_re(origin_id)
    
    tasks = []

    for i in range(min(top_n,len(games_req["data"]["matches"]))):
        report_id = games_req["data"]["matches"][i]["attributes"]["id"]
        tasks.append(fetch_id(report_id,pid))
    
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
    limits=httpx.Limits(max_connections=500))
httpx_client_ea = httpx.AsyncClient(base_url='https://accounts.ea.com/connect/auth')

@app.post('/proxy/accountsea/', status_code=200)
async def accounts_ea_proxy(request: Request, response: Response):
    try:
        headers = {'Cookie': request.headers.get('Cookie')}
        possible_header_names = ['user-agent', 'content-type']
        for name in possible_header_names:
            if name in request.headers:
                headers[name] = request.headers.get(name)
        if 'follow_redirects' in request.headers:
            follow_redirects = request.headers.get('follow_redirects')
        else:
            follow_redirects = False
        res = await httpx_client_ea.post(
            url = "/",
            params = request.query_params,
            headers = headers,
            follow_redirects=follow_redirects
        )
    except Exception as e:
        print(traceback.format_exc(limit=1))
        response.status_code = 504
        return traceback.format_exc(limit=1)
    for k,v in res.cookies:
        response.set_cookie(key=k, value=v)
    response.headers.update(res.headers)
    return res.json()

@app.post('/proxy/gateway/', status_code=200)
async def battlelog_gateway_proxy(request: Request, response: Response):
    try:
        res = await httpx_client_gateway.post(
            url="/",
            json = await request.json(),
            headers= {
                #'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': request.headers.get('X-GatewaySession')
            }
        )
    except Exception as e:
        print(traceback.format_exc(limit=1))
        response.status_code = 504
        return traceback.format_exc(limit=1)
    for k,v in res.cookies:
        response.set_cookie(key=k, value=v)
    return res.json()

@app.on_event("shutdown")
async def shutdown_event():
    await httpx_client_gateway.aclose()
    print('Client closed!')

if __name__ == '__main__':
    uvicorn.run(app)