from PIL import Image, ImageDraw, ImageFilter, ImageFont
import requests
import json
import random
import re
import os
import zhconv
import datetime
import asyncio
import httpx
from io import BytesIO
from .bf1rsp import *
from .utils import BF1_SERVERS_DATA, BF1_PLAYERS_DATA, request_API,search_all,special_stat_to_dict

GAME = 'bf1'
LANG = 'zh-tw'

async def paste_image(url,img,position):
    async with httpx.AsyncClient() as client:
        response = await client.get(url,timeout=20)
        image_data = response.content
        image = Image.open(BytesIO(image_data))
        img.paste(image,position,image)

async def paste_emb(url,img,position):
    async with httpx.AsyncClient() as client:
        response = await client.get(url,timeout=20)
        image_data = response.content
        image = Image.open(BytesIO(image_data)).resize((250,250)).convert("RGBA")
        try:
            img.paste(image,position,image)
        except:
            img.paste(image,position)

async def draw_f(server_id:int,session:int,remid, sid, sessionID):
    # 打开图片文件
    img = Image.open(BF1_SERVERS_DATA/f'Caches/background/DLC{random.randint(1, 6)}.jpg')
    img = img.resize((1506,2900))
    img = img.crop((0,0,1506,400*server_id+100))
    un = 0
    # 将原始图片模糊化
    img = img.filter(ImageFilter.GaussianBlur(radius=15))

    tasks = []
    ress = []
    for id in range(server_id):
        with open(BF1_SERVERS_DATA/f'{session}_jsonGT'/f'{session}_{id+1}.json','r', encoding='utf-8') as f:
            serverGT = json.load(f)
            gameId = serverGT['gameId']
        tasks.append(asyncio.create_task(upd_detailedServer(remid, sid, sessionID, gameId)))
    
    ress = await asyncio.gather(*tasks)
    for id in range(server_id):
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
        draw0.text(xy=(80,8), text=servername, fill=(255, 255, 255, 255),font=font_1)
        draw.text(xy=(560,10), text=status1, fill=(255, 255, 0, 200),font=font_2)
        draw.text(xy=(1160,10), text=status3, fill=(0, 255, 255, 200),font=font_2)
        draw.text(xy=(500,40), text='------------------------------------------------------', fill=(0, 255, 0, 100),font=font_1)
        if int(servermaxamount) - int(serveramount) < 10:
            draw.text(xy=(960,125), text=status2, fill=(0, 255, 0, 255),font=font_4)
        else:
            draw.text(xy=(960,125), text=status2, fill=(255, 150, 0, 255),font=font_4)
        pattern = re.compile(r"([\u4e00-\u9fa5]|[a-zA-Z]|[≤≥。，、；：“”‘’！？【】（）{}\[\]&nbsp;&mdash;…《》〈〉·—～,.?+\'\"\/;_\(\)]\ |[0-9])")
        count = 0
        result = ''
        for i in serverinfo:
            if pattern.match(i) and len(i.encode('utf-8')) == 3:
                count += 2
            else:
                count += 1

            if count < 25:
                result += i
            else:
                result += i + '\n'
                count = 0

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
    server_id -= un
    img = img.crop((0,0,1506,400*server_id+100))

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],400*server_id+65), text=text ,fill=(255, 255, 0, 255),font=font_0)
    img.save(BF1_SERVERS_DATA/f'Caches/{session}.jpg')
    return 1

async def draw_server(remid, sid, sessionID, serverName, res):
    img = Image.open(BF1_SERVERS_DATA/f'Caches/background/DLC{random.randint(1, 6)}.jpg')
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

    ress = await asyncio.gather(*tasks)

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
        serverstar = res_0['result']['serverInfo']['serverBookmarkCount']

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
        font_3 = ImageFont.truetype(font='msyh.ttc', size=28, encoding='UTF-8')
        font_4 = ImageFont.truetype(font='comic.ttf', size=72, encoding='UTF-8')
        draw0.text(xy=(80,8), text=servername, fill=(255, 255, 255, 255),font=font_1)
        draw.text(xy=(560,10), text=status1, fill=(255, 255, 0, 200),font=font_2)
        draw.text(xy=(1160,10), text=status3, fill=(0, 255, 255, 200),font=font_2)
        draw.text(xy=(500,40), text='------------------------------------------------------', fill=(0, 255, 0, 100),font=font_1)
        if int(servermaxamount) - int(serveramount) < 10:
            draw.text(xy=(960,125), text=status2, fill=(0, 255, 0, 255),font=font_4)
        else:
            draw.text(xy=(960,125), text=status2, fill=(255, 150, 0, 255),font=font_4)
        pattern = re.compile(r"([\u4e00-\u9fa5]|[a-zA-Z]|[≤≥。，、；：“”‘’！？【】（）{}\[\]&nbsp;&mdash;…《》〈〉·—～,.?+\'\"\/;_\(\)]\ |[0-9])")
        count = 0
        result = ''
        for i in serverinfo:
            if pattern.match(i) and len(i.encode('utf-8')) == 3:
                count += 2
            else:
                count += 1

            if count < 25:
                result += i
            else:
                result += i + '\n'
                count = 0

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
    
    img.save(BF1_SERVERS_DATA/f'Caches/{serverName}.jpg')
    return 1

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

def search_dicts_by_key_value(dict_list, key, value):
    for d in dict_list:
        if key in d and d[key] == value:
            return True
        else :
            return False

async def draw_stat(remid, sid, sessionID,personaId:int,playerName:str):
    tasks = []
    tasks.append(asyncio.create_task(upd_blazestats5(personaId)))
    tasks.append(asyncio.create_task(upd_StatsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_WeaponsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_VehiclesByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_Emblem(remid, sid, sessionID, personaId)))

    personaIds=[]
    personaIds.append(personaId)
    tasks.append(asyncio.create_task(upd_getActiveTagsByPersonaIds(remid,sid,sessionID,personaIds)))
    tasks.append(asyncio.create_task(bfeac_checkBan(playerName)))
    special_stat,res_stat,res_weapon,res_vehicle,emblem,res_tag,bfeac = await asyncio.gather(*tasks)

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

    owner,ban,admin,vip = search_all(personaId)


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
        weapons.append(dict_AS)
        weapons.append(dict_PK)
        weapons.append(dict_BD1)
        weapons.append(dict_BD2)
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
        img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC{random.randint(1, 6)}.jpg')

    
    img = img.resize((1500,1500))

    textbox = Image.new("RGBA", (1300,250), (0, 0, 0, 150))
    draw = ImageDraw.Draw(textbox)
    font_1 = ImageFont.truetype(font='msyhbd.ttc', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=40, encoding='UTF-8')
    if tag == '':
        text=f'{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,15), text=text, fill=(255, 255, 0, 255),font=font_1)
    else:
        text=f'[{tag}]{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,15), text=text, fill=(255, 255, 0, 255),font=font_1)

    draw.text(xy=(290,95), text=f'游玩时长:{secondsPlayed//3600}小时\n击杀数:{k}\n死亡数:{d}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,95), text=f'获胜率:{0 if win+loss == 0 else win*100/(win+loss):.2f}%\n命中率:{acc*100:.2f}%\n爆头率:{0 if k == 0 else hs/k*100:.2f}%', fill=(255, 255, 255, 255),font=font_2)
    try:
        draw.text(xy=(1070,95), text=f'KDA:{kd:.2f}\nKPM:{kpm}\nDPM:{round((d*60)/secondsPlayed,2)}', fill=(255, 255, 255, 255),font=font_2)
    except:
        draw.text(xy=(1070,95), text=f'KDA:{kd:.2f}\nKPM:{kpm}\nDPM:0.00', fill=(255, 255, 255, 255),font=font_2)
    position = (100, 100)
    img.paste(textbox, position, textbox)

    textbox1 = Image.new("RGBA", (640,675), (0, 0, 0, 150))
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
    draw.text(xy=(35,536), text=f'步兵击杀:{infantrykill}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,580), text=f'载具击杀:{carkill}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,624), text=f'BFEAC状态:{bfeac["stat"]}', fill=(255, 255, 255, 255),font=font_4)

    draw.text(xy=(360,403), text=f'{gamemodes[0]["prettyName"][0:2]}胜率:{(100*gamemodes[0]["winLossRatio"])/(1+gamemodes[0]["winLossRatio"]):.2f}%', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,447), text=f'{gamemodes[1]["prettyName"][0:2]}胜率:{(100*gamemodes[1]["winLossRatio"])/(1+gamemodes[1]["winLossRatio"]):.2f}%', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,536), text=f'步兵KPM:{infantrykp}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,580), text=f'载具KPM:{carkp}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,624), text=f'SPM:{spm}', fill=(255, 255, 255, 255),font=font_4)

    position1 = (100, 380)
    img.paste(textbox1, position1, textbox1)

    textbox3 = Image.new("RGBA", (640,330), (0, 0, 0, 150))
    draw = ImageDraw.Draw(textbox3)
    font_5 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    draw.text(xy=(80,150), text=f'{zhconv.convert(vehicles[0]["name"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
    kill1 = int(vehicles[0]['stats']['values']['kills'])
    star = kill1 // 100  #★{serverstar
    if star < 50:
        draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 255, 255),font=font_5)
    elif star < 100:
        draw.text(xy=(10,10), text=f'★{star}', fill=(0, 255, 0, 255),font=font_5)
    else:
        draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 0, 255),font=font_5)

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
    img.paste(textbox3, position3, textbox3)

    for i in range(3):
        textbox3 = Image.new("RGBA", (640,330), (0, 0, 0, 150))
        draw = ImageDraw.Draw(textbox3)
        draw.text(xy=(80,150), text=f'{zhconv.convert(weapons[i]["name"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
        kill1 = int(weapons[i]['stats']['values']['kills'])
        star = kill1 // 100 #★{serverstar
        if star < 50:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 255, 255),font=font_5)
        elif star < 100:
            draw.text(xy=(10,10), text=f'★{star}', fill=(0, 255, 0, 255),font=font_5)
        else:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 0, 255),font=font_5)

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
        img.paste(textbox3, position3, textbox3)

        wp_img = BF1_SERVERS_DATA/'Caches'/'Weapons'/f'{weapons[i]["imageUrl"].split("/")[-1]}'
        img_wp = Image.open(wp_img).resize((400,100)).convert("RGBA")
        img.paste(paste_img(img_wp), (880, 345*i+410), img_wp)

    img_class = Image.open(BF1_SERVERS_DATA/f'Caches/Classes/{bestClass}.png').resize((45,45)).convert("RGBA")
    img.paste(paste_img(img_class), (415, 409), img_class)

    vehicles_img = BF1_SERVERS_DATA/'Caches'/'Weapons'/f'{vehicles[0]["vehicles"][0]["imageUrl"].split("/")[-1]}'
    img_vehicles = Image.open(vehicles_img).resize((400,100)).convert("RGBA")
    img.paste(paste_img(img_vehicles), (220, 1100), img_vehicles)
    
    await paste_emb(emblem,img,(100,100))

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],1465), text=text ,fill=(255, 255, 0, 255),font=font_0)
 
 
    img.save(BF1_SERVERS_DATA/f'Caches/{playerName}.jpg')
    return 1
#draw_f(4,248966716,remid, sid, sessionID)

async def draw_wp(remid, sid, sessionID, personaId, playerName:str, mode:int):
    tasks = []
    tasks.append(asyncio.create_task(upd_blazestats5(personaId)))
    tasks.append(asyncio.create_task(upd_StatsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_WeaponsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_VehiclesByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_Emblem(remid, sid, sessionID, personaId)))

    personaIds=[]
    personaIds.append(personaId)
    tasks.append(asyncio.create_task(upd_getActiveTagsByPersonaIds(remid,sid,sessionID,personaIds)))

    special_stat,res_stat,res_weapon,res_vehicle,emblem,res_tag = await asyncio.gather(*tasks)

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
        img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC{random.randint(1, 6)}.jpg')

    img = img.resize((2000,2000))
    img = img.crop((350,0,1650,2000))

    textbox = Image.new("RGBA", (1300,250), (0, 0, 0, 150))
    draw = ImageDraw.Draw(textbox)
    font_1 = ImageFont.truetype(font='msyhbd.ttc', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=40, encoding='UTF-8')
    font_5 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    if tag == '':
        text=f'{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,15), text=text, fill=(255, 255, 0, 255),font=font_1)
    else:
        text=f'[{tag}]{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,15), text=text, fill=(255, 255, 0, 255),font=font_1)

    draw.text(xy=(290,95), text=f'游玩时长:{secondsPlayed//3600}小时\n击杀数:{k}\n死亡数:{d}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,95), text=f'获胜率:{0 if win+loss == 0 else win*100/(win+loss):.2f}%\n命中率:{acc*100:.2f}%\n爆头率:{0 if k == 0 else hs/k*100:.2f}%', fill=(255, 255, 255, 255),font=font_2)
    try:
        draw.text(xy=(1070,95), text=f'KDA:{kd:.2f}\nKPM:{kpm}\nDPM:{round((d*60)/secondsPlayed,2)}', fill=(255, 255, 255, 255),font=font_2)
    except:
        draw.text(xy=(1070,95), text=f'KDA:{kd:.2f}\nKPM:{kpm}\nDPM:0.00', fill=(255, 255, 255, 255),font=font_2)
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
        weapons.append(dict_AS)
        weapons.append(dict_PK)
        weapons.append(dict_BD1)
        weapons.append(dict_BD2)
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

    if mode < 13:
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

        for i in weapons:
            match i['category']:
                case '戰場裝備':
                    mode_1.append(i)
                case '配備':
                    mode_2.append(i)
                case '半自動步槍':
                    mode_3.append(i)
                case '霰彈槍':
                    mode_4.append(i)
                case '佩槍':
                    mode_5.append(i)
                case '輕機槍':
                    mode_6.append(i)
                case '近戰武器':
                    mode_7.append(i)
                case '步槍':
                    mode_8.append(i)
                case '坦克/駕駛員':
                    mode_9.append(i)
                case '手榴彈':
                    mode_10.append(i)
                case '制式步槍':
                    mode_11.append(i)
                case '衝鋒槍':
                    mode_12.append(i)

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

    for i in range(min(10,len(weapons)-1)):
        textbox3 = Image.new("RGBA", (645,330), (0, 0, 0, 150))
        draw = ImageDraw.Draw(textbox3)

        kill1 = int(weapons[i]['stats']['values']['kills'])
        star = kill1 // 100 #★{serverstar
        if star < 50:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 255, 255),font=font_5)
        elif star < 100:
            draw.text(xy=(10,10), text=f'★{star}', fill=(0, 255, 0, 255),font=font_5)
        else:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 0, 255),font=font_5)

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
        if mode == 13:
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

        position3 = (655*(i%2), 260+(i//2)*340)
        img.paste(textbox3, position3, textbox3)

        wp_img = BF1_SERVERS_DATA/'Caches'/'Weapons'/f'{weapons[i]["imageUrl"].split("/")[-1]}'
        img_wp = Image.open(wp_img).resize((400,100)).convert("RGBA")
        img.paste(paste_img(img_wp), (130+650*(i%2), 340*(i//2)+300), img_wp)

    await paste_emb(emblem,img,(0,0))

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],1965), text=text ,fill=(255, 255, 0, 255),font=font_0)
    img.save(BF1_SERVERS_DATA/f'Caches/{playerName}_wp.jpg')

    return 1

def get_pl(gameID:str)->dict:
    return request_API(GAME,'players',{'gameid':gameID})

async def async_get_stat(playerid,platoon,latency):
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            url="https://api.gametools.network/bf1/stats",
            params={'playerid': playerid,
                    'lang':'zh-tw',
                    "platform":"pc",}
                    )
        res = response.text[0:-1]+f', "platoon": "{platoon}", "latency": {latency}'+'}'
        return res
    
async def draw_pl(session,server_id,pl,gameId,remid, sid, sessionID):

    detailedServer = await upd_detailedServer(remid, sid, sessionID, gameId)
    vipList = detailedServer['result']["rspInfo"]['vipList']
    adminList = detailedServer['result']["rspInfo"]['adminList']

    try:
        with open(BF1_PLAYERS_DATA/'whitelist'/f'{session}_{server_id}.txt') as f:
            whiteList = f.read().split(',')
    except:
        whiteList = []
        print('whitelist not found')

    try:
        personaIds = []
        for filename in os.listdir(BF1_PLAYERS_DATA/f'{session}'):
            if filename.endswith('txt'):
                id = filename.rstrip('.txt')
                personaIds.append(id.split('_')[1])
        member_json = await upd_getPersonasByIds(remid, sid, sessionID,personaIds)
        member_json = member_json['result']
        memberList = [value['displayName'] for value in member_json.values()]
    except:
        print('memberList not found')
    tasks = []
    serverimg = detailedServer['result']['serverInfo']['mapImageUrl'].split('/')[5]
    serverimg = BF1_SERVERS_DATA/f'Caches/Maps/{serverimg}'
    serverName = detailedServer['result']['serverInfo']['name']

    teamImage_1 = pl['teams'][0]['key']
    pl_1 = pl['teams'][0]['players']
    for i in range(len(pl_1)):
        personaId = pl_1[i]['player_id']
        platoon = pl_1[i]['platoon']
        latency = pl_1[i]['latency']
        tasks.append(asyncio.create_task(async_get_stat(personaId,platoon,latency)))

    teamImage_2 = pl['teams'][1]['key']
    pl_2 = pl['teams'][1]['players']
    for j in range(len(pl_2)):
        personaId = pl_2[j]['player_id']
        platoon = pl_2[j]['platoon']
        latency = pl_2[j]['latency']
        tasks.append(asyncio.create_task(async_get_stat(personaId,platoon,latency)))
    
    results = await asyncio.gather(*tasks)
    print(datetime.datetime.now())
    stat1 = []
    stat2 = []
    for i in range(len(pl_1)):
        try:
            stat1.append(json.loads(results[i]))
        except:
            continue
    stat1 = filter(lambda x: 'rank' in x, stat1)
    stat1 = sorted(stat1, key=lambda x: x['rank'],reverse=True)


    for j in range(len(pl_1),len(pl_1)+len(pl_2)):
        try:
            stat2.append(json.loads(results[j]))
        except:
            continue 
    stat2 = filter(lambda x: 'rank' in x, stat2)  
    stat2 = sorted(stat2, key=lambda x: x['rank'],reverse=True)

    img = Image.open(serverimg)
    img = img.resize((1920,1220))
    img = img.filter(ImageFilter.GaussianBlur(radius=10))
    textbox0 = Image.new("RGBA", (1920,1220), (0, 0, 0, 150))
    img.paste(textbox0, (0, 0), textbox0)

    textbox = Image.new("RGBA", (900,1200), (0, 0, 0, 0))
    teamimg = Image.open(BF1_SERVERS_DATA/f'Caches/Teams/{teamImage_1}.png').resize((80,80))
    textbox.paste(teamimg,(0,0),teamimg)
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
    draw.text(xy=(320,15), text=f'平均kd: {avkd}\n平均kp: {avkp}' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(455,27.5), text=f'             KD    KP    爆头      胜率    时长' ,fill=(255, 255, 255, 255),font=font_2)

    (BF1_SERVERS_DATA/f'{session}_pl').mkdir(exist_ok=True)
    f = open(BF1_SERVERS_DATA/f'{session}_pl'/f'{server_id}_pl.txt','w')
    f.write('{\n"pl": [\n')
    for i in range(len(stat1)):
        draw.text(xy=(35,90+30*i), text=f'{i+1}' , fill =(255, 255,255, 255),font=font_2)
        
        if stat1[i]['rank'] < 150:
            draw.rectangle([(100, 94+30*i), (140, 112+30*i)], outline='white')
        else:
            draw.rectangle([(100, 94+30*i), (140, 112+30*i)], fill=(255, 255, 0, 100))
        
        text_width, _ = font_3.getsize(str(stat1[i]['rank']))
        x = 120 - text_width / 2
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
                            draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                    else:
                        if stat1[i]['platoon'] == "":
                            draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                else:
                    if stat1[i]['platoon'] == "":
                        draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                    else:
                        draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
            else:
                if stat1[i]['platoon'] == "":
                    draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
                else:
                    draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
        else:
            if stat1[i]['platoon'] == "":
                draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
            else:
                draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
        if stat1[i]['killDeath'] > 2.5:
            draw.text(xy=(540,90+30*i), text=f'{stat1[i]["killDeath"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat1[i]['killDeath'] > 1:
            draw.text(xy=(540,90+30*i), text=f'{stat1[i]["killDeath"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(540,90+30*i), text=f'{stat1[i]["killDeath"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if stat1[i]['killsPerMinute'] > 2.5:
            draw.text(xy=(599,90+30*i), text=f'{stat1[i]["killsPerMinute"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat1[i]['killsPerMinute'] > 1:
            draw.text(xy=(599,90+30*i), text=f'{stat1[i]["killsPerMinute"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(599,90+30*i), text=f'{stat1[i]["killsPerMinute"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat1[i]['headshots'].strip('%')) / 100  > 0.2:
            draw.text(xy=(662,90+30*i), text=f'{stat1[i]["headshots"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat1[i]['headshots'].strip('%')) / 100 > 0.05:
            draw.text(xy=(662,90+30*i), text=f'{stat1[i]["headshots"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(662,90+30*i), text=f'{stat1[i]["headshots"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat1[i]['winPercent'].strip('%')) / 100 > 0.7:
            draw.text(xy=(750,90+30*i), text=f'{stat1[i]["winPercent"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat1[i]['winPercent'].strip('%')) / 100 > 0.4:
            draw.text(xy=(750,90+30*i), text=f'{stat1[i]["winPercent"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(750,90+30*i), text=f'{stat1[i]["winPercent"]}' ,fill=(173, 216, 255, 255),font=font_2)

        draw.text(xy=(837,90+30*i), text=f'{stat1[i]["secondsPlayed"]//3600}' ,fill=(255, 255, 255, 255),font=font_2)
        
        f.write('{\n"slot": %d,\n"rank": %d,\n"kd": %f,\n"kp": %f,\n"id": %d\n},\n'%(i+1,stat1[i]['rank'],stat1[i]['killDeath'],stat1[i]['killsPerMinute'],stat1[i]['id']))
    position = (60, 110)
    img.paste(textbox, position, textbox)

    textbox1 = Image.new("RGBA", (900,1200), (0, 0, 0, 0))
    teamimg = Image.open(BF1_SERVERS_DATA/f'Caches/Teams/{teamImage_2}.png').resize((80,80))
    textbox1.paste(teamimg,(0,0),teamimg)
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
    draw.text(xy=(320,15), text=f'平均kd: {avkd}\n平均kp: {avkp}' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(455,27.5), text=f'             KD    KP    爆头      胜率    时长' ,fill=(255, 255, 255, 255),font=font_2)
    
    for i in range(len(stat2)):
        draw.text(xy=(35,90+30*i), text=f'{i+33}' , fill =(255, 255,255, 255),font=font_2)
        
        if stat2[i]['rank'] < 150:
            draw.rectangle([(100, 94+30*i), (140, 112+30*i)], outline='white')
        else:
            draw.rectangle([(100, 94+30*i), (140, 112+30*i)], fill=(255, 255, 0, 100))
        
        text_width, _ = font_3.getsize(str(stat2[i]['rank']))
        x = 120 - text_width / 2
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
                            draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                    else:
                        if stat2[i]['platoon'] == "":
                            draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                else:
                    if stat2[i]['platoon'] == "":
                        draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                    else:
                        draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
            else:
                if stat2[i]['platoon'] == "":
                    draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
                else:
                    draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
        else:
            if stat2[i]['platoon'] == "":
                draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
            else:
                draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
        if stat2[i]['killDeath'] > 2.5:
            draw.text(xy=(540,90+30*i), text=f'{stat2[i]["killDeath"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat2[i]['killDeath'] > 1:
            draw.text(xy=(540,90+30*i), text=f'{stat2[i]["killDeath"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(540,90+30*i), text=f'{stat2[i]["killDeath"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if stat2[i]['killsPerMinute'] > 2.5:
            draw.text(xy=(599,90+30*i), text=f'{stat2[i]["killsPerMinute"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat2[i]['killsPerMinute'] > 1:
            draw.text(xy=(599,90+30*i), text=f'{stat2[i]["killsPerMinute"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(599,90+30*i), text=f'{stat2[i]["killsPerMinute"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat2[i]['headshots'].strip('%')) / 100  > 0.2:
            draw.text(xy=(662,90+30*i), text=f'{stat2[i]["headshots"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat2[i]['headshots'].strip('%')) / 100 > 0.05:
            draw.text(xy=(662,90+30*i), text=f'{stat2[i]["headshots"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(662,90+30*i), text=f'{stat2[i]["headshots"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat2[i]['winPercent'].strip('%')) / 100 > 0.7:
            draw.text(xy=(750,90+30*i), text=f'{stat2[i]["winPercent"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat2[i]['winPercent'].strip('%')) / 100 > 0.4:
            draw.text(xy=(750,90+30*i), text=f'{stat2[i]["winPercent"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(750,90+30*i), text=f'{stat2[i]["winPercent"]}' ,fill=(173, 216, 255, 255),font=font_2)

        draw.text(xy=(837,90+30*i), text=f'{stat2[i]["secondsPlayed"]//3600}' ,fill=(255, 255, 255, 255),font=font_2)
        f.write('{\n"slot": %d,\n"rank": %d,\n"kd": %f,\n"kp": %f,\n"id": %d\n},\n'%(i+33,stat2[i]['rank'],stat2[i]['killDeath'],stat2[i]['killsPerMinute'],stat2[i]['id']))

    f.write('{\n"slot": 100,\n"rank": 0,\n"kd": 0,\n"kp": 0,\n"id": 0\n}')
    f.write(f'],\n"id": {server_id}\n')
    f.write('}')
    f.close()    
    position = (960, 110)
    img.paste(textbox1, position, textbox1)

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
    text = f'普通玩家  群友  vip  白名单  管理'
    x = (img.width-font_0.getsize(text)[0])/2

    draw.text(xy=((img.width-font_1.getsize(serverName)[0])/2,30), text=serverName ,fill=(255, 255, 255, 255),font=font_1)
    draw.text(xy=((img.width-font_0.getsize(text)[0])/2,1180), text='普通玩家' ,fill=(255, 255, 255, 255),font=font_0)
    draw.text(xy=(x+125,1180), text='群友' ,fill=(0, 255, 255, 255),font=font_0)
    draw.text(xy=(x+200,1180), text='vip' ,fill=(255, 125, 125, 255),font=font_0)
    draw.text(xy=(x+262.5,1180), text='白名单' ,fill=(0, 255, 0, 255),font=font_0)
    draw.text(xy=(x+362.5,1180), text='管理' ,fill=(255, 255, 0, 255),font=font_0)

    draw.line((60, 190, 1860, 190), fill=(128, 128, 128, 120), width=4)
    draw.line((60, 1165, 1860, 1165), fill=(128, 128, 128, 120), width=4)

    draw.line((60, 190, 60, 1165), fill=(128, 128, 128, 120), width=4)
    draw.line((145, 190, 145, 1165), fill=(128, 128, 128, 120), width=4)
    draw.line((960, 190, 960, 1165), fill=(128, 128, 128, 120), width=4)
    draw.line((1045, 190, 1045, 1165), fill=(128, 128, 128, 120), width=4)
    draw.line((1860, 190, 1860, 1165), fill=(128, 128, 128, 120), width=4)
    
    print(datetime.datetime.now())
    img.save(BF1_SERVERS_DATA/f'Caches/{gameId}_pl.jpg')
    return 1

async def draw_pl1(session,server_id,gameId,remid, sid, sessionID):
    
    pljson = await get_blazepl(remid,sid,sessionID,gameId)
    detailedServer = await upd_detailedServer(remid, sid, sessionID, gameId)
    vipList = detailedServer['result']["rspInfo"]['vipList']
    adminList = detailedServer['result']["rspInfo"]['adminList']

    try:
        with open(BF1_PLAYERS_DATA/'whitelist'/f'{session}_{server_id}.txt') as f:
            whiteList = f.read().split(',')
    except:
        whiteList = []
        print('whitelist not found')

    try:
        personaIds = []
        for filename in os.listdir(BF1_PLAYERS_DATA/f'{session}'):
            if filename.endswith('txt'):
                id = filename.rstrip('.txt')
                personaIds.append(id.split('_')[1])
        member_json = await upd_getPersonasByIds(remid, sid, sessionID,personaIds)
        member_json = member_json['result']
        memberList = [value['displayName'] for value in member_json.values()]
    except:
        memberList = []
        print('memberList not found')
    tasks = []
    serverimg = detailedServer['result']['serverInfo']['mapImageUrl'].split('/')[5]
    serverimg = BF1_SERVERS_DATA/f'Caches/Maps/{serverimg}'
    serverName = detailedServer['result']['serverInfo']['name']

    teamImage_1 = pljson['team1']
    teamImage_2 = pljson['team2']

    print(datetime.datetime.now())

    stat1 = sorted(pljson['1'], key=lambda x: x['rank'],reverse=True)
    stat2 = sorted(pljson['2'], key=lambda x: x['rank'],reverse=True)

    img = Image.open(serverimg)
    img = img.resize((1920,1220))
    img = img.filter(ImageFilter.GaussianBlur(radius=10))
    textbox0 = Image.new("RGBA", (1920,1220), (0, 0, 0, 150))
    img.paste(textbox0, (0, 0), textbox0)

    textbox = Image.new("RGBA", (900,1200), (0, 0, 0, 0))
    teamimg = Image.open(BF1_SERVERS_DATA/f'Caches/Teams/{teamImage_1}.png').resize((80,80))
    textbox.paste(teamimg,(0,0),teamimg)
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
    draw.text(xy=(320,15), text=f'平均kd: {avkd}\n平均kp: {avkp}' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(455,27.5), text=f'             KD    KP     爆头      胜率      IP' ,fill=(255, 255, 255, 255),font=font_2)

    (BF1_SERVERS_DATA/f'{session}_pl').mkdir(exist_ok=True)
    f = open(BF1_SERVERS_DATA/f'{session}_pl'/f'{server_id}_pl.txt','w')
    f.write('{\n"pl": [\n')
    for i in range(len(stat1)):
        draw.text(xy=(35,90+30*i), text=f'{i+1}' , fill =(255, 255,255, 255),font=font_2)
        
        if stat1[i]['rank'] < 150:
            draw.rectangle([(100, 94+30*i), (140, 112+30*i)], outline='white')
        else:
            draw.rectangle([(100, 94+30*i), (140, 112+30*i)], fill=(255, 255, 0, 100))
        
        text_width, _ = font_3.getsize(str(stat1[i]['rank']))
        x = 120 - text_width / 2
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
                            draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                    else:
                        if stat1[i]['platoon'] == "":
                            draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                else:
                    if stat1[i]['platoon'] == "":
                        draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                    else:
                        draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
            else:
                if stat1[i]['platoon'] == "":
                    draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
                else:
                    draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
        else:
            if stat1[i]['platoon'] == "":
                draw.text(xy=(145,90+30*i), text=f'{stat1[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
            else:
                draw.text(xy=(145,90+30*i), text=f'[{stat1[i]["platoon"]}]{stat1[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)

        if stat1[i]['killDeath'] > 2.5:
            draw.text(xy=(540,90+30*i), text=f'{stat1[i]["killDeath"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat1[i]['killDeath'] > 1:
            draw.text(xy=(540,90+30*i), text=f'{stat1[i]["killDeath"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(540,90+30*i), text=f'{stat1[i]["killDeath"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if stat1[i]['killsPerMinute'] > 2.5:
            draw.text(xy=(599,90+30*i), text=f'{stat1[i]["killsPerMinute"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat1[i]['killsPerMinute'] > 1:
            draw.text(xy=(599,90+30*i), text=f'{stat1[i]["killsPerMinute"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(599,90+30*i), text=f'{stat1[i]["killsPerMinute"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat1[i]['headShot'].strip('%')) / 100  > 0.2:
            draw.text(xy=(662,90+30*i), text=f'{stat1[i]["headShot"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat1[i]['headShot'].strip('%')) / 100 > 0.05:
            draw.text(xy=(662,90+30*i), text=f'{stat1[i]["headShot"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(662,90+30*i), text=f'{stat1[i]["headShot"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat1[i]['winPercent'].strip('%')) / 100 > 0.7:
            draw.text(xy=(750,90+30*i), text=f'{stat1[i]["winPercent"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat1[i]['winPercent'].strip('%')) / 100 > 0.4:
            draw.text(xy=(750,90+30*i), text=f'{stat1[i]["winPercent"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(750,90+30*i), text=f'{stat1[i]["winPercent"]}' ,fill=(173, 216, 255, 255),font=font_2)

        draw.text(xy=(835,90+30*i), text=f'{stat1[i]["loc"]}/{stat1[i]["lang"]}' ,fill=(255, 255, 255, 255),font=font_2)
        
        f.write('{\n"slot": %d,\n"rank": %d,\n"kd": %f,\n"kp": %f,\n"id": %s\n},\n'%(i+1,stat1[i]['rank'],stat1[i]['killDeath'],stat1[i]['killsPerMinute'],stat1[i]['id']))
    position = (60, 110)
    img.paste(textbox, position, textbox)

    textbox1 = Image.new("RGBA", (900,1200), (0, 0, 0, 0))
    teamimg = Image.open(BF1_SERVERS_DATA/f'Caches/Teams/{teamImage_2}.png').resize((80,80))
    textbox1.paste(teamimg,(0,0),teamimg)
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
    draw.text(xy=(320,15), text=f'平均kd: {avkd}\n平均kp: {avkp}' ,fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(455,27.5), text=f'             KD    KP     爆头      胜率      IP' ,fill=(255, 255, 255, 255),font=font_2)
    
    for i in range(len(stat2)):
        draw.text(xy=(35,90+30*i), text=f'{i+33}' , fill =(255, 255,255, 255),font=font_2)
        
        if stat2[i]['rank'] < 150:
            draw.rectangle([(100, 94+30*i), (140, 112+30*i)], outline='white')
        else:
            draw.rectangle([(100, 94+30*i), (140, 112+30*i)], fill=(255, 255, 0, 100))
        
        text_width, _ = font_3.getsize(str(stat2[i]['rank']))
        x = 120 - text_width / 2
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
                            draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(255, 255, 255, 255),font=font_2)
                    else:
                        if stat2[i]['platoon'] == "":
                            draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                        else:
                            draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(0, 255, 255, 255),font=font_2)
                else:
                    if stat2[i]['platoon'] == "":
                        draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
                    else:
                        draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(255, 125, 125, 255),font=font_2)
            else:
                if stat2[i]['platoon'] == "":
                    draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
                else:
                    draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(0, 255, 0, 255),font=font_2)
        else:
            if stat2[i]['platoon'] == "":
                draw.text(xy=(145,90+30*i), text=f'{stat2[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
            else:
                draw.text(xy=(145,90+30*i), text=f'[{stat2[i]["platoon"]}]{stat2[i]["userName"]}', fill=(255, 255, 0, 255),font=font_2)
        
        if stat2[i]['killDeath'] > 2.5:
            draw.text(xy=(540,90+30*i), text=f'{stat2[i]["killDeath"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat2[i]['killDeath'] > 1:
            draw.text(xy=(540,90+30*i), text=f'{stat2[i]["killDeath"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(540,90+30*i), text=f'{stat2[i]["killDeath"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if stat2[i]['killsPerMinute'] > 2.5:
            draw.text(xy=(599,90+30*i), text=f'{stat2[i]["killsPerMinute"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif stat2[i]['killsPerMinute'] > 1:
            draw.text(xy=(599,90+30*i), text=f'{stat2[i]["killsPerMinute"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(599,90+30*i), text=f'{stat2[i]["killsPerMinute"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat2[i]['headShot'].strip('%')) / 100  > 0.2:
            draw.text(xy=(662,90+30*i), text=f'{stat2[i]["headShot"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat2[i]['headShot'].strip('%')) / 100 > 0.05:
            draw.text(xy=(662,90+30*i), text=f'{stat2[i]["headShot"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(662,90+30*i), text=f'{stat2[i]["headShot"]}' ,fill=(173, 216, 255, 255),font=font_2)

        if float(stat2[i]['winPercent'].strip('%')) / 100 > 0.7:
            draw.text(xy=(750,90+30*i), text=f'{stat2[i]["winPercent"]}' ,fill=(255, 255, 0, 255),font=font_2)
        elif float(stat2[i]['winPercent'].strip('%')) / 100 > 0.4:
            draw.text(xy=(750,90+30*i), text=f'{stat2[i]["winPercent"]}' ,fill=(255, 255, 255, 255),font=font_2)
        else:
            draw.text(xy=(750,90+30*i), text=f'{stat2[i]["winPercent"]}' ,fill=(173, 216, 255, 255),font=font_2)

        draw.text(xy=(835,90+30*i), text=f'{stat2[i]["loc"]}/{stat2[i]["lang"]}' ,fill=(255, 255, 255, 255),font=font_2)
        f.write('{\n"slot": %d,\n"rank": %d,\n"kd": %f,\n"kp": %f,\n"id": %s\n},\n'%(i+33,stat2[i]['rank'],stat2[i]['killDeath'],stat2[i]['killsPerMinute'],stat2[i]['id']))

    f.write('{\n"slot": 100,\n"rank": 0,\n"kd": 0,\n"kp": 0,\n"id": 0\n}')
    f.write(f'],\n"id": {server_id}\n')
    f.write('}')
    f.close()    
    position = (960, 110)
    img.paste(textbox1, position, textbox1)

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
    text = f'普通玩家  群友  vip  白名单  管理'
    x = (img.width-font_0.getsize(text)[0])/2

    draw.text(xy=((img.width-font_1.getsize(serverName)[0])/2,30), text=serverName ,fill=(255, 255, 255, 255),font=font_1)
    draw.text(xy=((img.width-font_0.getsize(text)[0])/2,1180), text='普通玩家' ,fill=(255, 255, 255, 255),font=font_0)
    draw.text(xy=(x+125,1180), text='群友' ,fill=(0, 255, 255, 255),font=font_0)
    draw.text(xy=(x+200,1180), text='vip' ,fill=(255, 125, 125, 255),font=font_0)
    draw.text(xy=(x+262.5,1180), text='白名单' ,fill=(0, 255, 0, 255),font=font_0)
    draw.text(xy=(x+362.5,1180), text='管理' ,fill=(255, 255, 0, 255),font=font_0)

    draw.line((60, 190, 1860, 190), fill=(128, 128, 128, 120), width=4)
    draw.line((60, 1165, 1860, 1165), fill=(128, 128, 128, 120), width=4)

    draw.line((60, 190, 60, 1165), fill=(128, 128, 128, 120), width=4)
    draw.line((145, 190, 145, 1165), fill=(128, 128, 128, 120), width=4)
    draw.line((960, 190, 960, 1165), fill=(128, 128, 128, 120), width=4)
    draw.line((1045, 190, 1045, 1165), fill=(128, 128, 128, 120), width=4)
    draw.line((1860, 190, 1860, 1165), fill=(128, 128, 128, 120), width=4)
    
    print(datetime.datetime.now())
    img.save(BF1_SERVERS_DATA/f'Caches/{gameId}_pl.jpg')
    return 1

async def draw_r(remid, sid, sessionID, personaId, playerName):
    print(datetime.datetime.now())
    tasks = []
    tasks.append(asyncio.create_task(upd_StatsByPersonaId(remid, sid, sessionID, personaId)))
    tasks.append(asyncio.create_task(upd_Emblem(remid, sid, sessionID, personaId)))

    personaIds=[]
    personaIds.append(personaId)
    tasks.append(asyncio.create_task(upd_getActiveTagsByPersonaIds(remid,sid,sessionID,personaIds)))
    tasks.append(asyncio.create_task(async_bftracker_recent(playerName, 10)))
    res_stat,emblem,res_tag,async_result = await asyncio.gather(*tasks)

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
    print(datetime.datetime.now())

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
    if 'player not found' in async_result:
        return 0
    else:
        for i in range(10):
            data = async_result[i]
            try:
                if data['Kills'] > 5 or data['Deaths'] > 5:
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
        img = Image.open(BF1_SERVERS_DATA/'Caches'/'background'/f'DLC{random.randint(1, 6)}.jpg')
        img = img.resize((1300,1800))
        img = img.crop((0,0,1300,(410*len(recent)+410)))
        img = img.filter(ImageFilter.GaussianBlur(radius=15))

    textbox = Image.new("RGBA", (1300,250), (254, 238, 218, 180))
    draw = ImageDraw.Draw(textbox)
    font_1 = ImageFont.truetype(font='msyhbd.ttc', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=40, encoding='UTF-8')
    font_3 = ImageFont.truetype(font='comic.ttf', size=36, encoding='UTF-8')
    font_4 = ImageFont.truetype(font='Dengb.ttf', size=40, encoding='UTF-8')
    font_5 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
    if tag == '':
        text=f'{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,15), text=text, fill=(55, 1, 27, 255),font=font_1)
    else:
        text=f'[{tag}]{name}'
        draw.text(xy=(775-font_1.getsize(text)[0]/2,15), text=text, fill=(55, 1, 27, 255),font=font_1)

    draw.text(xy=(290,95), text=f'游玩时长:{secondsPlayed//3600}小时\n击杀数:{k}\n死亡数:{d}', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(680,95), text=f'获胜率:{0 if win+loss == 0 else win*100/(win+loss):.2f}%\n命中率:{acc*100:.2f}%\n爆头率:{0 if k == 0 else hs/k*100:.2f}%', fill=(66, 112, 244, 255),font=font_2)
    try:
        draw.text(xy=(1070,95), text=f'K/D:{kd:.2f}\nKPM:{kpm}\nDPM:{round((d*60)/secondsPlayed,2)}', fill=(66, 112, 244, 255),font=font_2)
    except:
        draw.text(xy=(1070,95), text=f'K/D:{kd:.2f}\nKPM:{kpm}\nDPM:0.00)', fill=(66, 112, 244, 255),font=font_2)
    
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
        text=f'{recent[i]["server"]}'

        match = re.search(r'(\d+)m(\d+)s', recent[i]['duration'])
        if match:
                minute = match.group(1)
                second = match.group(2)
                result = f"{minute}分{second}秒"
        elif re.search(r'(\d+)s', recent[i]['duration']):
                minute = 0
                second = recent[i]['duration'][0:-1]
                result = f"{minute}分{second}秒"
        elif re.search(r'(\d+)m', recent[i]['duration']):
                minute = recent[i]['duration'][0:-1]
                second = 0
                result = f"{minute}分{second}秒"
        else:
            minute = 0
            second = 0
            result = f"{minute}分{second}秒"

        mapandmode = dict[recent[i]["map"]] + '-' +dict[recent[i]["mode"]]
        draw.text(xy=(0,4), text=text[0:30], fill=(55, 1, 27, 255),font=font_3)
        draw.text(xy=((550+font_2.getsize(text[0:30])[0]/2-font_2.getsize(mapandmode)[0]/2),10), text=mapandmode, fill=(55, 1, 27, 255),font=font_2)
        if recent[i]["result"] == '胜利':
            draw.text(xy=((1200-font_2.getsize(recent[i]["result"])[0]/2),10), text=recent[i]["result"], fill=(100, 255, 50, 255),font=font_2)
        elif recent[i]["result"] == '落败':
            draw.text(xy=((1200-font_2.getsize(recent[i]["result"])[0]/2),10), text=recent[i]["result"], fill=(255, 105, 93, 255),font=font_2)
        elif recent[i]["result"] == '未结算':
            draw.text(xy=((1200-font_2.getsize(recent[i]["result"])[0]/2),10), text=recent[i]["result"], fill=(55, 1, 27, 255),font=font_2)

        draw.text(xy=(640,90), text=f'时长:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,90), text=f'{result}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,90), text=f'得分:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,90), text=f'{recent[i]["Score"]}', fill=(66, 112, 244, 255),font=font_4)
        
        draw.text(xy=(640,141), text=f'击杀:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,141), text=f'{recent[i]["Kills"]}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,141), text=f'死亡:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,141), text=f'{recent[i]["Deaths"]}', fill=(66, 112, 244, 255),font=font_4)

        draw.text(xy=(640,192), text=f'KDA:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,192), text=f'{recent[i]["kd"]}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,192), text=f'KPM:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,192), text=f'{((6000*int(recent[i]["Kills"]))//(60*int(minute)+int(second)))/100}', fill=(66, 112, 244, 255),font=font_4)
        
        draw.text(xy=(640,243), text=f'K/D:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,243), text=f'{recent[i]["K/D"]}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,243), text=f'SPM:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,243), text=f'{(60*int(recent[i]["Score"].replace(",", "")))//(60*int(minute)+int(second))}', fill=(66, 112, 244, 255),font=font_4)

        draw.text(xy=(640,294), text=f'命中:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(750,294), text=f'{recent[i]["acc"]}', fill=(66, 112, 244, 255),font=font_4)
        draw.text(xy=(960,294), text=f'爆头:', fill=(255,100,0,255),font=font_4)
        draw.text(xy=(1070,294), text=f'{(recent[i]["headshot"] *1000 // recent[i]["Kills"] ) / 10 if recent[i]["Kills"] else 0}%', fill=(66, 112, 244, 255),font=font_4)

        date_str = recent[i]["matchDate"]
        dt = datetime.datetime.strptime(date_str, '%m/%d/%Y %I:%M:%S %p')
        offset = datetime.timedelta(hours=13)
        dt = dt + offset
        formatted_dt = '数据记录时间: ' + dt.strftime('%Y/%m/%d %H:%M:%S')
 
        draw.text(xy=((925-font_5.getsize(formatted_dt)[0]/2),360), text=formatted_dt, fill=(34,139,34, 255),font=font_5)
        position = (0, 360+410*i)
        img.paste(textbox0,position,textbox0)
        img.paste(textbox1,position,textbox1)

        timeall += 60*int(minute) + int(second)
        killall += recent[i]["Kills"]
        deathall += recent[i]["Deaths"]
    
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
    print(datetime.datetime.now())
    img.save(BF1_SERVERS_DATA/f'Caches/{playerName}_r.jpg')

    return 1

async def draw_exchange(remid, sid, sessionID):
    res = await upd_exchange(remid, sid, sessionID)
    img = Image.new("RGBA", (1500,1100), (254, 238, 218, 180))
    tasks = []
    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=20, encoding='UTF-8')
    for i in range(len(res['result']['items'])):
        url = 'https://eaassets-a.akamaihd.net/battlelog/battlebinary/'+res['result']['items'][i]['item']['images']['Png180xANY'][11:]
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
            draw.text(xy=(140+200*(i%7)-0.5*font_0.getsize(text1)[0],170+150*(i//7)), text=text1 ,fill=(55, 1, 27, 255),font=font_0)

        draw.text(xy=(140+200*(i%7)-0.5*font_0.getsize(text2)[0],190+150*(i//7)), text=text2 ,fill=(0, 0, 100, 255),font=font_0)
        tasks.append(asyncio.create_task(paste_image(url,img,position)))

    await asyncio.gather(*tasks)
    
    font_1 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas. QQ: 120681532. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(1500-font_1.getsize(text)[0],1065), text=text ,fill=(34,139,34, 255),font=font_1)

    img.save(BF1_SERVERS_DATA/f'Caches/exchange.png')
    return 1

async def draw_a(num,name,personaId):
    img = Image.new("RGBA", (900,30*num), (254, 238, 218, 180))
    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='Dengb.ttf', size=25, encoding='UTF-8')
    for i in range(num):
         draw.text(xy=(10,30*i), text=str(i+1)+'. '+name[i] ,fill=(0, 0, 100, 255),font=font_0)
    img.save(BF1_SERVERS_DATA/f'Caches/{personaId}.png')
    return 1