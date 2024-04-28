from PIL import Image, ImageDraw, ImageFilter, ImageFont
from sqlalchemy.future import select
import logging
import json
import random
import re
import os
import zhconv
import datetime
import asyncio
from io import BytesIO
from .bf1rsp import *
from .bf1helper import search_all, upd_cache_StatsByPersonaId, update_diff
from .utils import *
from .image import *
from .secret import *
from .rdb import async_db_session, GroupMembers, GroupServerBind
from base64 import b64encode

GAME = 'bf1'
LANG = 'zh-tw'

def base64img(img) -> str:
    buf = BytesIO()
    img.save(buf,'png')
    img_stream = buf.getvalue()
    return 'base64://' + b64encode(img_stream).decode('ascii')

async def paste_exchange(url:str,img,position,size):
    if url.split("/")[-1] in os.listdir(BF1_SERVERS_DATA/"Caches"/"Skins"):
        image = Image.open(BF1_SERVERS_DATA/"Caches"/"Skins"/url.split("/")[-1])
        image = image.resize(size)
    else:
        response = await httpx_client.get(url,timeout=20)
        image_data = response.content
        image = Image.open(BytesIO(image_data))
        image.save(BF1_SERVERS_DATA/"Caches"/"Skins"/url.split("/")[-1])
        image = image.resize(size)
    img.paste(image,position,image)

async def paste_emb(url,img,position):
    if f'{url.split("=")[-1]}.png' in os.listdir(BF1_PLAYERS_DATA/"Emblem"):
        image = Image.open(BF1_PLAYERS_DATA/"Emblem"/f'{url.split("=")[-1]}.png')
        try:
            img.paste(image,position,image)
        except:
            img.paste(image,position)
    else:
        if url.endswith('.JPEG') or url.endswith('.png'):
            if url.split("/")[-1] in os.listdir(BF1_PLAYERS_DATA/"Emblem"):
                image = Image.open(BF1_PLAYERS_DATA/"Emblem"/url.split("/")[-1])
                try:
                    img.paste(image,position,image)
                except:
                    img.paste(image,position)
            else:
                try:
                    response = await httpx_client.get(url,timeout=5)
                    image_data = response.content
                    image = Image.open(BytesIO(image_data)).resize((250,250))     
                    image.save(BF1_PLAYERS_DATA/"Emblem"/url.split("/")[-1])
                    try:
                        img.paste(image,position,image)
                    except:
                        img.paste(image,position)
                except:
                    pass
        else:
            try:
                response = await httpx_client.get(url,timeout=5)
                image_data = response.content
                image = Image.open(BytesIO(image_data)).resize((250,250)).convert("RGBA")
                image.save(BF1_PLAYERS_DATA/"Emblem"/f'{url.split("=")[-1]}.png')
                try:
                    img.paste(image,position,image)
                except:
                    img.paste(image,position)
            except:
                pass


async def draw_f(server_inds: list, server_gameids: list, groupqq: int, remid: str, sid: str, sessionID: str):
    tasks = [asyncio.create_task(upd_detailedServer(remid, sid, sessionID, gameId)) for gameId in server_gameids]
    ress = []
    server_num = len(server_gameids)
    # 打开图片文件
    img = Image.open(BF1_SERVERS_DATA/f'Caches/background/DLC{random.randint(2, 6)}.jpg')
    img = img.resize((1506,400*server_num+100))

    un = 0
    # 将原始图片模糊化
    img = img.filter(ImageFilter.GaussianBlur(radius=15))    
    ress = await asyncio.gather(*tasks, return_exceptions=True)
    
    for id in range(server_num):
        server_ind = server_inds[id]
        try:
            res =  ress[id]
            servername = res['result']['serverInfo']['name']
            servermap = res['result']['serverInfo']['mapNamePretty']
            serveramount = res['result']['serverInfo']['slots']['Soldier']['current']
            serverspect = res['result']['serverInfo']['slots']['Spectator']['current']
            serverque = res['result']['serverInfo']['slots']['Queue']['current']
            servermaxamount = res['result']['serverInfo']['slots']['Soldier']['max']
            servermode = res['result']['serverInfo']['mapModePretty']
            serverstar = res['result']['serverInfo']['serverBookmarkCount']
            serverinfo = '简介：' + res['result']['serverInfo']['description']
            serverimg = res['result']['serverInfo']['mapImageUrl'].split('/')[-1]
            serverimg = BF1_SERVERS_DATA/f'Caches/Maps/{serverimg}'
        except:
           un += 1
           continue

        status1 = servermode + '-' +servermap
        status2 = f'{serveramount}/{servermaxamount}[{serverque}]({serverspect})'
        status3 = f'★{serverstar}'

        # 创建一个矩形图形
        textbox0 = Image.new("RGBA", (1386,80), (0, 0, 0, 255))
        textbox = Image.new("RGBA", (1386,300), (0, 0, 0, 200))

        # 在矩形图形上添加文字
        draw0 = ImageDraw.Draw(textbox0)
        draw = ImageDraw.Draw(textbox)
        font_1 = ImageFont.truetype(font='comic.ttf', size=44, encoding='UTF-8')
        font_2 = ImageFont.truetype(font='msyhbd.ttc', size=44, encoding='UTF-8')
        font_3 = ImageFont.truetype(font='msyhbd.ttc', size=28, encoding='UTF-8')
        font_4 = ImageFont.truetype(font='comic.ttf', size=72, encoding='UTF-8')
        draw0.text(xy=(80,8), text=f'[{server_ind}] ' + servername, fill=(255, 255, 255, 255),font=font_1)
        draw.text(xy=(560,10), text=zhconv.convert(status1,"zh-cn"), fill=(255, 255, 0, 200),font=font_2)
        draw.text(xy=(1160,10), text=status3, fill=(0, 255, 255, 200),font=font_2)
        draw.text(xy=(500,40), text='------------------------------------------------------', fill=(0, 255, 0, 100),font=font_1)
        if int(servermaxamount) - int(serveramount) < 10:
            draw.text(xy=(960,125), text=status2, fill=(0, 255, 0, 255),font=font_4)
        else:
            draw.text(xy=(960,125), text=status2, fill=(255, 150, 0, 255),font=font_4)

        result = ""
        text = ""
        for i in serverinfo:
            if font_3.getsize(text)[0] <= 350:
                text += i
                result += i
            else:
                result += i + "\n"
                text = ""
        result = zhconv.convert(result,"zh-cn")

        for i in range(len(result.split('\n'))):
            draw.text(xy=(520,90+i*40), text=result.split('\n')[i], fill=(255, 255, 255, 255),font=font_3)
            if i == 4:
                break

        # 将矩形图形添加到原始图片的指定位置
        position0 = (60, 60+400*(id-un))
        position = (60, 140+400*(id-un))
        img.paste(textbox0, position0, textbox0)
        img.paste(textbox, position, textbox)

        background = Image.open(serverimg).resize((480,300))
        img.paste(background, position)
    server_num -= un
    img = img.crop((0,0,1506,400*server_num+100))

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],400*server_num+65), text=text ,fill=(255, 255, 0, 255),font=font_0)
    
    return base64img(img)

async def draw_server(remid, sid, sessionID, serverName, res):
    img = Image.open(BF1_SERVERS_DATA/f'Caches/background/DLC{random.randint(2, 6)}.jpg')
    img = img.resize((1506,2100))
    img = img.filter(ImageFilter.GaussianBlur(radius=15))

    res = res['result']['gameservers']
    res = sorted(res, key=lambda x: x['slots']['Soldier']['current'],reverse=True)
    if (len(res)) <5:
        if len(res) == 0:
            return 0
        else:
            img = img.crop((0,0,1506,400*len(res)+100))
    tasks = []
    for ij in range(len(res)):   
        gameId = res[ij]['gameId']
        tasks.append(asyncio.create_task(upd_detailedServer(remid, sid, sessionID, gameId)))

    ress = await asyncio.gather(*tasks, return_exceptions=True)

    for ij in range(len(res)):
        servername = res[ij]['name']
        servermap = res[ij]['mapNamePretty']
        serveramount = res[ij]['slots']['Soldier']['current']
        serverspect = res[ij]['slots']['Spectator']['current']
        serverque = res[ij]['slots']['Queue']['current']
        servermaxamount = res[ij]['slots']['Soldier']['max']
        servermode = res[ij]['mapModePretty']
        #serverstar = res[i]['serverBookmarkCount']
        serverinfo = '简介：' + res[ij]['description']
        serverimg = res[ij]['mapImageUrl'].split('/')[-1]
        serverimg = BF1_SERVERS_DATA/f'Caches/Maps/{serverimg}'
        res_0 = ress[ij]
        serverstar = None if isinstance(res_0, Exception) else res_0['result']['serverInfo']['serverBookmarkCount']

        status1 = servermode + '-' +servermap
        status2 = f'{serveramount}/{servermaxamount}[{serverque}]({serverspect})'
        status3 = f'★{serverstar}'

        # 创建一个矩形图形
        textbox0 = Image.new("RGBA", (1386,80), (0, 0, 0, 255))
        textbox = Image.new("RGBA", (1386,300), (0, 0, 0, 200))

        # 在矩形图形上添加文字
        draw0 = ImageDraw.Draw(textbox0)
        draw = ImageDraw.Draw(textbox)
        font_1 = ImageFont.truetype(font='comic.ttf', size=44, encoding='UTF-8')
        font_2 = ImageFont.truetype(font='msyhbd.ttc', size=44, encoding='UTF-8')
        font_3 = ImageFont.truetype(font='msyhbd.ttc', size=28, encoding='UTF-8')
        font_4 = ImageFont.truetype(font='comic.ttf', size=72, encoding='UTF-8')
        draw0.text(xy=(80,8), text=servername, fill=(255, 255, 255, 255),font=font_1)
        draw.text(xy=(560,10), text=zhconv.convert(status1,"zh-cn"), fill=(255, 255, 0, 200),font=font_2)
        draw.text(xy=(1160,10), text=status3, fill=(0, 255, 255, 200),font=font_2)
        draw.text(xy=(500,40), text='------------------------------------------------------', fill=(0, 255, 0, 100),font=font_1)
        if int(servermaxamount) - int(serveramount) < 10:
            draw.text(xy=(960,125), text=status2, fill=(0, 255, 0, 255),font=font_4)
        else:
            draw.text(xy=(960,125), text=status2, fill=(255, 150, 0, 255),font=font_4)
        
        result = ""
        text = ""
        for i in serverinfo:
            if font_3.getsize(text)[0] <= 350:
                text += i
                result += i
            else:
                result += i + "\n"
                text = ""
        result = zhconv.convert(result,"zh-cn")

        for i in range(len(result.split('\n'))):
            draw.text(xy=(520,90+i*40), text=result.split('\n')[i], fill=(255, 255, 255, 255),font=font_3)
            if i == 4:
                break

        # 将矩形图形添加到原始图片的指定位置
        position0 = (60, 400*ij+60)
        position = (60, 140+400*ij)
        img.paste(textbox0, position0, textbox0)
        img.paste(textbox, position, textbox)

        background = Image.open(serverimg).resize((480,300))
        img.paste(background, position)

        if ij == 4:
            break
    

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],400*len(res)+65), text=text ,fill=(255, 255, 0, 255),font=font_0)
    
    return base64img(img)

def paste_img(img:Image):
    data = img.getdata()
    new_data = []
    for item in data:
        if item[3] == 0:
            new_data.append(item)
        else:
            new_data.append((255 - item[0], 255 - item[1], 255 - item[2], item[3]))
    img.putdata(new_data)
    return img

async def draw_stat(remid, sid, sessionID,personaId:int,playerName:str):
    tasks = []
    
    tasks.append(asyncio.create_task(upd_blazestat(personaId,'s3')))
    tasks.append(asyncio.create_task(upd_cache_StatsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_WeaponsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_VehiclesByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_Emblem(remid, sid, sessionID, personaId)))

    personaIds=[]
    personaIds.append(personaId)
    tasks.append(asyncio.create_task(upd_getActiveTagsByPersonaIds(remid,sid,sessionID,personaIds)))
    tasks.append(asyncio.create_task(bfeac_checkBan(personaId)))
    tasks.append(asyncio.create_task(upd_loadout(remid, sid, sessionID, personaId)))

    ress = await asyncio.gather(*tasks, return_exceptions=True)
    for res in ress:
        if isinstance(res, Exception):
            raise res
    special_stat1,res_stat,res_weapon,res_vehicle,emblem,res_tag,bfeac,res_pre = ress
    special_stat = await upd_blazestat(personaId,'s5')
    
    name = playerName
    tag = res_tag['result'][f'{personaId}']
    skill = res_stat['result']['basicStats']['skill']
    spm = res_stat['result']['basicStats']['spm']
    kpm = res_stat['result']['basicStats']['kpm']
    win = res_stat['result']['basicStats']['wins']
    loss = res_stat['result']['basicStats']['losses']
    
    bestClass= res_stat['result']['favoriteClass']
    acc = res_stat['result']['accuracyRatio']
    hs = res_stat['result']['headShots']
    secondsPlayed = res_stat['result']['basicStats']['timePlayed']
    kd = res_stat['result']['kdr']
    k = res_stat['result']['basicStats']['kills']
    d = res_stat['result']['basicStats']['deaths']
    longhs = res_stat['result']['longestHeadShot']
    rev = res_stat['result']['revives']
    dogtags = res_stat['result']['dogtagsTaken']
    ks = res_stat['result']["highestKillStreak"]
    avenge = res_stat['result']["avengerKills"]
    save = res_stat['result']["saviorKills"]
    heals = res_stat['result']["heals"]
    repairs = res_stat['result']["repairs"]
    killAssists = res_stat['result']["killAssists"]

    owner,ban,admin,vip = await search_all(personaId)


    gamemode = sorted(res_stat['result']['gameModeStats'], key=lambda x: x['score'],reverse=True)
    gamemodes = []
    for i in gamemode:
        if i['prettyName'] == '閃擊行動':
            continue
        else:
            gamemodes.append(i)

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

    vehicles = sorted(res_vehicle['result'], key=lambda x: x['stats']['values']['kills'],reverse=True)
    
    weapons = []
    for i in res_weapon['result']:
        for j in i['weapons']:
            try: 
                kill = j['stats']['values']['kills']
                weapons.append(j)
            except:
                pass
    try:
        dict_AS,dict_PK,dict_BD1,dict_BD2 = special_stat_to_dict(special_stat)
        dict_FL = special_stat_to_dict1(special_stat1)
        weapons.append(dict_AS)
        weapons.append(dict_PK)
        weapons.append(dict_BD1)
        weapons.append(dict_BD2)
        weapons.append(dict_FL)
    except:
        pass
    weapons = sorted(weapons, key=lambda x: x['stats']['values']['kills'],reverse=True)

    carkill = 0
    cartime = 0
    for i in vehicles:
        carkill = carkill + i['stats']['values']['kills']
        cartime = cartime + i['stats']['values']['seconds']
    try:
        carkp = round((carkill*60 / cartime),2)
    except:
        carkp = 0

    infantrykill = k - carkill
    infantrytime = secondsPlayed - cartime

    try:
        infantrykp = round((infantrykill*60 / infantrytime),2)
    except:
        infantrykp = 0

    json_class = {
        'Medic': '医疗兵',
        'Support': '支援兵',
        'Assault': '突击兵',
        'Scout': '侦察兵',
        'Cavalry': '骑兵',
        'Pilot': '飞行员',
        'Tanker': '坦克'
    }

    try:
        img = Image.open(BF1_PLAYERS_DATA/'Caches'/f'{personaId}.jpg')
    except:
        if bfeac["stat"] == "已封禁":
            img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'ban.jpg')     
        else:
            img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC{random.randint(2, 6)}.jpg')

    
    img = img.resize((1500,1500))

    textbox = Image.new("RGBA", (1300,250), (0, 0, 0, 100))
    draw = ImageDraw.Draw(textbox)
    font_1 = ImageFont.truetype(font='msyhbd.ttc', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    if tag == '':
        text=f'{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,5), text=text, fill=(255, 255, 0, 255),font=font_1)
    else:
        text=f'[{tag}]{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,5), text=text, fill=(255, 255, 0, 255),font=font_1)

    draw.text(xy=(290,80), text=f'游玩时长:{secondsPlayed//3600}小时', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(290,120), text=f'击杀数:{k}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(290,160), text=f'死亡数:{d}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(290,200), text=f'场均击杀:{0 if win+loss == 0 else round(k/(win+loss),1)}', fill=(255, 255, 255, 255),font=font_2)

    draw.text(xy=(680,80), text=f'获胜率:{0 if win+loss == 0 else win*100/(win+loss):.2f}%', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,120), text=f'命中率:{acc*100:.2f}%', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,160), text=f'爆头率:{0 if k == 0 else hs/k*100:.2f}%', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,200), text=f'场均死亡:{0 if win+loss == 0 else round(d/(win+loss),1)}', fill=(255, 255, 255, 255),font=font_2)
    
    draw.text(xy=(1070,80), text=f'等级:{getRank(spm,secondsPlayed)}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(1070,120), text=f'KDA:{kd:.2f}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(1070,160), text=f'KPM:{kpm}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(1070,200), text=f'DPM:{0.0 if secondsPlayed == 0 else round((d*60)/secondsPlayed,2)}', fill=(255, 255, 255, 255),font=font_2)

    position = (100, 100)
    img.paste(textbox, position, textbox)

    textbox1 = Image.new("RGBA", (640,675), (0, 0, 0, 100))
    draw = ImageDraw.Draw(textbox1)
    font_3 = ImageFont.truetype(font='Dengb.ttf', size=45, encoding='UTF-8')
    font_4 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    draw.text(xy=(120,30), text=f'最佳兵种:    {json_class[bestClass]}', fill=(255, 255, 255, 255),font=font_3)

    draw.text(xy=(35,95), text=f'最远爆头:{longhs}m', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,139), text=f'最高连杀:{ks}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,183), text=f'协助击杀:{int(killAssists)}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,227), text=f'复仇击杀:{avenge}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,271), text=f'救星击杀:{save}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,315), text=f'拥有服务器:{owner}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,359), text=f'管理服务器:{admin}', fill=(255, 255, 255, 255),font=font_4)

    draw.text(xy=(360,95), text=f'技巧值:{skill}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,139), text=f'狗牌数:{dogtags}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,183), text=f'救援数:{int(rev)}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,227), text=f'治疗数:{int(heals)}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,271), text=f'修理数:{int(repairs)}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,315), text=f'vip数量:{vip}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,359), text=f'ban数量:{ban}', fill=(255, 255, 255, 255),font=font_4)

    smallmode = gamemodes[2]["wins"]+gamemodes[2]["losses"]+gamemodes[3]["wins"]+gamemodes[3]["losses"]+gamemodes[4]["wins"]+gamemodes[4]["losses"]+gamemodes[5]["wins"]+gamemodes[5]["losses"]+gamemodes[6]["wins"]+gamemodes[6]["losses"]
    
    try:
        smwp = ((gamemodes[2]["wins"]+gamemodes[3]["wins"]+gamemodes[4]["wins"]+gamemodes[5]["wins"]+gamemodes[6]["wins"])*100) / smallmode
        draw.text(xy=(360,491), text=f'其他胜率:{smwp:.2f}%', fill=(255, 255, 255, 255),font=font_4)
    except:
        smwp = 0
        draw.text(xy=(360,491), text=f'其他胜率:{smwp:.1f}%', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,403), text=f'{gamemodes[0]["prettyName"][0:2]}场次:{gamemodes[0]["wins"]+gamemodes[0]["losses"]}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,447), text=f'{gamemodes[1]["prettyName"][0:2]}场次:{gamemodes[1]["wins"]+gamemodes[1]["losses"]}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,491), text=f'其他场次:{smallmode}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,536), text=f'步兵击杀:{int(infantrykill)}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,580), text=f'载具击杀:{int(carkill)}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,624), text=f'BFEAC状态:{bfeac["stat"]}', fill=(255, 255, 255, 255),font=font_4)

    draw.text(xy=(360,403), text=f'{gamemodes[0]["prettyName"][0:2]}胜率:{(100*gamemodes[0]["winLossRatio"])/(1+gamemodes[0]["winLossRatio"]):.2f}%', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,447), text=f'{gamemodes[1]["prettyName"][0:2]}胜率:{(100*gamemodes[1]["winLossRatio"])/(1+gamemodes[1]["winLossRatio"]):.2f}%', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,536), text=f'步兵KPM:{infantrykp}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,580), text=f'载具KPM:{carkp}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,624), text=f'SPM:{spm}', fill=(255, 255, 255, 255),font=font_4)

    position1 = (100, 380)
    img.paste(textbox1, position1, textbox1)

    textbox3 = Image.new("RGBA", (640,330), (0, 0, 0, 100))
    draw = ImageDraw.Draw(textbox3)
    font_5 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    font_6 = ImageFont.truetype(font='Dengb.ttf', size=30, encoding='UTF-8')
    draw.text(xy=(80,150), text=f'{zhconv.convert(vehicles[0]["name"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
    kill1 = int(vehicles[0]['stats']['values']['kills'])
    star = kill1 // 100  #★{serverstar

    try:
        vkp = round(kill1*60/vehicles[0]['stats']['values']['seconds'],2)
    except:
        vkp = 0.00
    draw.text(xy=(10,177), text=f'----------------------------------', fill=(255, 255, 255, 150),font=font_5)
    draw.text(xy=(80,225), text=f'击杀:{kill1}', fill=(255, 255, 255, 255),font=font_5)
    draw.text(xy=(80,270), text=f"KPM:{vkp}", fill=(255, 255, 255, 255),font=font_5)
    draw.text(xy=(380,225), text=f"摧毁:{int(vehicles[0]['stats']['values']['destroyed'])}", fill=(255, 255, 255, 255),font=font_5)
    draw.text(xy=(380,270), text=f"时间:{(int(vehicles[0]['stats']['values']['seconds'])/3600):.1f}h", fill=(255, 255, 255, 255),font=font_5)
    position3 = (100, 1070)
 
    if star < 50:
        draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 255, 255),font=font_5)
    elif star < 100:
        draw.text(xy=(10,10), text=f'★{star}', fill=(0, 255, 0, 255),font=font_5)
    else:
        draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 0, 255),font=font_5)
   
    try:
        skin_name,skin_url,skin_rare = getVehicleSkin(zhconv.convert(vehicles[0]["name"],"zh-cn"),res_pre)
        text = zhconv.convert(skin_name,"zh-cn")

        if skin_rare == 0:
            draw.text(xy=(630-font_6.getsize(text)[0],10), text=text, fill=(255, 255, 255, 255),font=font_6)
        elif skin_rare == 1:
            draw.text(xy=(630-font_6.getsize(text)[0],10), text=text, fill=(0, 255, 255, 255),font=font_6)
        elif skin_rare == 2:
            draw.text(xy=(630-font_6.getsize(text)[0],10), text=text, fill=(255, 255, 0, 255),font=font_6)
        img.paste(textbox3, position3, textbox3)
        await paste_exchange(skin_url,img,(220, 1100),(400,100))
    
    except:
        img.paste(textbox3, position3, textbox3)

        vehicles_img = BF1_SERVERS_DATA/'Caches'/'Weapons'/f'{vehicles[0]["vehicles"][0]["imageUrl"].split("/")[-1]}'
        img_vehicles = Image.open(vehicles_img).resize((400,100)).convert("RGBA")
        img.paste(paste_img(img_vehicles), (220, 1100), img_vehicles)
    

    for i in range(3):
        textbox3 = Image.new("RGBA", (640,330), (0, 0, 0, 100))
        draw = ImageDraw.Draw(textbox3)
        draw.text(xy=(80,150), text=f'{zhconv.convert(weapons[i]["name"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
        kill1 = int(weapons[i]['stats']['values']['kills'])
        star = kill1 // 100 #★{serverstar

        try:
            acc = (weapons[i]['stats']['values']['hits']*100) / (weapons[i]['stats']['values']['shots'])
        except:
            acc = 0.00
        
        try:
            eff = (weapons[i]['stats']['values']['hits']) / (weapons[i]['stats']['values']['kills'])
        except:
            eff = 0.00

        try:
            wkp = (weapons[i]['stats']['values']['kills']*60) / (weapons[i]['stats']['values']['seconds'])
        except:
            wkp = 0.00

        try:
            whs = (weapons[i]['stats']['values']['headshots']*100) / (weapons[i]['stats']['values']['kills'])
        except:
            whs = 0.00
        draw.text(xy=(10,177), text=f'----------------------------------', fill=(255, 255, 255, 150),font=font_5)
        draw.text(xy=(80,210), text=f'击杀:{kill1}\nKPM:{wkp:.2f}\n命中:{acc:.2f}%', fill=(255, 255, 255, 255),font=font_5)
        draw.text(xy=(380,210), text=f'效率:{eff:.2f}\n爆头:{whs:.2f}%\n时间:{((int(weapons[i]["stats"]["values"]["seconds"]))/3600):.1f}h', fill=(255, 255, 255, 255),font=font_5)

        position3 = (760, 380+i*345)
        
        if star < 50:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 255, 255),font=font_5)
        elif star < 100:
            draw.text(xy=(10,10), text=f'★{star}', fill=(0, 255, 0, 255),font=font_5)
        else:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 0, 255),font=font_5) 

        try:
            skin_name,skin_url,skin_rare = getWeaponSkin(zhconv.convert(weapons[i]["name"],"zh-cn"),res_pre)
            text = zhconv.convert(skin_name,"zh-cn")

            if skin_rare == 0:
                draw.text(xy=(630-font_6.getsize(text)[0],10), text=text, fill=(255, 255, 255, 255),font=font_6)
            elif skin_rare == 1:
                draw.text(xy=(630-font_6.getsize(text)[0],10), text=text, fill=(0, 255, 255, 255),font=font_6)
            elif skin_rare == 2:
                draw.text(xy=(630-font_6.getsize(text)[0],10), text=text, fill=(255, 255, 0, 255),font=font_6)

            img.paste(textbox3, position3, textbox3)
            await paste_exchange(skin_url,img,(880, 345*i+410),(400,100))
        except:
              
            img.paste(textbox3, position3, textbox3)        

            wp_img = BF1_SERVERS_DATA/'Caches'/'Weapons'/f'{weapons[i]["imageUrl"].split("/")[-1]}'
            img_wp = Image.open(wp_img).resize((400,100)).convert("RGBA")
            img.paste(paste_img(img_wp), (880, 345*i+410), img_wp)

    img_class = Image.open(BF1_SERVERS_DATA/f'Caches/Classes/{bestClass}.png').resize((45,45)).convert("RGBA")
    img.paste(paste_img(img_class), (415, 409), img_class)
    
    await paste_emb(emblem,img,(100,100))

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    a,b,c = img.getpixel((1490,1490))
    draw.text(xy=(img.width-font_0.getsize(text)[0],1465), text=text ,fill=(a+128 if a<128 else a-128, b+128 if b<128 else b-128, c+128 if c<128 else c-128, 255),font=font_0)
 
    return base64img(img)

#draw_f(4,248966716,remid, sid, sessionID)

async def draw_wp(remid, sid, sessionID, personaId, playerName:str, mode:int, col, row):
    tasks = []

    tasks.append(asyncio.create_task(upd_blazestat(personaId,'s3')))
    tasks.append(asyncio.create_task(upd_cache_StatsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_WeaponsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_VehiclesByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_Emblem(remid, sid, sessionID, personaId)))

    personaIds=[]
    personaIds.append(personaId)
    tasks.append(asyncio.create_task(upd_getActiveTagsByPersonaIds(remid,sid,sessionID,personaIds)))

    tasks.append(asyncio.create_task(upd_loadout(remid, sid, sessionID, personaId)))

    ress = await asyncio.gather(*tasks, return_exceptions=True)
    for res in ress:
        if isinstance(res, Exception):
            raise res
    special_stat1,res_stat,res_weapon,res_vehicle,emblem,res_tag,res_pre = ress
    special_stat = await upd_blazestat(personaId,'s5')
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
    
    try:
        img = Image.open(BF1_PLAYERS_DATA/'Caches'/f'{personaId}.jpg')
    except:    
        img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC{random.randint(2, 6)}.jpg')

    if 655*col-10 <= 340*row+300:
        img = img.resize((340*row+300,340*row+300))
        img = img.crop((170*row+150-327.5*col+5,0,170*row+150+327.5*col-5,340*row+300))
    else:        
        img = img.resize((655*col-10,655*col-10))
        img = img.crop((0,327.5*col-5-170*row-150,655*col-10,327.5*col-5+170*row+150))

    textbox = Image.new("RGBA", (1300,250), (0, 0, 0, 100))
    draw = ImageDraw.Draw(textbox)
    font_1 = ImageFont.truetype(font='msyhbd.ttc', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    font_4 = ImageFont.truetype(font='Dengb.ttf', size=30, encoding='UTF-8')
    font_5 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    if tag == '':
        text=f'{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,5), text=text, fill=(255, 255, 0, 255),font=font_1)
    else:
        text=f'[{tag}]{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,5), text=text, fill=(255, 255, 0, 255),font=font_1)

    draw.text(xy=(290,80), text=f'游玩时长:{secondsPlayed//3600}小时', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(290,120), text=f'击杀数:{k}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(290,160), text=f'死亡数:{d}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(290,200), text=f'场均击杀:{0 if win+loss == 0 else round(k/(win+loss),1)}', fill=(255, 255, 255, 255),font=font_2)

    draw.text(xy=(680,80), text=f'获胜率:{0 if win+loss == 0 else win*100/(win+loss):.2f}%', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,120), text=f'命中率:{acc*100:.2f}%', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,160), text=f'爆头率:{0 if k == 0 else hs/k*100:.2f}%', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,200), text=f'场均死亡:{0 if win+loss == 0 else round(d/(win+loss),1)}', fill=(255, 255, 255, 255),font=font_2)
    
    draw.text(xy=(1070,80), text=f'等级:{getRank(spm,secondsPlayed)}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(1070,120), text=f'KDA:{kd:.2f}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(1070,160), text=f'KPM:{kpm}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(1070,200), text=f'DPM:{0.0 if secondsPlayed == 0 else round((d*60)/secondsPlayed,2)}', fill=(255, 255, 255, 255),font=font_2)

    position = (0, 0)
    img.paste(textbox, position, textbox)

    weapons = []
    for i in res_weapon['result']:
        for j in i['weapons']:
            try: 
                kill = j['stats']['values']['kills']
                weapons.append(j)
            except:
                pass
    try:
        dict_AS,dict_PK,dict_BD1,dict_BD2 = special_stat_to_dict(special_stat)
        dict_FL = special_stat_to_dict1(special_stat1)
        weapons.append(dict_AS)
        weapons.append(dict_PK)
        weapons.append(dict_BD1)
        weapons.append(dict_BD2)
        weapons.append(dict_FL)
    except:
        pass
    weapons = sorted(weapons, key=lambda x: x['stats']['values']['kills'],reverse=True)

    vehicles = []
    for i in range(len(res_vehicle['result'])):
        if i != 6 and i != 7 and i != 8:
            for j in res_vehicle['result'][i]['vehicles']:
                try: 
                    kill = j['stats']['values']['kills']
                    vehicles.append(j)
                except:
                    pass
        
    vehicles = sorted(vehicles, key=lambda x: x['stats']['values']['kills'],reverse=True) 

    if mode < 17:
        mode_1 = []
        mode_2 = []
        mode_3 = []
        mode_4 = []
        mode_5 = []
        mode_6 = []
        mode_7 = []
        mode_8 = []
        mode_9 = []
        mode_10 = []
        mode_11 = []
        mode_12 = []
        mode_13 = []
        mode_14 = []
        mode_15 = []
        mode_16 = []        

        for i in weapons:
            match i['category']:
                case '戰場裝備':
                    mode_1.append(i)
                case '配備':
                    mode_2.append(i)
                    if i['name'] == "炸藥" or i['name'] == "反坦克火箭砲" or i['name'] == "防空火箭砲" or i['name'] == "反坦克地雷" or i['name'] == "反坦克手榴彈":
                        mode_13.append(i)
                    elif i['name'] == "迫擊砲（空爆）" or i['name'] == "迫擊砲（高爆）" or i['name'] == "維修工具" or i['name'] == "磁吸地雷" or i['name'] == "十字弓發射器（高爆）" or i['name'] == "十字弓發射器（破片）":
                        mode_14.append(i)
                    elif i['name'] == "絆索炸彈（高爆）" or i['name'] == "絆索炸彈（燃燒）" or i['name'] == "絆索炸彈（毒氣）" or i['name'] == "信號槍（閃光）" or i['name'] == "信號槍（偵察）" or i['name'] == "K 彈":
                        mode_15.append(i)
                    elif i['name'] == "醫療用針筒":
                        mode_16.append(i)                    
                case '半自動步槍':
                    mode_3.append(i)
                    mode_16.append(i)
                case '霰彈槍':
                    mode_4.append(i)
                    mode_13.append(i)
                case '佩槍':
                    mode_5.append(i)
                    if i['name'] == "加塞 M1870" or i['name'] == "Howdah 手槍" or i['name'] == "1903 Hammerless":
                        mode_13.append(i)
                    elif i['name'] == "Repetierpistole M1912" or i['name'] == "Modello 1915" or i['name'] == "鬥牛犬左輪手槍":
                        mode_14.append(i)
                    elif i['name'] == "Mars 自動手槍" or i['name'] == "Bodeo 1889" or i['name'] == "費羅梅爾停止手槍":
                        mode_15.append(i)
                    elif i['name'] == "自動左輪手槍" or i['name'] == "C96" or i['name'] == "Taschenpistole M1914":
                        mode_16.append(i)
                case '輕機槍':
                    mode_6.append(i)
                    mode_14.append(i)
                case '近戰武器':
                    if i['name'] == '奇兵棒':
                        mode_1.append(i)
                    mode_7.append(i)
                case '步槍':
                    mode_8.append(i)
                    mode_15.append(i)
                case '坦克/駕駛員':
                    mode_9.append(i)
                case '手榴彈':
                    mode_10.append(i)
                    if i['name'] == "步槍手榴彈（破片）" or i['name'] == "步槍手榴彈（煙霧）" or i['name'] == "步槍手榴彈（高爆）":
                        mode_2.append(i)
                        mode_16.append(i)                    
                case '制式步槍':
                    mode_11.append(i)
                case '衝鋒槍':
                    mode_12.append(i)
                    mode_13.append(i)

        match mode:
            case 0:
                weapons = weapons
            case 1:
                weapons = mode_1   
            case 2:
                weapons = mode_2
            case 3:
                weapons = mode_3
            case 4:
                weapons = mode_4
            case 5:
                weapons = mode_5
            case 6:
                weapons = mode_6
            case 7:
                weapons = mode_7
            case 8:
                weapons = mode_8
            case 9:
                weapons = mode_9
            case 10:
                weapons = mode_10
            case 11:
                weapons = mode_11
            case 12:
                weapons = mode_12
            case 13:
                weapons = mode_13
            case 14:
                weapons = mode_14
            case 15:
                weapons = mode_15
            case 16:
                weapons = mode_16
        weapons = sorted(weapons, key=lambda x: x['stats']['values']['kills'],reverse=True)
    else:
        attack = {
            "name": "攻击机",
            "imageUrl": "https://eaassets-a.akamaihd.net/battlelog/battlebinary/gamedata/Tunguska/63/53/GERHalberstadtCLII-c1cb8257.png",
            "stats": res_vehicle['result'][6]['stats']
        }

        bomber = {
            "name": "轰炸机",
            "imageUrl": "https://eaassets-a.akamaihd.net/battlelog/battlebinary/gamedata/Tunguska/84/65/GERGothaGIV-54bfb0bf.png",
            "stats": res_vehicle['result'][7]['stats']
        }

        fight = {
            "name": "战斗机",
            "imageUrl": "https://eaassets-a.akamaihd.net/battlelog/battlebinary/gamedata/Tunguska/113/96/FRA_SPAD_X_XIII-8f60a194.png",
            "stats": res_vehicle['result'][8]['stats']
        }

        vehicles.append(attack)
        vehicles.append(bomber)
        vehicles.append(fight)
        
        weapons = sorted(vehicles, key=lambda x: x['stats']['values']['kills'],reverse=True)

    for i in range(min(row*col,len(weapons))):
        textbox4 = Image.new("RGBA", (645,190), (255, 255, 255, 255))
        position3 = (655*(i%col), 260+(i//col)*340)
        #img.paste(textbox4, position3, textbox4)

        textbox3 = Image.new("RGBA", (645,330), (0, 0, 0, 100))
        draw = ImageDraw.Draw(textbox3)

        kill1 = int(weapons[i]['stats']['values']['kills'])
        star = kill1 // 100 #★{serverstar

        try:
            acc = (weapons[i]['stats']['values']['hits']*100) / (weapons[i]['stats']['values']['shots'])
        except:
            acc = 0.00
        
        try:
            eff = (weapons[i]['stats']['values']['hits']) / (weapons[i]['stats']['values']['kills'])
        except:
            eff = 0.00

        try:
            wkp = (weapons[i]['stats']['values']['kills']*60) / (weapons[i]['stats']['values']['seconds'])
        except:
            wkp = 0.00

        try:
            whs = (weapons[i]['stats']['values']['headshots']*100) / (weapons[i]['stats']['values']['kills'])
        except:
            whs = 0.00
        
        wtime = int(weapons[i]['stats']['values']['seconds'])/3600
        if mode == 17:
            draw.text(xy=(80,150), text=f'{zhconv.convert(weapons[i]["name"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(10,177), text=f'-----------------------------------', fill=(255, 255, 255, 150),font=font_5)
            draw.text(xy=(80,225), text=f'击杀:{kill1}', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(80,270), text=f"KPM:{wkp:.2f}", fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(380,225), text=f"摧毁:{int(weapons[i]['stats']['values']['destroyed'])}", fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(380,270), text=f"时间:{wtime:.1f}h", fill=(255, 255, 255, 255),font=font_5)
        else:
            draw.text(xy=(80,150), text=f'{zhconv.convert(weapons[i]["name"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(10,177), text=f'----------------------------------', fill=(255, 255, 255, 150),font=font_5)
            draw.text(xy=(80,210), text=f'击杀:{kill1}\nKPM:{wkp:.2f}\n命中:{acc:.2f}%', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(380,210), text=f'效率:{eff:.2f}\n爆头:{whs:.2f}%\n时间:{wtime:.1f}h', fill=(255, 255, 255, 255),font=font_5)
        
        if star < 50:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 255, 255),font=font_5)
        elif star < 100:
            draw.text(xy=(10,10), text=f'★{star}', fill=(0, 255, 0, 255),font=font_5)
        else:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 0, 255),font=font_5)
        
        try:
            if mode == 17:
                skin_name,skin_url,skin_rare = getVehicleSkin(zhconv.convert(weapons[i]["name"],"zh-cn"),res_pre)
            else:
                skin_name,skin_url,skin_rare = getWeaponSkin(zhconv.convert(weapons[i]["name"],"zh-cn"),res_pre)
            
            text = zhconv.convert(skin_name,"zh-cn")
            
            if skin_rare == 0:
                draw.text(xy=(635-font_4.getsize(text)[0],10), text=text, fill=(255, 255, 255, 255),font=font_4)
            elif skin_rare == 1:
                draw.text(xy=(635-font_4.getsize(text)[0],10), text=text, fill=(0, 255, 255, 255),font=font_4)
            elif skin_rare == 2:
                draw.text(xy=(630-font_4.getsize(text)[0],10), text=text, fill=(255, 255, 0, 255),font=font_4)

            img.paste(textbox3, position3, textbox3)
            await paste_exchange(skin_url,img,(130+650*(i%col), 340*(i//col)+300),(400,100))
        except: 
                          
            img.paste(textbox3, position3, textbox3)
            wp_img = BF1_SERVERS_DATA/'Caches'/'Weapons'/f'{weapons[i]["imageUrl"].split("/")[-1]}'
            img_wp = Image.open(wp_img).resize((400,100)).convert("RGBA")
            img.paste(paste_img(img_wp), (130+650*(i%col), 340*(i//col)+300), img_wp)

    await paste_emb(emblem,img,(0,0))

    textbox = Image.new("RGBA", (img.width,40), (0, 0, 0, 100))
    draw = ImageDraw.Draw(textbox)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],20-font_0.getsize(text)[1]/2), text=text ,fill=(255, 255, 0, 255),font=font_0)
    img.paste(textbox, (0,340*row+260), textbox)

    return base64img(img)

async def draw_pl2(groupqq: int, server_ind: str, server_id: int, gameId: int, 
                   remid: str, sid: str, sessionID: str, message_id: int = None) -> str:
    """
    Draw playerlist of a server and cache the data into redis. (Version 2)
    
    server_id: serverId of Battlefield servers, not group server index
    """
    pljson = await get_blazeplbyid(remid,sid,sessionID,gameId)
    detailedServer = await upd_detailedServer(remid, sid, sessionID, gameId)
    vipList = detailedServer['result']["rspInfo"]['vipList']
    adminList = detailedServer['result']["rspInfo"]['adminList']
    adminList.append(detailedServer['result']['rspInfo']['owner'])

    async with async_db_session() as session:
        server_row = (await session.execute(select(GroupServerBind).filter_by(groupqq=groupqq, serverid=server_id))).first()
        whiteList = []
        if server_row:
            if server_row[0].whitelist:
                whiteList_pid = server_row[0].whitelist.split(',')
                wl_json = await upd_getPersonasByIds(remid, sid, sessionID, whiteList_pid)
                if 'error' in wl_json:
                    logging.debug('Whitelist query failed')
                else:
                    whiteList = [value['displayName'] for value in wl_json['result'].values()]
        else:
            logging.debug('whitelist not found')

        member_row = (await session.execute(select(GroupMembers).filter_by(groupqq=groupqq))).all()
        personaIds = [r[0].pid for r in member_row]
        member_json = await upd_getPersonasByIds(remid, sid, sessionID,personaIds)
        if 'error' in member_json:
            memberList = []
            logging.debug('memberList query failed')
        else:
            member_json = member_json['result']
            memberList = [value['displayName'] for value in member_json.values()]

    serverimg = detailedServer['result']['serverInfo']['mapImageUrl'].split('/')[5]
    serverimg = BF1_SERVERS_DATA/f'Caches/Maps/{serverimg}'
    serverName = detailedServer['result']['serverInfo']['name']

    teamImage_1 = pljson['team1']
    teamImage_2 = pljson['team2']

    logging.info("draw_pl1"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    stat1 = sorted(pljson['1'], key=lambda x: x['rank'],reverse=True)
    stat2 = sorted(pljson['2'], key=lambda x: x['rank'],reverse=True)
    stat3 = sorted(pljson['spec'], key=lambda x: x['rank'],reverse=True)
    stat4 = sorted(pljson['queue'], key=lambda x: x['rank'],reverse=True)

    h = 1217
    if len(stat3) != 0:
        h += (30*((len(stat3)+1)//2) + 10)
    if len(stat4) != 0:
        h += (30*((len(stat4)+1)//2) + 10)

    img = Image.open(serverimg)
    img = img.resize((1920,h))
    img = img.filter(ImageFilter.GaussianBlur(radius=10))
    textbox0 = Image.new("RGBA", (1920,h), (0, 0, 0, 150))
    img.paste(textbox0, (0, 0), textbox0)

    textbox = Image.new("RGBA", (900,1200), (0, 0, 0, 0))
    teamimg = Image.open(BF1_SERVERS_DATA/f'Caches/Teams/{teamImage_1}.png').resize((80,80)).convert("RGBA")
    try:
        textbox.paste(teamimg,(0,0),teamimg)
    except:
        textbox.paste(teamimg,(0,0))
    draw = ImageDraw.Draw(textbox)

    font_1 = ImageFont.truetype(font='comic.ttf', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
    font_3 = ImageFont.truetype(font='Dengb.ttf', size=20, encoding='UTF-8')


    num_150 = 0
    levelall = 0
    kdall = 0
    kpall = 0
    for i in stat1:
        if i['rank'] == 150:
            num_150 +=1
        levelall += i['rank']
        kdall += i['killDeath']
        kpall += i['killsPerMinute']
    try:
        avlevel = levelall // len(stat1)
        avkd = ((kdall*100) // len(stat1)) / 100
        avkp = ((kpall*100) // len(stat1)) / 100
    except:
        avlevel = avkd = avkp = 0
    
    draw.text(xy=(100,15), text=f'150数量: {num_150}\n平均等级: {avlevel}' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(298,15), text=f'平均kd: {avkd}\n平均kp: {avkp}' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(410,27.5), text=f'            KD    KP     爆头       胜率    时长' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(865,27.5), text=f'语' ,fill=(255, 255, 255, 255),font=font_2)
    
    f = {"pl": []}
    for i in range(len(stat1)):
        draw.text(xy=(22.5-font_2.getsize(f'{i+1}')[0]/2,90+30*i), text=f'{i+1}' , fill =(255, 255,255, 255),font=font_2)
        if stat1[i]['rank'] < 50:
            draw.rectangle([(60, 94+30*i), (100, 112+30*i)], fill=(0, 255, 255, 100))
        elif stat1[i]['rank'] < 100:
            draw.rectangle([(60, 94+30*i), (100, 112+30*i)], fill=(0, 255, 0, 100))
        elif stat1[i]['rank'] < 150:
            draw.rectangle([(60, 94+30*i), (100, 112+30*i)], fill=(255, 255, 0, 100))
        else:
            draw.rectangle([(60, 94+30*i), (100, 112+30*i)], fill=(255, 0, 0, 150))
        
        text_width, _ = font_3.getsize(str(stat1[i]['rank']))
        x = 80 - text_width / 2
        y = 93 + 30*i
        draw.text((x, y), str(stat1[i]['rank']), fill=(255, 255, 255, 255), font=font_3)
        
        result1 = [item for item in adminList if item['displayName'] == stat1[i]["userName"]]
        result2 = [item for item in whiteList if item == stat1[i]["userName"]]        
        result3 = [item for item in vipList if item['displayName'] == stat1[i]["userName"]]
        result4 = [item for item in memberList if item == stat1[i]["userName"]]
        
        if result1 == []:
            if result2 == []:
                if result3 == []:
                    if result4 == []:
                        if stat1[i]['platoon'] == "":
                            draw.text(xy=(110,90+30*i), text=f'{stat1[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(110,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                    else:
                        if stat1[i]['platoon'] == "":
                            draw.text(xy=(110,90+30*i), text=f'{stat1[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(110,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                else:
                    if stat1[i]['platoon'] == "":
                        draw.text(xy=(110,90+30*i), text=f'{stat1[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                    else:
                        draw.text(xy=(110,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
            else:
                if stat1[i]['platoon'] == "":
                    draw.text(xy=(110,90+30*i), text=f'{stat1[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
                else:
                    draw.text(xy=(110,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
        else:
            if stat1[i]['platoon'] == "":
                draw.text(xy=(110,90+30*i), text=f'{stat1[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
            else:
                draw.text(xy=(110,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)

        if stat1[i]['killDeath'] > 2.5:
            draw.text(xy=(485,90+30*i), text=f'{stat1[i]["killDeath"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat1[i]['killDeath'] > 1:
            draw.text(xy=(485,90+30*i), text=f'{stat1[i]["killDeath"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(485,90+30*i), text=f'{stat1[i]["killDeath"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if stat1[i]['killsPerMinute'] > 2.5:
            draw.text(xy=(549,90+30*i), text=f'{stat1[i]["killsPerMinute"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat1[i]['killsPerMinute'] > 1:
            draw.text(xy=(549,90+30*i), text=f'{stat1[i]["killsPerMinute"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(549,90+30*i), text=f'{stat1[i]["killsPerMinute"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat1[i]['headShot'].strip('%')) / 100  > 0.2:
            draw.text(xy=(617,90+30*i), text=f'{stat1[i]["headShot"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat1[i]['headShot'].strip('%')) / 100 > 0.05:
            draw.text(xy=(617,90+30*i), text=f'{stat1[i]["headShot"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(617,90+30*i), text=f'{stat1[i]["headShot"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat1[i]['winPercent'].strip('%')) / 100 > 0.7:
            draw.text(xy=(710,90+30*i), text=f'{stat1[i]["winPercent"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat1[i]['winPercent'].strip('%')) / 100 > 0.4:
            draw.text(xy=(710,90+30*i), text=f'{stat1[i]["winPercent"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(710,90+30*i), text=f'{stat1[i]["winPercent"]}' ,fill=(173, 216, 255, 255),font=font_2)

        draw.text(xy=(800,90+30*i), text=f'{int(stat1[i]["secondsPlayed"])//3600}' ,fill=(255, 255, 255, 255),font=font_2)
        draw.text(xy=(865,90+30*i), text=f'{stat1[i]["loc"]}' ,fill=(255, 255, 255, 255),font=font_2)
        
        f['pl'].append({'slot': i+1, 'rank': stat1[i]['rank'], 'kd': stat1[i]['killDeath'], 'kp': stat1[i]['killsPerMinute'], 'id': stat1[i]['id'], 'name': stat1[i]["userName"]})
    
    position = (60, 110)
    img.paste(textbox, position, textbox)

    textbox1 = Image.new("RGBA", (900,1200), (0, 0, 0, 0))
    teamimg = Image.open(BF1_SERVERS_DATA/f'Caches/Teams/{teamImage_2}.png').resize((80,80)).convert("RGBA")
    try:
        textbox1.paste(teamimg,(0,0),teamimg)
    except:
        textbox1.paste(teamimg,(0,0))
    draw = ImageDraw.Draw(textbox1)

    num_150 = 0
    levelall = 0
    kdall = 0
    kpall = 0
    for i in stat2:
        if i['rank'] == 150:
            num_150 +=1
        levelall += i['rank']
        kdall += i['killDeath']
        kpall += i['killsPerMinute']
    try:
        avlevel = levelall // len(stat2)
        avkd = ((kdall*100) // len(stat2)) / 100
        avkp = ((kpall*100) // len(stat2)) / 100
    except:
        avlevel = avkd = avkp = 0
    
    draw.text(xy=(100,15), text=f'150数量: {num_150}\n平均等级: {avlevel}' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(298,15), text=f'平均kd: {avkd}\n平均kp: {avkp}' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(410,27.5), text=f'            KD    KP     爆头       胜率    时长' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(865,27.5), text=f'语' ,fill=(255, 255, 255, 255),font=font_2)
    
    for i in range(len(stat2)):
        draw.text(xy=(22.5-font_2.getsize(f'{i+33}')[0]/2,90+30*i), text=f'{i+33}' , fill =(255, 255,255, 255),font=font_2)
        if stat2[i]['rank'] < 50:
            draw.rectangle([(60, 94+30*i), (100, 112+30*i)], fill=(0, 255, 255, 100))
        elif stat2[i]['rank'] < 100:
            draw.rectangle([(60, 94+30*i), (100, 112+30*i)], fill=(0, 255, 0, 100))
        elif stat2[i]['rank'] < 150:
            draw.rectangle([(60, 94+30*i), (100, 112+30*i)], fill=(255, 255, 0, 100))
        else:
            draw.rectangle([(60, 94+30*i), (100, 112+30*i)], fill=(255, 0, 0, 150))
        
        text_width, _ = font_3.getsize(str(stat2[i]['rank']))
        x = 80 - text_width / 2
        y = 93 + 30*i
        draw.text((x, y), str(stat2[i]['rank']), fill=(255, 255, 255, 255), font=font_3)
        
        result1 = [item for item in adminList if item['displayName'] == stat2[i]["userName"]]
        result2 = [item for item in whiteList if item == stat2[i]["userName"]]        
        result3 = [item for item in vipList if item['displayName'] == stat2[i]["userName"]]
        result4 = [item for item in memberList if item == stat2[i]["userName"]]
        
        if result1 == []:
            if result2 == []:
                if result3 == []:
                    if result4 == []:
                        if stat2[i]['platoon'] == "":
                            draw.text(xy=(110,90+30*i), text=f'{stat2[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(110,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                    else:
                        if stat2[i]['platoon'] == "":
                            draw.text(xy=(110,90+30*i), text=f'{stat2[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(110,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                else:
                    if stat2[i]['platoon'] == "":
                        draw.text(xy=(110,90+30*i), text=f'{stat2[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                    else:
                        draw.text(xy=(110,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
            else:
                if stat2[i]['platoon'] == "":
                    draw.text(xy=(110,90+30*i), text=f'{stat2[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
                else:
                    draw.text(xy=(110,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
        else:
            if stat2[i]['platoon'] == "":
                draw.text(xy=(110,90+30*i), text=f'{stat2[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
            else:
                draw.text(xy=(110,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)

        if stat2[i]['killDeath'] > 2.5:
            draw.text(xy=(485,90+30*i), text=f'{stat2[i]["killDeath"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat2[i]['killDeath'] > 1:
            draw.text(xy=(485,90+30*i), text=f'{stat2[i]["killDeath"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(485,90+30*i), text=f'{stat2[i]["killDeath"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if stat2[i]['killsPerMinute'] > 2.5:
            draw.text(xy=(549,90+30*i), text=f'{stat2[i]["killsPerMinute"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat2[i]['killsPerMinute'] > 1:
            draw.text(xy=(549,90+30*i), text=f'{stat2[i]["killsPerMinute"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(549,90+30*i), text=f'{stat2[i]["killsPerMinute"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat2[i]['headShot'].strip('%')) / 100  > 0.2:
            draw.text(xy=(617,90+30*i), text=f'{stat2[i]["headShot"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat2[i]['headShot'].strip('%')) / 100 > 0.05:
            draw.text(xy=(617,90+30*i), text=f'{stat2[i]["headShot"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(617,90+30*i), text=f'{stat2[i]["headShot"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat2[i]['winPercent'].strip('%')) / 100 > 0.7:
            draw.text(xy=(710,90+30*i), text=f'{stat2[i]["winPercent"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat2[i]['winPercent'].strip('%')) / 100 > 0.4:
            draw.text(xy=(710,90+30*i), text=f'{stat2[i]["winPercent"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(710,90+30*i), text=f'{stat2[i]["winPercent"]}' ,fill=(173, 216, 255, 255),font=font_2)

        draw.text(xy=(800,90+30*i), text=f'{int(stat2[i]["secondsPlayed"])//3600}' ,fill=(255, 255, 255, 255),font=font_2)
        draw.text(xy=(865,90+30*i), text=f'{stat2[i]["loc"]}' ,fill=(255, 255, 255, 255),font=font_2)

        f['pl'].append({'slot': i+33, 'rank': stat2[i]['rank'], 'kd': stat2[i]['killDeath'], 'kp': stat2[i]['killsPerMinute'], 'id': stat2[i]['id'], 'name': stat2[i]["userName"]})
    
    position = (960, 110)
    img.paste(textbox1, position, textbox1)

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
    text = f'普通玩家  群友  vip  白名单  管理  65-67为观战玩家  69-78为排队玩家  Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    x = (img.width-font_0.getsize(text)[0])/2

    draw.text(xy=((img.width-font_1.getsize(serverName)[0])/2,30), text=serverName ,fill=(255, 255, 255, 255),font=font_1)
    draw.text(xy=((img.width-font_0.getsize(text)[0])/2,h-40), text='普通玩家' ,fill=(255, 255, 255, 255),font=font_0)
    draw.text(xy=(x+125,h-40), text='群友' ,fill=(0, 255, 255, 255),font=font_0)
    draw.text(xy=(x+200,h-40), text='vip' ,fill=(255, 125, 125, 255),font=font_0)
    draw.text(xy=(x+262.5,h-40), text='白名单' ,fill=(0, 255, 0, 255),font=font_0)
    draw.text(xy=(x+362.5,h-40), text='管理' ,fill=(255, 255, 0, 255),font=font_0)
    draw.text(xy=(x+437.5,h-40), text='65-68为观战玩家' ,fill=(255, 125, 0, 255),font=font_0)
    draw.text(xy=(x+460+font_0.getsize('65-68为观战玩家')[0],h-40), text='69-78为排队玩家' ,fill=(255, 100, 255, 255),font=font_0)
    draw.text(xy=(x+470+font_0.getsize('69-78为排队玩家  69-78为排队玩家')[0],h-40), text= f'Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',fill=(125, 125, 255, 255),font=font_0)
    
    draw.line((60, 190, 1860, 190), fill=(128, 128, 128, 120), width=4)
    draw.line((60, 1165, 1860, 1165), fill=(128, 128, 128, 120), width=4)

    draw.line((60, 190, 60, h-50), fill=(128, 128, 128, 120), width=4)
    draw.line((105, 190, 105, h-50), fill=(128, 128, 128, 120), width=4)
    draw.line((960, 190, 960, h-50), fill=(128, 128, 128, 120), width=4)
    draw.line((1005, 190, 1005, h-50), fill=(128, 128, 128, 120), width=4)
    draw.line((1860, 190, 1860, h-50), fill=(128, 128, 128, 120), width=4)
    
    if len(stat3) != 0:
        textbox2 = Image.new("RGBA", (1800,40+30*(len(stat3)//2)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(textbox2)
        for i in range(len(stat3)):
            draw.text(xy=(22.5-font_2.getsize(f'{i+33}')[0]/2+900*(i%2),30*(i//2)), text=f'{i+65}' , fill =(255, 255,255, 255),font=font_2)
            if stat3[i]['rank'] < 50:
                draw.rectangle([(60+900*(i%2), 4+30*(i//2)), (100+900*(i%2), 22+30*(i//2))], fill=(0, 255, 255, 100))
            elif stat3[i]['rank'] < 100:
                draw.rectangle([(60+900*(i%2), 4+30*(i//2)), (100+900*(i%2), 22+30*(i//2))], fill=(0, 255, 0, 100))
            elif stat3[i]['rank'] < 150:
                draw.rectangle([(60+900*(i%2), 4+30*(i//2)), (100+900*(i%2), 22+30*(i//2))], fill=(255, 255, 0, 100))
            else:
                draw.rectangle([(60+900*(i%2), 4+30*(i//2)), (100+900*(i%2), 22+30*(i//2))], fill=(255, 0, 0, 150))
            
            text_width, _ = font_3.getsize(str(stat3[i]['rank']))
            x = 80 - text_width / 2 +900*(i%2)
            y = 3 + 30*(i//2)
            draw.text((x, y), str(stat3[i]['rank']), fill=(255, 255, 255, 255), font=font_3)
            
            result1 = [item for item in adminList if item['displayName'] == stat3[i]["userName"]]
            result2 = [item for item in whiteList if item == stat3[i]["userName"]]        
            result3 = [item for item in vipList if item['displayName'] == stat3[i]["userName"]]
            result4 = [item for item in memberList if item == stat3[i]["userName"]]
            
            if result1 == []:
                if result2 == []:
                    if result3 == []:
                        if result4 == []:
                            if stat3[i]['platoon'] == "":
                                draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat3[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                            else:
                                draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat3[i]["platoon"]}]{stat3[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                        else:
                            if stat3[i]['platoon'] == "":
                                draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat3[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                            else:
                                draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat3[i]["platoon"]}]{stat3[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                    else:
                        if stat3[i]['platoon'] == "":
                            draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat3[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                        else:
                            draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat3[i]["platoon"]}]{stat3[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                else:
                    if stat3[i]['platoon'] == "":
                        draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat3[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
                    else:
                        draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat3[i]["platoon"]}]{stat3[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
            else:
                if stat3[i]['platoon'] == "":
                    draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat3[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
                else:
                    draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat3[i]["platoon"]}]{stat3[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)

            if stat3[i]['killDeath'] > 2.5:
                draw.text(xy=(485+900*(i%2),30*(i//2)), text=f'{stat3[i]["killDeath"]}' ,fill=(255, 255, 0, 255),font=font_2)
            elif stat3[i]['killDeath'] > 1:
                draw.text(xy=(485+900*(i%2),30*(i//2)), text=f'{stat3[i]["killDeath"]}' ,fill=(255, 255, 255, 255),font=font_2)
            else:
                draw.text(xy=(485+900*(i%2),30*(i//2)), text=f'{stat3[i]["killDeath"]}' ,fill=(173, 216, 255, 255),font=font_2)

            if stat3[i]['killsPerMinute'] > 2.5:
                draw.text(xy=(549+900*(i%2),30*(i//2)), text=f'{stat3[i]["killsPerMinute"]}' ,fill=(255, 255, 0, 255),font=font_2)
            elif stat3[i]['killsPerMinute'] > 1:
                draw.text(xy=(549+900*(i%2),30*(i//2)), text=f'{stat3[i]["killsPerMinute"]}' ,fill=(255, 255, 255, 255),font=font_2)
            else:
                draw.text(xy=(549+900*(i%2),30*(i//2)), text=f'{stat3[i]["killsPerMinute"]}' ,fill=(173, 216, 255, 255),font=font_2)

            if float(stat3[i]['headShot'].strip('%')) / 100  > 0.2:
                draw.text(xy=(617+900*(i%2),30*(i//2)), text=f'{stat3[i]["headShot"]}' ,fill=(255, 255, 0, 255),font=font_2)
            elif float(stat3[i]['headShot'].strip('%')) / 100 > 0.05:
                draw.text(xy=(617+900*(i%2),30*(i//2)), text=f'{stat3[i]["headShot"]}' ,fill=(255, 255, 255, 255),font=font_2)
            else:
                draw.text(xy=(617+900*(i%2),30*(i//2)), text=f'{stat3[i]["headShot"]}' ,fill=(173, 216, 255, 255),font=font_2)

            if float(stat3[i]['winPercent'].strip('%')) / 100 > 0.7:
                draw.text(xy=(710+900*(i%2),30*(i//2)), text=f'{stat3[i]["winPercent"]}' ,fill=(255, 255, 0, 255),font=font_2)
            elif float(stat3[i]['winPercent'].strip('%')) / 100 > 0.4:
                draw.text(xy=(710+900*(i%2),30*(i//2)), text=f'{stat3[i]["winPercent"]}' ,fill=(255, 255, 255, 255),font=font_2)
            else:
                draw.text(xy=(710+900*(i%2),30*(i//2)), text=f'{stat3[i]["winPercent"]}' ,fill=(173, 216, 255, 255),font=font_2)

            draw.text(xy=(800+900*(i%2),30*(i//2)), text=f'{int(stat3[i]["secondsPlayed"])//3600}' ,fill=(255, 255, 255, 255),font=font_2)
            draw.text(xy=(865+900*(i%2),30*(i//2)), text=f'{stat3[i]["loc"]}' ,fill=(255, 255, 255, 255),font=font_2)

            f['pl'].append({'slot': i+65, 'rank': stat3[i]['rank'], 'kd': stat3[i]['killDeath'], 'kp': stat3[i]['killsPerMinute'], 'id': stat3[i]['id'], 'name': stat3[i]["userName"]})
        
        draw.line((0, 32+30*(i//2), 1860, 32+30*(i//2)), fill=(128, 128, 128, 255), width=4)
        img.paste(textbox2, (60,1176), textbox2)

    if len(stat4) != 0:
        textbox2 = Image.new("RGBA", (1800,40+30*(len(stat4)//2)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(textbox2)
        for i in range(len(stat4)):
            draw.text(xy=(22.5-font_2.getsize(f'{i+69}')[0]/2+900*(i%2),30*(i//2)), text=f'{i+69}' , fill =(255, 255,255, 255),font=font_2)
            if stat4[i]['rank'] < 50:
                draw.rectangle([(60+900*(i%2), 4+30*(i//2)), (100+900*(i%2), 22+30*(i//2))], fill=(0, 255, 255, 100))
            elif stat4[i]['rank'] < 100:
                draw.rectangle([(60+900*(i%2), 4+30*(i//2)), (100+900*(i%2), 22+30*(i//2))], fill=(0, 255, 0, 100))
            elif stat4[i]['rank'] < 150:
                draw.rectangle([(60+900*(i%2), 4+30*(i//2)), (100+900*(i%2), 22+30*(i//2))], fill=(255, 255, 0, 100))
            else:
                draw.rectangle([(60+900*(i%2), 4+30*(i//2)), (100+900*(i%2), 22+30*(i//2))], fill=(255, 0, 0, 150))
            
            text_width, _ = font_3.getsize(str(stat4[i]['rank']))
            x = 80 - text_width / 2 +900*(i%2)
            y = 3 + 30*(i//2)
            draw.text((x, y), str(stat4[i]['rank']), fill=(255, 255, 255, 255), font=font_3)
            
            result1 = [item for item in adminList if item['displayName'] == stat4[i]["userName"]]
            result2 = [item for item in whiteList if item == stat4[i]["userName"]]        
            result3 = [item for item in vipList if item['displayName'] == stat4[i]["userName"]]
            result4 = [item for item in memberList if item == stat4[i]["userName"]]
            
            if result1 == []:
                if result2 == []:
                    if result3 == []:
                        if result4 == []:
                            if stat4[i]['platoon'] == "":
                                draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat4[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                            else:
                                draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat4[i]["platoon"]}]{stat4[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                        else:
                            if stat4[i]['platoon'] == "":
                                draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat4[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                            else:
                                draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat4[i]["platoon"]}]{stat4[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                    else:
                        if stat4[i]['platoon'] == "":
                            draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat4[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                        else:
                            draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat4[i]["platoon"]}]{stat4[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                else:
                    if stat4[i]['platoon'] == "":
                        draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat4[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
                    else:
                        draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat4[i]["platoon"]}]{stat4[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
            else:
                if stat4[i]['platoon'] == "":
                    draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'{stat4[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
                else:
                    draw.text(xy=(110+900*(i%2),30*(i//2)), text=f'[{stat4[i]["platoon"]}]{stat4[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)

            if stat4[i]['killDeath'] > 2.5:
                draw.text(xy=(485+900*(i%2),30*(i//2)), text=f'{stat4[i]["killDeath"]}' ,fill=(255, 255, 0, 255),font=font_2)
            elif stat4[i]['killDeath'] > 1:
                draw.text(xy=(485+900*(i%2),30*(i//2)), text=f'{stat4[i]["killDeath"]}' ,fill=(255, 255, 255, 255),font=font_2)
            else:
                draw.text(xy=(485+900*(i%2),30*(i//2)), text=f'{stat4[i]["killDeath"]}' ,fill=(173, 216, 255, 255),font=font_2)

            if stat4[i]['killsPerMinute'] > 2.5:
                draw.text(xy=(549+900*(i%2),30*(i//2)), text=f'{stat4[i]["killsPerMinute"]}' ,fill=(255, 255, 0, 255),font=font_2)
            elif stat4[i]['killsPerMinute'] > 1:
                draw.text(xy=(549+900*(i%2),30*(i//2)), text=f'{stat4[i]["killsPerMinute"]}' ,fill=(255, 255, 255, 255),font=font_2)
            else:
                draw.text(xy=(549+900*(i%2),30*(i//2)), text=f'{stat4[i]["killsPerMinute"]}' ,fill=(173, 216, 255, 255),font=font_2)

            if float(stat4[i]['headShot'].strip('%')) / 100  > 0.2:
                draw.text(xy=(617+900*(i%2),30*(i//2)), text=f'{stat4[i]["headShot"]}' ,fill=(255, 255, 0, 255),font=font_2)
            elif float(stat4[i]['headShot'].strip('%')) / 100 > 0.05:
                draw.text(xy=(617+900*(i%2),30*(i//2)), text=f'{stat4[i]["headShot"]}' ,fill=(255, 255, 255, 255),font=font_2)
            else:
                draw.text(xy=(617+900*(i%2),30*(i//2)), text=f'{stat4[i]["headShot"]}' ,fill=(173, 216, 255, 255),font=font_2)

            if float(stat4[i]['winPercent'].strip('%')) / 100 > 0.7:
                draw.text(xy=(710+900*(i%2),30*(i//2)), text=f'{stat4[i]["winPercent"]}' ,fill=(255, 255, 0, 255),font=font_2)
            elif float(stat4[i]['winPercent'].strip('%')) / 100 > 0.4:
                draw.text(xy=(710+900*(i%2),30*(i//2)), text=f'{stat4[i]["winPercent"]}' ,fill=(255, 255, 255, 255),font=font_2)
            else:
                draw.text(xy=(710+900*(i%2),30*(i//2)), text=f'{stat4[i]["winPercent"]}' ,fill=(173, 216, 255, 255),font=font_2)

            draw.text(xy=(800+900*(i%2),30*(i//2)), text=f'{int(stat4[i]["secondsPlayed"])//3600}' ,fill=(255, 255, 255, 255),font=font_2)
            draw.text(xy=(865+900*(i%2),30*(i//2)), text=f'{stat4[i]["loc"]}' ,fill=(255, 255, 255, 255),font=font_2)
            
            f['pl'].append({'slot': i+69, 'rank': stat4[i]['rank'], 'kd': stat4[i]['killDeath'], 'kp': stat4[i]['killsPerMinute'], 'id': stat4[i]['id'], 'name': stat4[i]["userName"]})
        
        draw.line((0, 32+30*(i//2), 1860, 32+30*(i//2)), fill=(128, 128, 128, 255), width=4)
        img.paste(textbox2, (60,1176 if len(stat3)==0 else 1176+10+30*((len(stat3)+1)//2)), textbox2)
    
    f['pl'].append({'slot': 100, 'rank': 0, 'kd': 0, 'kp': 0, 'id': 0, 'name': None})
    f['serverid'] = server_id
    f['serverind'] = server_ind

    logging.info("draw_pl2"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    return base64img(img), json.dumps(f)

async def draw_r(remid, sid, sessionID, personaId, playerName):
    print("draw_r"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    tasks = []
    tasks.append(asyncio.create_task(upd_cache_StatsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_Emblem(remid, sid, sessionID, personaId)))

    personaIds=[]
    personaIds.append(personaId)
    tasks.append(asyncio.create_task(upd_getActiveTagsByPersonaIds(remid,sid,sessionID,personaIds)))
    tasks.append(asyncio.create_task(upd_report(playerName, personaId, 10)))

    ress = await asyncio.gather(*tasks, return_exceptions=True)
    for res in ress:
        if isinstance(res, Exception):
            raise res
    res_stat,emblem,res_tag,async_result = ress

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
    print("draw_r"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

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

    recent = []
    count = 0
    if 'player not found' in async_result["data"]:
        return 0
    else:
        for data in async_result["data"]:
            try:
                if data['kills'] > 2 or data['deaths'] > 2:
                    recent.append(data)
                    count += 1
                    if count == 3:
                        break
            except:
                continue

    try:
        img = Image.open(BF1_PLAYERS_DATA/'Caches'/f'{personaId}.jpg') 
        img = img.resize((1800,1800))
        img = img.crop((250,0,1550,(410*len(recent)+410)))
    except:    
        img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC1.jpg')
        img = img.resize((1300,1800))
        img = img.crop((0,0,1300,(410*len(recent)+410)))
        img = img.filter(ImageFilter.GaussianBlur(radius=15))

    textbox = Image.new("RGBA", (1300,250), (254, 238, 218, 180))
    draw = ImageDraw.Draw(textbox)
    font_1 = ImageFont.truetype(font='msyhbd.ttc', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    font_3 = ImageFont.truetype(font='comic.ttf', size=36, encoding='UTF-8')
    font_4 = ImageFont.truetype(font='Dengb.ttf', size=40, encoding='UTF-8')
    font_5 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
    
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
    
    timeall = 0
    killall = 0
    deathall = 0
    Scoreall = 0

    with open(BF1_SERVERS_DATA/'zh-cn.json', 'r',encoding='UTF-8') as f:
        dict = json.load(f)
    for i in range(len(recent)):
        textbox0 = Image.new("RGBA", (1300,60), (0, 0, 0, 255))
        textbox1 = Image.new("RGBA", (1300,410), (254, 238, 218, 180))
        mapimg = Image.open(BF1_SERVERS_DATA/'Caches'/'Maps1'/f'{dict[recent[i]["map"]]}.jpg').resize((551,350))
        textbox1.paste(mapimg,(0,60))
        draw = ImageDraw.Draw(textbox1)
        
        text=f'{recent[i]["serverName"]}'

        if recent[i]["teamId"] == 0:
            team = ""
            isWinner = "未结算"
        else:
            if recent[i]["teams"][0]["isWinner"] == recent[i]["teams"][1]["isWinner"]:
                isWinner = "未结算"
                for k in recent[i]["teams"]:
                    if k["id"] == recent[i]["teamId"]:
                        team = dict[k["name"]]
            else:
                for k in recent[i]["teams"]:
                    if k["id"] == recent[i]["teamId"]:
                        team = dict[k["name"]]
                        if k["isWinner"]:
                            isWinner = "胜利"
                        else:
                            isWinner = "落败"


        mapandmode = dict[recent[i]["map"]] + '-' +dict[recent[i]["mode"]] + " "
        
        timePlayed = recent[i]["timePlayed"]
        hours = int(timePlayed // 3600)
        minutes = int(timePlayed // 60 - 60*hours)
        seconds = int(timePlayed) - 3600*hours - 60*minutes

        duration = f"{minutes}分{seconds}秒" if hours == 0 else f"{hours}时{minutes}分{seconds}秒"
        draw.text(xy=(0,4), text=text[0:30], fill=(55, 1, 27, 255),font=font_3)
        draw.text(xy=((550+font_2.getsize(text[0:30])[0]/2-font_2.getsize(mapandmode)[0]/2),10), text=mapandmode, fill=(55, 1, 27, 255),font=font_2)
        if isWinner == '胜利':
            draw.text(xy=((1280-font_2.getsize(team+ "  " + isWinner)[0]),10), text=team+ "  " + isWinner, fill=(100, 255, 50, 255),font=font_2)
        elif isWinner == '落败':
            draw.text(xy=((1280-font_2.getsize(team+ "  " + isWinner)[0]),10), text=team+ "  " + isWinner, fill=(255, 105, 93, 255),font=font_2)
        elif isWinner == '未结算':
            draw.text(xy=((1200-font_2.getsize(team+ "  " + isWinner)[0]),10), text=team+ "  " + isWinner, fill=(55, 1, 27, 255),font=font_2)

        draw.text(xy=(640,90), text=f'时长:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,90), text=duration, fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,90), text=f'得分:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,90), text=f'{recent[i]["score"]}', fill=(66, 112, 244, 255),font=font_4)
        
        draw.text(xy=(640,141), text=f'击杀:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,141), text=f'{int(recent[i]["kills"])}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,141), text=f'死亡:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,141), text=f'{int(recent[i]["deaths"])}', fill=(66, 112, 244, 255),font=font_4)

        draw.text(xy=(640,192), text=f'KDA:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,192), text=f'{recent[i]["kd"]}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,192), text=f'KPM:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,192), text=f'{recent[i]["kpm"]}', fill=(66, 112, 244, 255),font=font_4)
        
        draw.text(xy=(640,243), text=f'伤害:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,243), text=f'{int(recent[i]["damage"]*100)}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,243), text=f'SPM:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,243), text=f'{int(recent[i]["spm"])}', fill=(66, 112, 244, 255),font=font_4)

        draw.text(xy=(640,294), text=f'命中:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,294), text=f'{recent[i]["acc"]}%', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,294), text=f'爆头:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,294), text=f'{recent[i]["hs"]}%', fill=(66, 112, 244, 255),font=font_4)

        date_str = recent[i]["timestamp"][:-6]
        dt = datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
        offset = datetime.timedelta(hours=8)
        dt = dt + offset
        formatted_dt = '数据记录时间: ' + dt.strftime('%Y/%m/%d %H:%M:%S')
 
        draw.text(xy=((925-font_5.getsize(formatted_dt)[0]/2),360), text=formatted_dt, fill=(34,139,34, 255),font=font_5)
        position = (0, 360+410*i)
        img.paste(textbox0,position,textbox0)
        img.paste(textbox1,position,textbox1)

        timeall += int(timePlayed)
        killall += int(recent[i]["kills"])
        deathall += int(recent[i]["deaths"])
    
    textbox = Image.new("RGBA", (1300,50), (254, 238, 218, 180))
    img.paste(textbox,(0,410*len(recent)+360),textbox)

    textbox = Image.new("RGBA", (1300,110), (254, 238, 218, 180))
    draw = ImageDraw.Draw(textbox)
    text = f'时长: {timeall//3600}时{(timeall%3600)//60}分{timeall%60}秒  击杀: {killall}  死亡: {deathall}  KD: {((killall*100)//deathall)/100 if deathall !=0 else killall}  KP: {(killall*6000 // timeall)/100 if timeall !=0 else killall}'
    draw.text(xy=(650-font_2.getsize(text)[0]/2,35), text=text ,fill=(34,139,34,255),font=font_2)
    img.paste(textbox,(0,250),textbox)

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],410*len(recent)+365), text=text ,fill=(34,139,34, 255),font=font_0)
    draw.line((0, 250, 1300, 250), fill=(55, 1, 27, 120), width=4)
    print("draw_r"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    return base64img(img)

async def draw_exchange(remid, sid, sessionID):
    res = await upd_exchange(remid, sid, sessionID)
    h = len(res['result']['items'])
    h = h//7+1 if h%7 else h//7
    img = Image.new("RGBA", (1500,150*h+150), (254, 238, 218, 255))
    tasks = []
    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=20, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=15, encoding='UTF-8')
    f = open(CURRENT_FOLDER/"ex.json","r",encoding="utf-8")
    ex_dict = json.load(f)
    for i in range(len(res['result']['items'])):
        url = 'https://eaassets-a.akamaihd.net/battlelog/battlebinary/'+res['result']['items'][i]['item']['images']['Png180xANY'][11:]
        
        try:
            if res['result']['items'][i]['item']['images']['Png300xANY'][11:]:
                url = 'https://eaassets-a.akamaihd.net/battlelog/battlebinary/'+res['result']['items'][i]['item']['images']['Png300xANY'][11:]
        except:
            pass
        
        position = (50+200*(i%7),100+150*(i//7))

        text = res['result']['items'][i]['item']["name"]
        text1 = res['result']['items'][i]['item']["parentName"]
        text2 = str(res['result']['items'][i]['price'])+'零件'

        if res['result']['items'][i]['item']["rarenessLevel"]['value'] == 0:
            draw.text(xy=(140+200*(i%7)-0.5*font_0.getsize(text)[0],150+150*(i//7)), text=text ,fill=(34,139,34, 255),font=font_0)
        elif res['result']['items'][i]['item']["rarenessLevel"]['value'] == 1:
            draw.text(xy=(140+200*(i%7)-0.5*font_0.getsize(text)[0],150+150*(i//7)), text=text ,fill=(66, 112, 244, 255),font=font_0)
        elif res['result']['items'][i]['item']["rarenessLevel"]['value'] == 2:
            if text1 == None:
                draw.text(xy=(140+200*(i%7)-0.5*font_0.getsize(text)[0],170+150*(i//7)), text=text ,fill=((255,100,0,255)),font=font_0)
            else:
                draw.text(xy=(140+200*(i%7)-0.5*font_0.getsize(text)[0],150+150*(i//7)), text=text ,fill=((255,100,0,255)),font=font_0)
    
        if text1 != None:
            draw.text(xy=(140+200*(i%7)-0.5*font_2.getsize(text1)[0],173+150*(i//7)), text=text1 ,fill=(55, 1, 27, 255),font=font_2)

        draw.text(xy=(140+200*(i%7)-0.5*font_0.getsize(text2)[0],190+150*(i//7)), text=text2 ,fill=(0, 0, 100, 255),font=font_0)
        try:
            if text in ex_dict[text1]:
                draw.line((50+200*(i%7), 215+150*(i//7), 230+200*(i%7), 215+150*(i//7)), fill=(255, 1, 27, 120), width=4)
        except:
            pass
        tasks.append(asyncio.create_task(paste_exchange(url,img,position,(180,45))))

    await asyncio.gather(*tasks)
    
    font_1 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(1500-font_1.getsize(text)[0],150*h+115), text=text ,fill=(34,139,34, 255),font=font_1)

    return base64img(img)

async def draw_a(num,name,reason,personaId):
    if reason == []:
        img = Image.new("RGBA", (900,30*num), (254, 238, 218, 255))
        draw = ImageDraw.Draw(img)
        font_0 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
        for i in range(num):
            draw.text(xy=(10,30*i), text=str(i+1)+'. '+name[i] ,fill=(0, 0, 100, 255),font=font_0)
    else:
        img = Image.new("RGBA", (900,60*num), (254, 238, 218, 255))
        draw = ImageDraw.Draw(img)
        font_0 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
        for i in range(num):
            draw.text(xy=(10,60*i), text=str(i+1)+'. '+name[i] ,fill=(0, 0, 100, 255),font=font_0)
            draw.text(xy=(10,60*i+30), text="理由: "+ reason[i],fill=(0, 0, 100, 255),font=font_0)
    return base64img(img)

async def draw_faq():
    with open(CURRENT_FOLDER/"faq.txt", "r",encoding="UTF-8") as f:
        textArg = f.read().split("\n")
    img = Image.new("RGBA", (900,30*len(textArg)), (254, 238, 218, 255))
    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='simsun.ttc', size=25, encoding='UTF-8')
    for i in range(len(textArg)):
        if textArg[i].startswith("Q"):
            draw.text(xy=(10,30*i), text=textArg[i], fill=(150, 0, 0, 255),font=font_0)
        else:
            draw.text(xy=(10,30*i), text=textArg[i], fill=(0, 0, 100, 255),font=font_0)

    return base64img(img)

async def draw_re(remid, sid, sessionID, personaId, playerName):
    print("draw_re"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    tasks = []
    #tasks.append(asyncio.create_task(upd_StatsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_Emblem(remid, sid, sessionID, personaId)))

    personaIds=[]
    personaIds.append(personaId)
    tasks.append(asyncio.create_task(upd_getActiveTagsByPersonaIds(remid,sid,sessionID,personaIds)))
    tasks.append(asyncio.create_task(update_diff(remid,sid,sessionID,personaId)))

    emblem,res_tag,(recent,res_stat) = await asyncio.gather(*tasks)

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

    try:
        img = Image.open(BF1_PLAYERS_DATA/'Caches'/f'{personaId}.jpg') 
        img = img.resize((1800,1800))
        img = img.crop((250,0,1550,(170*len(recent)+300)))
    except:    
        img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC1.jpg')
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
        draw.text(xy=(860,100), text=f'{round(recent[i]["k"] / recent[i]["d"] if recent[i]["d"] !=0 else recent[i]["k"], 2)}', fill=(66, 112, 244, 255),font=font_4)
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

async def upd_pl_platoons(remid, sid, sessionID, gameId):
    pljson = await upd_blazepl(gameId)
    personaIds = []
    playerNames = []
    tasks = []
    for stats in pljson["1"]:
        personaIds.append(stats["id"])
        playerNames.append(stats["userName"])
    for stats in pljson["2"]:
        personaIds.append(stats["id"])
        playerNames.append(stats["userName"])

    for id in personaIds:
        tasks.append(asyncio.create_task(upd_platoons(remid,sid,sessionID,id)))
    
    plat = await asyncio.gather(*tasks)


    platjson = {}
    guids = []
    for i in range(len(plat)):
        res = plat[i]["result"]
        for platoon in res:
            name = platoon["name"]
            guid = platoon["guid"]
            if guid not in guids:
                guids.append(guid)
                platjson[guid] = {}
                platjson[guid]["name"] = name
                platjson[guid]["tag"] = platoon["tag"]
                platjson[guid]["emblem"] = platoon["emblem"]
                platjson[guid]["player"] = []
                platjson[guid]["player"].append(playerNames[i])
            else:
                platjson[guid]["player"].append(playerNames[i])

    return platjson

async def draw_platoons(remid, sid, sessionID, gameId,mode):
    platjson = await upd_pl_platoons(remid, sid, sessionID, gameId)
    status = list(platjson.values())
    
    tasks = []
    names = []
    tags = []
    emblems = []
    players = []
    hs = []
    h = 0
    for i in status:
        if len(i["player"]) > mode:
            names.append(i["name"])
            tags.append(i["tag"])
            emblems.append(i["emblem"])
            players.append(i["player"])
            hs.append(290+100*(len(i["player"])))
            h += (290+100*(len(i["player"])))

    img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC1.jpg')
    img = img.resize((1300,h))
    draw = ImageDraw.Draw(img)
    
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=250, encoding='UTF-8')
    font_1 = ImageFont.truetype(font='Dengb.ttf', size=90, encoding='UTF-8')
    
    y = 0
    for i in range(len(names)):
        draw.text(xy=(775-font_0.getsize(tags[i])[0]/2,y), text=tags[i] ,fill=(34,139,34, 255),font=font_0)
        for j in range(len(players[i])):
            draw.text(xy=(0,y + 250 + j*100), text=f"[{tags[i]}]{players[i][j]}" ,fill=(66, 112, 244, 255),font=font_1)

        try:
            emblem = emblems[i].split('/')
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
        

        position = (0,y)
        tasks.append(paste_emb(emblem,img,position))
        y += hs[i]
    await asyncio.gather(*tasks)

    return base64img(img)

async def draw_searchplatoons(remid, sid, sessionID, partialName):
    platjson = await upd_findplatoon(remid, sid, sessionID, partialName)
    status = platjson["result"]
    
    tasks = []
    names = []
    tags = []
    emblems = []
    players = []

    for i in status:
        names.append(i["name"])
        tags.append(i["tag"])
        emblems.append(i["emblem"])

    img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC1.jpg')
    img = img.resize((1300,250*len(status)))
    draw = ImageDraw.Draw(img)
    
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=250, encoding='UTF-8')
    font_1 = ImageFont.truetype(font='Dengb.ttf', size=90, encoding='UTF-8')
    
    y = 0
    for i in range(len(names)):
        draw.text(xy=(775-font_1.getsize(tags[i])[0]/2,y+20), text=tags[i] ,fill=(34,139,34, 255),font=font_1)
        draw.text(xy=(775-font_1.getsize(names[i])[0]/2,y+140), text=names[i] ,fill=(66, 112, 244, 255),font=font_1)

        try:
            emblem = emblems[i].split('/')
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
        

        position = (0,y)
        tasks.append(paste_emb(emblem,img,position))
        y += 250
    await asyncio.gather(*tasks)

    return base64img(img)

async def draw_detailplatoon(remid, sid, sessionID, partialName):
    platjson = await upd_findplatoon(remid, sid, sessionID, partialName)
    guid = platjson["result"][0]["guid"]
    
    details,members = await asyncio.gather(
        upd_platoon(remid, sid, sessionID, guid),
        upd_platoonMembers(remid, sid, sessionID, guid)
    )

    name = details["result"]["name"]
    try:
        des = "简介: " + details["result"]["description"]
    except:
        des = "简介: "
    tag = details["result"]["tag"]
    emblem = details["result"]["emblem"]
    dateCreated = details["result"]["dateCreated"]
    dateCreated = datetime.datetime.fromtimestamp(int(dateCreated)).strftime("%Y-%m-%d %H:%M:%S")
    members = members["result"]     

    role9 = []
    role6 = []
    role3 = []
    role0 = []
    for i in members:
        if i["role"] == "role9":
            role9.append(i["displayName"])
        elif i["role"] == "role6":
            role6.append(i["displayName"])
        elif i["role"] == "role3":
            role3.append(i["displayName"])
        elif i["role"] == "role0":
            role0.append(i["displayName"])  
    h = 700 + 50*(len(role9)//3+len(role6)//3+len(role3)//3+len(role0)//3)

    img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC1.jpg')
    img = img.resize((1300,h))
    draw = ImageDraw.Draw(img)
    
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=50, encoding='UTF-8')
    font_1 = ImageFont.truetype(font='Dengb.ttf', size=90, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=40, encoding='UTF-8')


    draw.text(xy=(775-font_1.getsize(tag)[0]/2,20), text=tag ,fill=(34,139,34, 255),font=font_1)
    draw.text(xy=(775-font_1.getsize(name)[0]/2,140), text=name ,fill=(66, 112, 244, 255),font=font_1)

    draw.text(xy=(0,260), text=f"创建时间: {dateCreated}" ,fill=(255,100,0,255),font=font_2)

    result = ""
    text = ""
    for i in des:
        if font_2.getsize(text)[0] <= 1200:
            text += i
            result += i
        else:
            result += i + "\n"
            text = ""
    result = zhconv.convert(result,"zh-cn")

    for i in range(len(result.split('\n'))):
        draw.text(xy=(0,320+i*50), text=result.split('\n')[i], fill=(66, 112, 244, 255),font=font_2)
        if i == 1:
            break

    draw.text(xy=(0,430), text=f"成员(共{len(members)}人): " ,fill=(34,139,34, 255),font=font_2)
    
    draw.text(xy=(0,480), text=f"将军: " ,fill=(34,139,34, 255),font=font_2)       
    for a in range(len(role9)):
        draw.text(xy=(120+a%3*400,480+a//3*50), text=role9[a] ,fill=(34,139,34, 255),font=font_2)
    try:
        y = 530+a//3*50
    except:
        y = 530
    
    draw.text(xy=(0,y), text=f"上校: " ,fill=(34,139,34, 255),font=font_2) 
    for b in range(len(role6)):
        draw.text(xy=(120+b%3*400,y+b//3*50), text=role6[b] ,fill=(34,139,34, 255),font=font_2)
    try:
        y = y+b//3*50 +50
    except:
        y = y+50
    
    draw.text(xy=(0,y), text=f"中尉: " ,fill=(34,139,34, 255),font=font_2) 
    for c in range(len(role3)):
        draw.text(xy=(120+c%3*400,y+c//3*50), text=role3[c] ,fill=(34,139,34, 255),font=font_2)
    try:
        y = y+c//3*50 +50
    except:
        y = y+50
    
    draw.text(xy=(0,y), text=f"列兵: " ,fill=(34,139,34, 255),font=font_2) 
    for d in range(len(role0)):
        draw.text(xy=(120+d%3*400,y+d//3*50), text=role0[d] ,fill=(34,139,34, 255),font=font_2)

    try:
        emblem = emblem.split('/')
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
        

    position = (0,0)
    await paste_emb(emblem,img,position)

    return base64img(img)

async def draw_log(logs,remid: str, sid: str, sessionID: str):
    img = Image.new("RGBA", (900,60*len(logs)), (254, 238, 218, 255))
    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
    pids = []
    
    for i in range(len(logs)):
        logtime = logs[i].split("|")[0].strip()
        logdict = json.loads(logs[i].split("|")[1].strip())

        try:
            pid = logdict["pid"]
            if int(pid) not in pids:
                pids.append(int(pid))
        except:
            pass
        draw.text(xy=(10,60*i), text=str(i+1)+'. '+logtime ,fill=(0, 0, 100, 255),font=font_0)
        
    userName_res = await upd_getPersonasByIds(remid, sid, sessionID,pids)
    names = {str(pid): (userName_res['result'][str(pid)]['displayName'] if str(pid) in userName_res['result'] else str(pid)) for pid in pids}
    
    for i in range(len(logs)):
        logtime = logs[i].split("|")[0].strip()
        logdict = json.loads(logs[i].split("|")[1].strip())
        try:
            name = names[str(logdict["pid"])]
        except:
            pass
        match logdict["incident"]:
            case 'map':
                msg = f'{logdict["processor"]}将{logdict["serverind"]}服地图切换为{logdict["mapName"]}'
            case 'kick':
                msg = f'{logdict["processor"]}在{logdict["serverind"]}服踢出玩家{name}, 理由:{logdict["reason"]}'
            case 'kickall':
                msg = f'{logdict["processor"]}在{logdict["serverind"]}服踢出玩家{name}(清服), 理由:{logdict["reason"]}'
            case 'ban':
                msg = f'{logdict["processor"]}在{logdict["serverind"]}服封禁玩家{name}, 理由:{logdict["reason"]}'
            case 'banall':
                msg = f'{logdict["processor"]}封禁玩家{name}(banall), 理由:{logdict["reason"]}'
            case 'unban':
                msg = f'{logdict["processor"]}在{logdict["serverind"]}服解封玩家{name}'
            case 'unbanall':
                msg = f'{logdict["processor"]}解封玩家{name}(unbanall)'   
            case 'vban':
                msg = f'{logdict["processor"]}在{logdict["serverind"]}服封禁玩家{name}(vban), 理由:{logdict["reason"]}'
            case 'vbanall':
                msg = f'{logdict["processor"]}封禁玩家{name}(vbanall), 理由:{logdict["reason"]}'
            case 'unvban':
                msg = f'{logdict["processor"]}在{logdict["serverind"]}服解封玩家{name}(vban)'
            case 'unvbanall':
                msg = f'{logdict["processor"]}解封玩家{name}(vbanall)' 
            case 'move':
                msg = f'{logdict["processor"]}在{logdict["serverind"]}服将玩家{name}换边' 
            case 'vip':
                msg = f'{logdict["processor"]}在{logdict["serverind"]}服为玩家{name}添加{logdict["day"]}天vip'
                try:
                    nextday = logdict["nextday"]
                    msg += f'({nextday})'
                except:
                    pass
            case 'unvip':
                msg = f'{logdict["processor"]}在{logdict["serverind"]}服解除玩家{name}的vip' 
        
        draw.text(xy=(10,60*i+25), text='   '+msg ,fill=(0, 0, 100, 255),font=font_0)
    
    return base64img(img)

__all__ = [
    'base64img',
    'draw_f',
    'draw_server',
    'draw_stat',
    'draw_wp',
    'draw_pl2',
    'draw_r',
    'draw_a',
    'draw_exchange',
    'draw_faq',
    'draw_re',
    'draw_platoons',
    'draw_searchplatoons',
    'draw_detailplatoon',
    'draw_log'
]