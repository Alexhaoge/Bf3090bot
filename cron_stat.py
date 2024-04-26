import json, asyncio, datetime,httpx,uuid
import psycopg
import time
from dotenv import dotenv_values
from pathlib import Path
from PIL import Image
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from cronlib.db import *
from cronlib.api import *
from cronlib.cron_secret import *

config = dotenv_values('.env.prod')
BFCHAT_DATA_FOLDER = Path(config['BFCHAT_DIR']).resolve()
BLAZE_HOST = config['BLAZE_HOST']
PROXY_HOST = config['PROXY_HOST']
EAC_SERVER_BLACKLIST = config['EAC_SERVER_BLACKLIST']
db_url = config['psycopg_database']

# with open(BFCHAT_DATA_FOLDER/'bf1_servers/zh-cn.json','r', encoding='utf-8') as f:
#     zh_cn_mapname = json.load(f)
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

async def refresh_statInfo():
    time_start = time.time()
    conn = psycopg.connect(db_url)

    tasks = []
    results = []

    pids = [r[0] for r in db_op(conn, "SELECT pid FROM players;", [])]
    
    stats_old = [{'pid': r[0], 'kills': r[1], 'deaths': r[2], 'playtimes': r[3], 'wins': r[4], 'losses': r[5], 'rounds': r[6], 'headshots': r[7], 'updatetime': r[8], 'acc': r[9], 'score': r[10]} for r in db_op(conn, "SELECT * FROM playerstats;", [])]
    stats_old_json = {}
    for stt in stats_old:
        pid = stt["pid"]
        stats_old_json[f'{pid}'] = stt

    diff_old = [{'pid': r[0], 'diff': r[1]} for r in db_op(conn, "SELECT * FROM playerstatsdiff;", [])]
    diff_old_json = {}
    for stt in diff_old:
        pid = stt["pid"]
        diff_old_json[f'{pid}'] = stt["diff"]

    pids_temp = []
    cnt = 0
    for pid in pids:
        remid, sid, sessionID = get_one_random_bf1admin(conn)
        pids_temp.append(pid)
        tasks.append(upd_StatsByPersonaId(remid,sid,sessionID,pid))
        if len(tasks) == 200:
            cnt+=200
            print(f"开始获取战绩详细信息，共{len(tasks)}个，总进度{cnt}/{len(pids)}")
            temp = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(filter(lambda x: isinstance(x, dict), temp))
            update_db(results,pids_temp,conn,stats_old_json,diff_old_json)
            
            pids_temp = []
            results = []
            tasks = []
            await asyncio.sleep(1)

    if tasks:
        print(f"开始获取战绩详细信息，共{len(tasks)}个，总进度{len(pids)}/{len(pids)}")
        temp = await asyncio.gather(*tasks, return_exceptions=True)
        results.extend(filter(lambda x: isinstance(x, dict), temp))
    time_end = time.time()
    print(f'更新战绩用时: {time_end-time_start}')
def update_db(results,pids,conn,stats_old_json,diff_old_json):
    stats_info = []
    diff_info = []
    for i in range(len(results)):
        res_stat = results[i]
        pid = pids[i]

        win = res_stat['result']['basicStats']['wins']
        loss = res_stat['result']['basicStats']['losses']
        acc = res_stat['result']['accuracyRatio']
        hs = res_stat['result']['headShots']
        secondsPlayed = res_stat['result']['basicStats']['timePlayed']
        k = res_stat['result']['basicStats']['kills']
        d = res_stat['result']['basicStats']['deaths']
        rounds = res_stat['result']["roundsPlayed"]
        spm = res_stat['result']['basicStats']['spm']
        score = int(spm * secondsPlayed / 60)

        try:
            oldstat = stats_old_json[f'{pid}']
            oldtime = oldstat["playtimes"]
        except:
            oldtime = secondsPlayed

        try:
            olddiff = diff_old_json[f'{pid}']
        except:
            olddiff = {}
        newdiff = {}
        
        if oldtime != secondsPlayed:
            killsdiff = k - oldstat["kills"]
            deathsdiff = d - oldstat["deaths"]
            winsdiff =  win - oldstat["wins"]
            lossesdiff = loss - oldstat["losses"]
            timediff = secondsPlayed - oldtime
            hsdiff = hs - oldstat["headshots"]
            roundsdiff = rounds - oldstat["rounds"]
            scorediff = score - oldstat["score"]
            updatetime_old = oldstat["updatetime"]
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
                "oldtime" : updatetime_old,
                "newtime" : updatetime_new
            }
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

            newdiff = json.dumps(newdiff)
            diff_info.append((pid,newdiff,newdiff))

        stats_info.append((pid,k,d,secondsPlayed,win,loss,rounds,hs,datetime.datetime.timestamp(datetime.datetime.now()),acc,score,k,d,secondsPlayed,win,loss,rounds,hs,datetime.datetime.timestamp(datetime.datetime.now()),acc,score))
        
    db_op_many(conn, 'INSERT INTO playerstats (pid, kills, deaths, playtimes, wins, losses, rounds, headshots, updatetime, acc, score) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (pid) DO UPDATE SET kills=%s, deaths=%s, playtimes=%s, wins=%s, losses=%s, rounds=%s, headshots=%s, updatetime=%s, acc=%s, score=%s', 
                stats_info)
    if diff_info != []:
        db_op_many(conn, 'INSERT INTO playerstatsdiff (pid, diff) VALUES(%s, %s) ON CONFLICT (pid) DO UPDATE SET diff=%s', diff_info)    

asyncio.run(refresh_statInfo())

# async def start_job():
#     scheduler = AsyncIOScheduler()
#     scheduler.add_job(refresh_statInfo, 'interval', hours=6)
#     scheduler.start()
#     try:
#         while True:
#             await asyncio.sleep(1)
#     except (KeyboardInterrupt, SystemExit):
#         scheduler.shutdown()

# if __name__ == '__main__':
#     asyncio.run(start_job())

async def update_diff(remid, sid, sessionID, pid):
    stats_old = [{'pid': r[0], 'kills': r[1], 'deaths': r[2], 'playtimes': r[3], 'wins': r[4], 'losses': r[5], 'rounds': r[6], 'headshots': r[7], 'updatetime': r[8], 'acc': r[9], 'score': r[10]} for r in db_op(conn, "SELECT * FROM playerstats WHERE pid=%s;", [pid])]
    diff_old = [{'pid': r[0], 'diff': r[1]} for r in db_op(conn, "SELECT * FROM playerstatsdiff WHERE pid=%s", [pid])]

    stats_info = []
    diff_info = []
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
    score = int(spm * secondsPlayed / 60)

    try:
        oldstat = stats_old[0]
        oldtime = oldstat["playtimes"]
    except:
        oldtime = secondsPlayed

    try:
        olddiff = diff_old[0]
    except:
        olddiff = {}
    newdiff = {}
    
    if oldtime != secondsPlayed:
        killsdiff = k - oldstat["kills"]
        deathsdiff = d - oldstat["deaths"]
        winsdiff =  win - oldstat["wins"]
        lossesdiff = loss - oldstat["losses"]
        timediff = secondsPlayed - oldtime
        hsdiff = hs - oldstat["headshots"]
        roundsdiff = rounds - oldstat["rounds"]
        scorediff = score - oldstat["score"]
        updatetime_old = oldstat["updatetime"]
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
            "oldtime" : updatetime_old,
            "newtime" : updatetime_new
        }
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

        newdiff_str = json.dumps(newdiff)
        diff_info.append((pid,newdiff_str,newdiff_str))

    stats_info.append((pid,k,d,secondsPlayed,win,loss,rounds,hs,datetime.datetime.timestamp(datetime.datetime.now()),acc,score,k,d,secondsPlayed,win,loss,rounds,hs,datetime.datetime.timestamp(datetime.datetime.now()),acc,score))
    
    db_op_many(conn, 'INSERT INTO playerstats (pid, kills, deaths, playtimes, wins, losses, rounds, headshots, updatetime, acc, score) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (pid) DO UPDATE SET kills=%s, deaths=%s, playtimes=%s, wins=%s, losses=%s, rounds=%s, headshots=%s, updatetime=%s, acc=%s, score=%s', 
                stats_info)
    if diff_info != []:
        db_op_many(conn, 'INSERT INTO playerstatsdiff (pid, diff) VALUES(%s, %s) ON CONFLICT (pid) DO UPDATE SET diff=%s', diff_info)     
    
    return newdiff

async def draw_re(remid, sid, sessionID, personaId, playerName):
    print("draw_re"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    tasks = []
    tasks.append(asyncio.create_task(upd_StatsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_Emblem(remid, sid, sessionID, personaId)))

    personaIds=[]
    personaIds.append(personaId)
    tasks.append(asyncio.create_task(upd_getActiveTagsByPersonaIds(remid,sid,sessionID,personaIds)))
    tasks.append(asyncio.create_task(update_diff(remid,sid,sessionID,personaId)))

    res_stat,emblem,res_tag,recent = await asyncio.gather(*tasks)

    name = playerName
    tag = res_tag['result'][f'{personaId}']
    kpm = res_stat['result']['basicStats']['kpm']
    win = res_stat['result']['basicStats']['wins']
    loss = res_stat['result']['basicStats']['losses']
    acc = res_stat['result']['accuracyRatio']
    hs = res_stat['result']['headShots']
    secondsPlayed = res_stat['result']['basicStats']['timePlayed']
    kd = res_stat['result']['kdr']
    k = res_stat['result']['basicStats']['kills']
    d = res_stat['result']['basicStats']['deaths']
    spm = res_stat['result']['basicStats']['spm']
    print("draw_re"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    
    if list(recent.values())[0]["k"] < 0:
        del recent["1"]
    recent = list(recent.values())
    try:
        emblem = emblem['result'].split('/')
    except:
        emblem = 'https://secure.download.dm.origin.com/production/avatar/prod/1/599/208x208.JPEG'
    else:
        try: 
            sta1 = emblem[7]
            sta2 = emblem[8]
            sta3 = emblem[9]
            sta4 = emblem[10].split('?')[1]
            emblem = 'https://eaassets-a.akamaihd.net/battlelog/bf-emblems/prod_default/ugc/'+sta1+'/'+sta2+'/'+sta3+'/256.png?'+sta4
        except:
            sta1 = emblem[6]
            sta2 = emblem[len(emblem)-1].split('.')[0]
            emblem = 'https://eaassets-a.akamaihd.net/battlelog/bf-emblems/prod_default/'+sta1+'/256/'+sta2+'.png'


    img = Image.open(Path('C:/Users/pengx/Desktop/1/bf1/bfchat_data/bf1_servers')/'Caches'/'background'/f'DLC1.jpg')
    img = img.resize((1300,1800))
    img = img.crop((0,0,1300,(170*len(recent)+300)))
    img = img.filter(ImageFilter.GaussianBlur(radius=15))

    textbox = Image.new("RGBA", (1300,250), (254, 238, 218, 180))
    draw = ImageDraw.Draw(textbox)
    font_1 = ImageFont.truetype(font='msyhbd.ttc', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    font_3 = ImageFont.truetype(font='comic.ttf', size=36, encoding='UTF-8')
    font_4 = ImageFont.truetype(font='Dengb.ttf', size=40, encoding='UTF-8')
    font_5 = ImageFont.truetype(font='Dengb.ttf', size=30, encoding='UTF-8')

    if tag == '':
        text=f'{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,5), text=text, fill=(55, 1, 27, 255),font=font_1)
    else:
        text=f'[{tag}]{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,5), text=text, fill=(55, 1, 27, 255),font=font_1)

    draw.text(xy=(290,80), text=f'游玩时长:{secondsPlayed//3600}小时', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(290,120), text=f'击杀数:{k}', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(290,160), text=f'死亡数:{d}', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(290,200), text=f'场均击杀:{0 if win+loss == 0 else round(k/(win+loss),1)}', fill=(66, 112, 244, 255),font=font_2)

    draw.text(xy=(680,80), text=f'获胜率:{0 if win+loss == 0 else win*100/(win+loss):.2f}%', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(680,120), text=f'命中率:{acc*100:.2f}%', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(680,160), text=f'爆头率:{0 if k == 0 else hs/k*100:.2f}%', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(680,200), text=f'场均死亡:{0 if win+loss == 0 else round(d/(win+loss),1)}', fill=(66, 112, 244, 255),font=font_2)
    
    draw.text(xy=(1070,80), text=f'等级:{getRank(spm,secondsPlayed)}', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(1070,120), text=f'KDA:{kd:.2f}', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(1070,160), text=f'KPM:{kpm}', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(1070,200), text=f'DPM:{0.0 if secondsPlayed == 0 else round((d*60)/secondsPlayed,2)}', fill=(66, 112, 244, 255),font=font_2)
    
    position = (0, 0)
    img.paste(textbox, position, textbox)
    
    await paste_emb(emblem,img,(0,0))

    if recent == None:
        return 0
    for i in range(len(recent)):
        textbox1 = Image.new("RGBA", (1300,170), (254, 238, 218, 180))
        draw = ImageDraw.Draw(textbox1)
        print(recent)
        time_played = recent[i]['time']
        if time_played < 60:
            time_play = f"{time_played}秒"
        elif time_played < 3600:
            time_play = f"{time_played // 60}分 {time_played % 60}秒"
        else:
            time_play = f"{time_played // 3600}时 {(time_played % 3600 ) // 60}分 {time_played % 60}秒"


        kill = recent[i]['k']
        death = recent[i]['d']
        
        formatted_dt = '数据记录时间: ' + datetime.datetime.fromtimestamp(recent[i]["newtime"]).strftime("%Y-%m-%d %H:%M:%S")
 
        draw.text(xy=((650-font_5.getsize(formatted_dt)[0]/2),20), text=formatted_dt, fill=(34,139,34, 255),font=font_5)

        draw.text(xy=(100,60), text=f'时长:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(210,60), text=f'{time_play}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(480,60), text=f'击杀:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(590,60), text=f'{recent[i]["k"]}', fill=(66, 112, 244, 255),font=font_4)
  
        draw.text(xy=(750,60), text=f'死亡:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(860,60), text=f'{recent[i]["d"]}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(1010,60), text=f'爆头:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1120,60), text=f'{recent[i]["hs"]}', fill=(66, 112, 244, 255),font=font_4)        
        
        draw.text(xy=(100,100), text=f'胜负:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(210,100), text=f'{recent[i]["w"]}W/{recent[i]["l"]}L ({recent[i]["w"] // recent[i]["round"] if recent[i]["round"] != 0 else 0} %)', fill=(66, 112, 244, 255),font=font_4)        
        draw.text(xy=(480,100), text=f'HS%:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(590,100), text=f'{round(recent[i]["hs"] * 100 / recent[i]["k"] if recent[i]["k"] !=0 else 0, 2)}%', fill=(66, 112, 244, 255),font=font_4)  

        draw.text(xy=(750,100), text=f'KDA:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(860,100), text=f'{round(recent[i]["k"] / recent[i]["d"] if recent[i]["d"] !=0 else 0, 2)}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(1010,100), text=f'KPM:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1120,100), text=f'{round(recent[i]["k"] * 60 / time_played, 2)}', fill=(66, 112, 244, 255),font=font_4)
        
        draw.text(xy=(0,150), text=f'-----------------------------------------------------------------------------------------------',fill=(55, 1, 27, 255), font=font_5)
        
        position = (0, 250+170*i)
        img.paste(textbox1,position,textbox1)

    textbox = Image.new("RGBA", (1300,50), (254, 238, 218, 180))
    img.paste(textbox,(0,170*len(recent)+250),textbox)

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],170*len(recent)+255), text=text ,fill=(34,139,34, 255),font=font_0)
    draw.line((0, 250, 1300, 250), fill=(55, 1, 27, 120), width=4)
    print("draw_re"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    return base64img(img)

