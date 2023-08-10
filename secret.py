import httpx
import json
import asyncio
from .bf1rsp import *

async def upd_blazestat(personaId,method):
    async with httpx.AsyncClient() as client:
        response = await client.post(url=f'http://127.0.0.1:5000/stats/{method}/{personaId}',timeout=10)
        try:
            status = response.content.decode('utf-8')
            status = status.replace('"No_Scope_Defined":','').replace('"KSSV":','').replace('\r','').replace('\n','').replace('\t','').replace(' ','').replace(',}','}').replace(',]',']').replace('}]}}','}}}}').replace('{"STAT":[','{"STAT":{').rstrip(',')
            status = json.loads(status)
            exlist = list(list(status.values())[0]["STAT"].values())[0]["STAT"]

            dictjson = {}
            for i in range(0,len(exlist),5):
                L = []
                for j in range(5):
                    try:
                        L.append(float(exlist[i+j]))
                    except:
                        continue
                dictjson[f'{int(int(i)/5+3)}'] = L
            return dictjson
        except:
            return 0

async def upd_blazepl(gameId):
    async with httpx.AsyncClient() as client:
        response = await client.post(url=f'http://127.0.0.1:5000/pl/{int(gameId)}',timeout=10)
        status = response.content.decode('utf-8')
    
    originstatus = '{' + status.replace('\r','').replace('\n','').replace('\t','').replace("\\","\\\\").replace(' ','').replace(',}','}').replace(',]',']').rstrip(",").replace('"LGAM":[','"LGAM":{').replace('"PROS":[','"PROS": {').replace('"DNET":[','"DNET":{').replace('],"DRTO"','},"DRTO"').replace('"HNET":[','"HNET":{').replace('],"MCAP"','},"MCAP"').replace("}]}]", "}}}}}").replace('"soldier":','')
    status = json.loads(originstatus)
    PL = list(list(status['LGAM'].values())[0]["PROS"].values())
    TIDX = []
    PID = []
    NAME = []

    for player in PL:
        TIDX.append(player["TIDX"])
        PID.append(player["PID"])
        NAME.append(player["NAME"])

    MAP = list(status['LGAM'].values())[0]['GAME']["ATTR"]["level"]
    
    stat1 = []
    stat2 = []
    for i in range(len(TIDX)):
            dic = {
                "id": PID[i],
                "userName": NAME[i],
                }
            if TIDX[i] == "0":
                stat1.append(dic)
            if TIDX[i] == "1":
                stat2.append(dic)
    pljson = {
        "map": MAP,
        "team1": MapTeamDict[f"{MAP}"]["Team1"],
        "team2": MapTeamDict[f"{MAP}"]["Team2"],
        '1': stat1,
        '2': stat2
    }
    return pljson

async def get_blazepl(remid,sid,sessionID,gameId):
    async with httpx.AsyncClient() as client:
        response = await client.post(url=f'http://127.0.0.1:5000/pl/{int(gameId)}',timeout=10)
        status = response.content.decode('utf-8')
    
    originstatus = '{' + status.replace('\r','').replace('\n','').replace('\t','').replace("\\","\\\\").replace(' ','').replace(',}','}').replace(',]',']').rstrip(",").replace('"LGAM":[','"LGAM":{').replace('"PROS":[','"PROS": {').replace('"DNET":[','"DNET":{').replace('],"DRTO"','},"DRTO"').replace('"HNET":[','"HNET":{').replace('],"MCAP"','},"MCAP"').replace("}]}]", "}}}}}").replace('"soldier":','')
    status = json.loads(originstatus)
    PL = list(list(status['LGAM'].values())[0]["PROS"].values())
    TIDX = []
    IPS = []
    PID = []
    NAME = []
    LOC = []
    LAG = []
    RANK = []
    for player in PL:
        TIDX.append(player["TIDX"])
        PID.append(player["PID"])
        NAME.append(player["NAME"])
        LOC.append(player["LOC"])

        try:
            ip = player["PNET"]["VALU"]["EXIP"]["IP"]
            ip = IPy.intToIp((ip),4)
            ip = reader.city(ip).country.names['zh-CN']
        except:
            ip = '一'
        IPS.append(ip[0])

        try:
            LAG.append(player["PATT"]["latency"])
        except:
            LAG.append("0")
        
        try:
            RANK.append(player["PATT"]["rank"])
        except:
            RANK.append("0")

    MAP = list(status['LGAM'].values())[0]['GAME']["ATTR"]["level"]

    LOCS = []
    for i in LOC:
        if i.startswith('16840'):
            LOCS.append("丹")
        elif i.startswith('16843'):
            LOCS.append("德")
        elif i.startswith('17020'):
            LOCS.append("西")
        elif i.startswith('17017'):
            LOCS.append("英")
        elif i.startswith('17181'):
            LOCS.append("芬")
        elif i.startswith('17187'):
            LOCS.append("法")
        elif i.startswith('17525'):
            LOCS.append("匈")
        elif i.startswith('17692'):
            LOCS.append("意")
        elif i.startswith('17847'):
            LOCS.append("日")
        elif i.startswith('18024'):
            LOCS.append("韩")
        elif i.startswith('18525'):
            LOCS.append("荷")
        elif i.startswith('18861'):
            LOCS.append("波")
        elif i.startswith('18866'):
            LOCS.append("葡")
        elif i.startswith('18861'):
            LOCS.append("波")                        
        elif i.startswith('19202'):
            LOCS.append("俄") 
        elif i.startswith('19371'):
            LOCS.append("瑞") 
        elif i.startswith('19529'):
            LOCS.append("泰") 
        elif i.startswith('19536'):
            LOCS.append("土") 
        elif i.startswith('19699'):
            LOCS.append("乌") 
        elif i.startswith('20536'):
            LOCS.append("中") 
        else:
            LOCS.append("一") 
    
    tasks = []
    for i in PID:
        tasks.append(asyncio.create_task(upd_StatsByPersonaId(remid,sid,sessionID,i)))
    TAG = await upd_getActiveTagsByPersonaIds(remid,sid,sessionID,PID)

    STAT = await asyncio.gather(*tasks)
    TAG = TAG["result"]
    stat1 = []
    stat2 = []
    for i in range(len(TIDX)):
        try:
            stt = STAT[i]["result"]
            win = stt['basicStats']['wins']
            loss = stt['basicStats']['losses']
            acc = stt['accuracyRatio']
            hs = stt['headShots']
            kd = stt['kdr']
            k = stt['basicStats']['kills']
        except Exception as e:
            continue
        else:
            dic = {
                "id": PID[i],
                "platoon": TAG[f'{PID[i]}'],
                "loc": LOCS[i],
                "lang": IPS[i],
                "userName": NAME[i],
                "rank": int(RANK[i]),
                "latency": LAG[i],
                "killDeath": round(kd,2),
                "killsPerMinute": stt["basicStats"]["kpm"],
                "winPercent": f'{0 if win+loss == 0 else win*100/(win+loss):.2f}%',
                "secondsPlayed": stt["basicStats"]["timePlayed"],
                "headShot": f"{0 if k == 0 else hs/k*100:.2f}%"
                }
            if TIDX[i] == "0":
                stat1.append(dic)
            if TIDX[i] == "1":
                stat2.append(dic)
    pljson = {
        "map": MAP,
        "team1": MapTeamDict[f"{MAP}"]["Team1"],
        "team2": MapTeamDict[f"{MAP}"]["Team2"],
        '1': stat1,
        '2': stat2
    }

    return pljson

async def bfeac_checkBan(player_name: str) -> dict:
    """
    检查玩家bfeac信息
    :param player_name: 玩家名称
    :return: {"stat": "状态", "url": "案件链接"}
    """
    check_eacInfo_url = f"https://api.bfeac.com/case/EAID/{player_name}"
    header = {
        "apikey": "keep-alive"
    }
    eac_stat_dict = {
        0: "未处理",
        1: "已封禁",
        2: "证据不足",
        3: "自证通过",
        4: "自证中",
        5: "刷枪",
    }
    result = {
        "stat": "无",
        "url": "无"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(check_eacInfo_url, timeout=5)
            response = json.loads(response.text)
        if response.get("data"):
            data = response["data"][0]
            eac_status = eac_stat_dict[data["current_status"]]
            if data.get("case_id"):
                case_id = data["case_id"]
                case_url = f"https://bfeac.com/#/case/{case_id}"
                result["url"] = case_url
            result["stat"] = eac_status
        return result
    except Exception as e:
        print(f"bfeac_checkBan: {e}")
        return result
    
async def bfeac_report(playerName,case_body) -> dict:
    """
    举报
    """
    url = f"https://api.bfeac.com/inner_api/case_report"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url = url,
                json = {
                    "target_personaId": 0,
                    "target_userId": 0,
                    "target_EAID": playerName,
                    "case_body": case_body,
                    "game_type": 1,
                    "battlelog_snapshot_url": None,
                    "report_by": {}
                },
                headers = {
                    "apikey": "0f493d7f-359c-11ee-8b10-0097a5a3dbd7"
                },
            )
        return response.json()
    except Exception as e:
        return response.content