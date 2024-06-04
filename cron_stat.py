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

async def refresh_statInfo():
    time_start = time.time()
    conn = psycopg.connect(db_url)

    results = []

    pids = [r[0] for r in db_op(conn, "SELECT pid FROM players;", [])]
    
    stats_old = [{'pid': r[0], 'kills': r[1], 'deaths': r[2], 'playtimes': r[3], 'wins': r[4], 'losses': r[5], 'rounds': r[6], 'headshots': r[7], 'updatetime': r[8], 'acc': r[9], 'score': r[10], 'shot': r[11], 'hit': r[12]} for r in db_op(conn, "SELECT * FROM playerstats;", [])]
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
        pids_temp.append(pid)

        if len(pids_temp) == 100:
            cnt+=100
            print(f"开始获取战绩详细信息，共{len(pids_temp)}个，总进度{cnt}/{len(pids)}")
            results = await blaze_stat_renew(pids_temp)
            update_db(results,pids_temp,conn,stats_old_json,diff_old_json)
            
            pids_temp = []
            results = []

            await asyncio.sleep(1)

    if pids_temp:
        print(f"开始获取战绩详细信息，共{len(pids_temp)}个，总进度{len(pids)}/{len(pids)}")
        results = await blaze_stat_renew(pids_temp)
        update_db(results,pids_temp,conn,stats_old_json,diff_old_json)

    time_end = time.time()
    print(f'更新战绩用时: {time_end-time_start}')

def update_db(results,pids,conn,stats_old_json,diff_old_json):
    stats_info = []
    diff_info = []
    for pid in pids:
        try:
            (results0,results1) = results
            stat_list = results0[str(pid)]
            stat_list1 = results1[str(pid)]
        except Exception as e:
            print(e)
            continue

        k = int(float(stat_list[0]))
        d = int(float(stat_list[1]))
        hs = int(float(stat_list[2]))
        shot = int(float(stat_list[3]))
        hit = int(float(stat_list[4]))
        win = int(float(stat_list[5]))
        loss = int(float(stat_list[6]))
        acc = hit / shot if shot != 0 else 0
        rounds = win + loss
        
        score = int(float(stat_list1[0]))
        secondsPlayed = int(float(stat_list1[1])+float(stat_list1[2])+float(stat_list1[3])+float(stat_list1[4])+float(stat_list1[5])+float(stat_list1[6])+float(stat_list1[7])+float(stat_list1[8]))

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
        
        if oldtime < secondsPlayed:
            killsdiff = k - oldstat["kills"]
            deathsdiff = d - oldstat["deaths"]
            winsdiff =  win - oldstat["wins"]
            lossesdiff = loss - oldstat["losses"]
            timediff = secondsPlayed - oldtime
            hsdiff = hs - oldstat["headshots"]
            roundsdiff = rounds - oldstat["rounds"]
            scorediff = score - oldstat["score"]
            shotdiff = shot - oldstat["shot"]
            hitdiff = hit - oldstat["hit"]
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
                "shot" : shotdiff,
                "hit" : hitdiff,
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

        stats_info.append((pid,k,d,secondsPlayed,win,loss,rounds,hs,datetime.datetime.timestamp(datetime.datetime.now()),acc,score,shot,hit,k,d,secondsPlayed,win,loss,rounds,hs,datetime.datetime.timestamp(datetime.datetime.now()),acc,score,shot,hit))
        
    db_op_many(conn, 'INSERT INTO playerstats (pid, kills, deaths, playtimes, wins, losses, rounds, headshots, updatetime, acc, score, shot, hit) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (pid) DO UPDATE SET kills=%s, deaths=%s, playtimes=%s, wins=%s, losses=%s, rounds=%s, headshots=%s, updatetime=%s, acc=%s, score=%s, shot=%s, hit=%s', 
                stats_info)
    if diff_info != []:
        db_op_many(conn, 'INSERT INTO playerstatsdiff (pid, diff) VALUES(%s, %s) ON CONFLICT (pid) DO UPDATE SET diff=%s', diff_info)    

asyncio.run(refresh_statInfo())

async def start_job():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(refresh_statInfo, 'interval', hours=6)
    scheduler.start()
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == '__main__':
    asyncio.run(start_job())

