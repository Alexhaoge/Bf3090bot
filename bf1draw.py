from PIL import Image, ImageDraw, ImageFilter, ImageFont
import requests
import json
import uuid
import re
import os
import zhconv
import datetime
import asyncio
import httpx
from io import BytesIO
from .bf1rsp import upd_detailedServer, upd_servers, upd_Emblem, upd_getPersonasByIds, async_bftracker_recent
from .utils import BF1_SERVERS_DATA, BF1_PLAYERS_DATA, request_API

GAME = 'bf1'
LANG = 'zh-tw'

async def draw_f(server_id:int,session:int,remid, sid, sessionID):
    # 打开图片文件
    img = Image.open(BF1_SERVERS_DATA/'Caches/DLC1.jpg')
    img = img.resize((1506,2100))
    img = img.crop((0,0,1506,400*server_id+100))
    # 将原始图片模糊化
    img = img.filter(ImageFilter.GaussianBlur(radius=15))
    for id in range(server_id):
        with open(BF1_SERVERS_DATA/f'{session}_jsonGT'/f'{session}_{id+1}.json','r', encoding='utf-8') as f:
            serverGT = json.load(f)
            gameId = serverGT['gameId']
            
        res =  await upd_detailedServer(remid, sid, sessionID, gameId)
        servername = res['result']['serverInfo']['name']
        servermap = res['result']['serverInfo']['mapNamePretty']
        serveramount = res['result']['serverInfo']['slots']['Soldier']['current']
        serverspect = res['result']['serverInfo']['slots']['Spectator']['current']
        serverque = res['result']['serverInfo']['slots']['Queue']['current']
        servermaxamount = res['result']['serverInfo']['slots']['Soldier']['max']
        servermode = res['result']['serverInfo']['mapModePretty']
        serverstar = res['result']['serverInfo']['serverBookmarkCount']
        serverinfo = '简介：' + res['result']['serverInfo']['description']
        serverimg = res['result']['serverInfo']['mapImageUrl'].split('/')[5]
        serverimg = BF1_SERVERS_DATA/f'Caches/Maps/{serverimg}'

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
        position0 = (60, 60+400*id)
        position = (60, 140+400*id)
        img.paste(textbox0, position0, textbox0)
        img.paste(textbox, position, textbox)

        background = Image.open(serverimg).resize((480,300))
        img.paste(background, position)
        
    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas.QQ Group: 94103090. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],400*server_id+65), text=text ,fill=(255, 255, 0, 255),font=font_0)
    img.save(BF1_SERVERS_DATA/f'Caches/{session}.jpg')
    return 1

async def draw_server(remid, sid, sessionID, serverName, res):
    img = Image.open(BF1_SERVERS_DATA/f'Caches/DLC1.jpg')
    img = img.resize((1506,2020))
    img = img.filter(ImageFilter.GaussianBlur(radius=15))

    res = res['result']['gameservers']
    res = sorted(res, key=lambda x: x['slots']['Soldier']['current'],reverse=True)
    if (len(res)) <5:
        if len(res) == 0:
            return 0
        else:
            img = img.crop((0,0,1506,400*len(res)+100))

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
        serverimg = res[ij]['mapImageUrl'].split('/')[5]
        serverimg = BF1_SERVERS_DATA/f'Caches/Maps/{serverimg}'
        gameId = res[ij]['gameId']
        res_0 =  await upd_detailedServer(remid, sid, sessionID, gameId)
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
    text = f'Powered by Mag1Catz and special thanks to Openblas.QQ Group: 94103090. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
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

async def draw_stat(remid, sid, sessionID,res:dict,playerName:str):
    name = res['userName']
    tag = res['activePlatoon']['tag']
    personaId = res['id']
    rank = res['rank']
    skill = res['skill']
    spm = res['scorePerMinute']
    kpm = res['killsPerMinute']
    win = res['winPercent']
    bestClass= res['bestClass']
    acc = res['accuracy']
    hs = res['headshots']
    secondsPlayed = res['secondsPlayed']
    kd = res['killDeath']
    k = res['kills']
    d = res['deaths']
    longhs = res['longestHeadShot']
    rev = res['revives']
    dogtags = res['dogtagsTaken']
    ks = res["highestKillStreak"]
    avenge = res["avengerKills"]
    save = res["saviorKills"]
    heals = res["heals"]
    repairs = res["repairs"]
    killAssists = res["killAssists"]
    classes = res["classes"]

    gamemode = sorted(res['gamemodes'], key=lambda x: x['score'],reverse=True)
    gamemodes = []
    for i in gamemode:
        if i['gamemodeName'] == '閃擊行動':
            continue
        else:
            gamemodes.append(i)

    emblem = await upd_Emblem(remid, sid, sessionID, personaId)
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

    print(emblem)

    vehicles = sorted(res['vehicles'], key=lambda x: x['kills'],reverse=True)
    weapons = sorted(res['weapons'], key=lambda x: x['kills'],reverse=True)

    carkill = 0
    cartime = 0
    for i in vehicles:
        carkill = carkill + i['kills']
        cartime = cartime + i['timeIn']
    try:
        carkp = (carkill*6000 // cartime)/100
    except:
        carkp = 0

    infantrykill = k - carkill
    infantrytime = secondsPlayed - cartime

    try:
        infantrykp = (infantrykill*6000 // infantrytime)/100
    except:
        infantrykp = 0

    json_class = {
        'Medic': '医疗兵',
        'Support': '支援兵',
        'Assault': '突击兵',
        'Scout': '侦察兵',
        'Cavalry': '骑兵',
        'Pilot': '飞行员',
        'tanker': '坦克'
    }

    try:
        img_emb = Image.open(requests.get(emblem, stream=True,timeout=20).raw).resize((250,250)).convert("RGBA")
    except:
        img_emb = Image.open(BF1_SERVERS_DATA/'Caches'/'DLC1.jpg')

    try:
        img = Image.open(BF1_PLAYERS_DATA/'Caches'/f'{personaId}.jpg')
    except:    
        img = Image.open(BF1_SERVERS_DATA/'Caches'/'DLC1.jpg')

    
    img = img.resize((1500,1500))

    textbox = Image.new("RGBA", (1500,1500), (0, 0, 0, 50))
    img.paste(textbox, (0, 0), textbox)

    textbox = Image.new("RGBA", (1300,250), (0, 0, 0, 150))
    draw = ImageDraw.Draw(textbox)
    font_1 = ImageFont.truetype(font='msyhbd.ttc', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=40, encoding='UTF-8')
    if tag == None:
        draw.text(xy=(290,15), text=f'{name}', fill=(255, 255, 0, 255),font=font_1)
    else:
        draw.text(xy=(290,15), text=f'[{tag}]{name}', fill=(255, 255, 0, 255),font=font_1)
    draw.text(xy=(1000,15), text=f'Rank: {rank}', fill=(255, 255, 0, 255),font=font_1)
    draw.text(xy=(290,95), text=f'游玩时长:{secondsPlayed//3600}小时\n击杀数:{k}\n死亡数:{d}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,95), text=f'获胜率:{win}\n命中率:{acc}\n爆头率:{hs}', fill=(255, 255, 255, 255),font=font_2)
    try:
        draw.text(xy=(1070,95), text=f'K/D:{kd}\nKPM:{kpm}\nDPM:{round((d*60)/secondsPlayed,2)}', fill=(255, 255, 255, 255),font=font_2)
    except:
        draw.text(xy=(1070,95), text=f'K/D:{kd}\nKPM:{kpm}\nDPM:0.00)', fill=(255, 255, 255, 255),font=font_2)
    position = (100, 100)
    img.paste(textbox, position, textbox)

    textbox1 = Image.new("RGBA", (640,350), (0, 0, 0, 150))
    draw = ImageDraw.Draw(textbox1)
    font_3 = ImageFont.truetype(font='Dengb.ttf', size=45, encoding='UTF-8')
    font_4 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    draw.text(xy=(120,30), text=f'最佳兵种:    {json_class[bestClass]}', fill=(255, 255, 255, 255),font=font_3)

    draw.text(xy=(35,95), text=f'最远爆头:{longhs}m', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,140), text=f'最高连杀:{ks}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,185), text=f'协助击杀:{int(killAssists)}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,230), text=f'复仇击杀:{avenge}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,275), text=f'救星击杀:{save}', fill=(255, 255, 255, 255),font=font_4)

    draw.text(xy=(360,95), text=f'技巧值:{skill}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,140), text=f'狗牌数:{dogtags}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,185), text=f'救援数:{int(rev)}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,230), text=f'治疗数:{int(heals)}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,275), text=f'修理数:{int(repairs)}', fill=(255, 255, 255, 255),font=font_4)

    position1 = (100, 380)
    img.paste(textbox1, position1, textbox1)

    textbox2 = Image.new("RGBA", (640,280), (0, 0, 0, 150))
    draw = ImageDraw.Draw(textbox2)
    
    smallmode = gamemodes[2]["wins"]+gamemodes[2]["losses"]+gamemodes[3]["wins"]+gamemodes[3]["losses"]+gamemodes[4]["wins"]+gamemodes[4]["losses"]+gamemodes[5]["wins"]+gamemodes[5]["losses"]+gamemodes[6]["wins"]+gamemodes[6]["losses"]
    
    try:
        smwp = ((gamemodes[2]["wins"]+gamemodes[3]["wins"]+gamemodes[4]["wins"]+gamemodes[5]["wins"]+gamemodes[6]["wins"])*100) / smallmode
        draw.text(xy=(360,120), text=f'其他胜率:{smwp:.2f}%', fill=(255, 255, 255, 255),font=font_4)
    except:
        smwp = 0
        draw.text(xy=(360,120), text=f'其他胜率:{smwp:.1f}%', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,30), text=f'{gamemodes[0]["gamemodeName"][0:2]}场次:{gamemodes[0]["wins"]+gamemodes[0]["losses"]}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,75), text=f'{gamemodes[1]["gamemodeName"][0:2]}场次:{gamemodes[1]["wins"]+gamemodes[1]["losses"]}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,120), text=f'其他场次:{smallmode}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,165), text=f'步兵击杀:{infantrykill}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(35,210), text=f'载具击杀:{carkill}', fill=(255, 255, 255, 255),font=font_4)

    draw.text(xy=(360,30), text=f'{gamemodes[0]["gamemodeName"][0:2]}胜率:{gamemodes[0]["winPercent"]}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,75), text=f'{gamemodes[1]["gamemodeName"][0:2]}胜率:{gamemodes[1]["winPercent"]}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,165), text=f'步兵KPM:{infantrykp}', fill=(255, 255, 255, 255),font=font_4)
    draw.text(xy=(360,210), text=f'载具KPM:{carkp}', fill=(255, 255, 255, 255),font=font_4)

    position2 = (100, 760)
    img.paste(textbox2, position2, textbox2)

    textbox3 = Image.new("RGBA", (640,330), (0, 0, 0, 150))
    draw = ImageDraw.Draw(textbox3)
    font_5 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    draw.text(xy=(80,150), text=f'{zhconv.convert(vehicles[0]["vehicleName"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
    kill1 = vehicles[0]['kills']
    star = kill1 // 100 #★{serverstar
    if star < 50:
        draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 255, 255),font=font_5)
    elif star < 100:
        draw.text(xy=(10,10), text=f'★{star}', fill=(0, 255, 0, 255),font=font_5)
    else:
        draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 0, 255),font=font_5)

    draw.text(xy=(10,177), text=f'----------------------------------', fill=(255, 255, 255, 150),font=font_5)
    draw.text(xy=(80,225), text=f'击杀:{kill1}', fill=(255, 255, 255, 255),font=font_5)
    draw.text(xy=(80,270), text=f'KPM:{vehicles[0]["killsPerMinute"]}', fill=(255, 255, 255, 255),font=font_5)
    draw.text(xy=(380,225), text=f'摧毁:{vehicles[0]["destroyed"]}', fill=(255, 255, 255, 255),font=font_5)
    draw.text(xy=(380,270), text=f'时间:{vehicles[0]["timeIn"]//3600}h', fill=(255, 255, 255, 255),font=font_5)
    position3 = (100, 1070)
    img.paste(textbox3, position3, textbox3)

    for i in range(3):
        textbox3 = Image.new("RGBA", (640,330), (0, 0, 0, 150))
        draw = ImageDraw.Draw(textbox3)
        draw.text(xy=(80,150), text=f'{zhconv.convert(weapons[i]["weaponName"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
        kill1 = weapons[i]['kills']
        star = kill1 // 100 #★{serverstar
        if star < 50:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 255, 255),font=font_5)
        elif star < 100:
            draw.text(xy=(10,10), text=f'★{star}', fill=(0, 255, 0, 255),font=font_5)
        else:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 0, 255),font=font_5)

        try:
            acc = (weapons[i]["shotsHit"]*100)// weapons[i]["shotsFired"]
        except:
            acc = 'infinity'

        draw.text(xy=(10,177), text=f'----------------------------------', fill=(255, 255, 255, 150),font=font_5)
        draw.text(xy=(80,210), text=f'击杀:{kill1}\nKPM:{weapons[i]["killsPerMinute"]}\n命中:{acc}%', fill=(255, 255, 255, 255),font=font_5)
        draw.text(xy=(380,210), text=f'效率:{weapons[i]["hitVKills"]}\n爆头:{weapons[i]["headshots"]}\n时间:{weapons[i]["timeEquipped"]//3600}h', fill=(255, 255, 255, 255),font=font_5)

        position3 = (760, 380+i*345)
        img.paste(textbox3, position3, textbox3)

        wp_img = vehicles[0]["image"].split('/')
        wp_img = BF1_SERVERS_DATA/'Caches'/'Weapons'/f'{weapons[i]["image"].split("/")[len(wp_img)-1]}'
        img_wp = Image.open(wp_img).resize((400,100)).convert("RGBA")
        img.paste(paste_img(img_wp), (880, 345*i+410), img_wp)

    img_class = Image.open(BF1_SERVERS_DATA/f'Caches/Classes/{bestClass}.png').resize((45,45)).convert("RGBA")
    img.paste(paste_img(img_class), (415, 409), img_class)

    vehicles_img = vehicles[0]["image"].split('/')
    vehicles_img = BF1_SERVERS_DATA/'Caches'/'Weapons'/f'{vehicles[0]["image"].split("/")[len(vehicles_img)-1]}'
    img_vehicles = Image.open(vehicles_img).resize((400,100)).convert("RGBA")
    img.paste(paste_img(img_vehicles), (220, 1100), img_vehicles)
    
    img.paste(img_emb, (100, 100),img_emb)

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas.QQ Group: 94103090. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],1465), text=text ,fill=(255, 255, 0, 255),font=font_0)
 
    img.save(BF1_SERVERS_DATA/f'Caches/{playerName}.jpg')
    return 1
#draw_f(4,248966716,remid, sid, sessionID)

async def draw_wp(remid, sid, sessionID, res:dict, playerName:str, mode:int):
    name = res['userName']
    tag = res['activePlatoon']['tag']
    personaId = res['id']
    rank = res['rank']
    kpm = res['killsPerMinute']
    win = res['winPercent']
    acc = res['accuracy']
    hs = res['headshots']
    secondsPlayed = res['secondsPlayed']
    kd = res['killDeath']
    k = res['kills']
    d = res['deaths']

    emblem = await upd_Emblem(remid, sid, sessionID, personaId)
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
        img_emb = Image.open(requests.get(emblem, stream=True,timeout=20).raw).resize((250,250)).convert("RGBA")
    except:
        img_emb = Image.open(BF1_SERVERS_DATA/'Caches'/'DLC1.jpg')
    print(emblem)
    
    try:
        img = Image.open(BF1_PLAYERS_DATA/'Caches'/f'{personaId}.jpg')
    except:    
        img = Image.open(BF1_SERVERS_DATA/'Caches'/'DLC1.jpg')

    img = img.resize((2000,2000))
    img = img.crop((350,0,1650,2000))
    
    textbox = Image.new("RGBA", (1300,2000), (0, 0, 0, 50))
    img.paste(textbox, (0, 0), textbox)

    textbox = Image.new("RGBA", (1300,250), (0, 0, 0, 150))
    draw = ImageDraw.Draw(textbox)
    font_1 = ImageFont.truetype(font='msyhbd.ttc', size=50, encoding='UTF-8')
    font_2 = ImageFont.truetype(font='Dengb.ttf', size=40, encoding='UTF-8')
    font_5 = ImageFont.truetype(font='Dengb.ttf', size=35, encoding='UTF-8')
    if tag == None:
        draw.text(xy=(290,15), text=f'{name}', fill=(255, 255, 0, 255),font=font_1)
    else:
        draw.text(xy=(290,15), text=f'[{tag}]{name}', fill=(255, 255, 0, 255),font=font_1)
    draw.text(xy=(1000,15), text=f'Rank: {rank}', fill=(255, 255, 0, 255),font=font_1)
    draw.text(xy=(290,95), text=f'游玩时长:{secondsPlayed//3600}小时\n击杀数:{k}\n死亡数:{d}', fill=(255, 255, 255, 255),font=font_2)
    draw.text(xy=(680,95), text=f'获胜率:{win}\n命中率:{acc}\n爆头率:{hs}', fill=(255, 255, 255, 255),font=font_2)
    try:
        draw.text(xy=(1070,95), text=f'K/D:{kd}\nKPM:{kpm}\nDPM:{round((d*60)/secondsPlayed,2)}', fill=(255, 255, 255, 255),font=font_2)
    except:
        draw.text(xy=(1070,95), text=f'K/D:{kd}\nKPM:{kpm}\nDPM:0.00)', fill=(255, 255, 255, 255),font=font_2)
    position = (0, 0)
    img.paste(textbox, position, textbox)

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

        for i in res['weapons']:
            match i['type']:
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

        for i in range(len(mode_3)):
            if mode_3[i]['weaponName'] == 'M1917 卡賓槍（巡邏）':
                m1917 = i
            elif mode_3[i]['weaponName'] == '卡爾卡諾 M91 卡賓槍（巡邏）':
                m91 = i

        mode_12.append(mode_3[m1917])
        mode_8.append(mode_3[m91])
        del mode_3[m91]
        del mode_3[m1917]

        for i in range(len(mode_5)):
            if mode_5[i]['weaponName'] == '三八式步槍（巡邏）':
                m38 = i
                break  
        mode_8.append(mode_5[m38])
        del mode_5[m38]

        match mode:
            case 0:
                weapons = res['weapons']
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
        weapons = sorted(weapons, key=lambda x: x['kills'],reverse=True)

    else:
        mode_13 = []
        mode_14 = []
        mode_15 = []

        vehicles = res['vehicles']
        for i in range(len(vehicles)-1,-1,-1):
            match vehicles[i]['type']:
                case '攻擊機':
                    mode_13.append(vehicles[i])
                    del vehicles[i]
                case '轟炸機':
                    mode_14.append(vehicles[i])
                    del vehicles[i]
                case '戰鬥機':
                    mode_15.append(vehicles[i])
                    del vehicles[i]
        
        attack = {
            "vehicleName": "攻击机",
            "type": "攻擊機",
            "image": "https://eaassets-a.akamaihd.net/battlelog/battlebinary/gamedata/Tunguska/63/53/GERHalberstadtCLII-c1cb8257.png",
            "kills": mode_13[0]['kills']+mode_13[1]['kills']+mode_13[2]['kills']+mode_13[3]['kills'],
            "killsPerMinute": 1.19,
            "destroyed": mode_13[0]['destroyed']+mode_13[1]['destroyed']+mode_13[2]['destroyed']+mode_13[3]['destroyed'],
            "timeIn": mode_13[0]['timeIn']+mode_13[1]['timeIn']+mode_13[2]['timeIn']+mode_13[3]['timeIn']
        }
        try:
            kpm = ((attack["kills"]*6000) // attack["timeIn"])/100
            attack.update({"killsPerMinute": kpm})
        except:
            attack.update({"killsPerMinute": 0})

        bomber = {
            "vehicleName": "轰炸机",
            "type": "轟炸機",
            "image": "https://eaassets-a.akamaihd.net/battlelog/battlebinary/gamedata/Tunguska/84/65/GERGothaGIV-54bfb0bf.png",
            "kills": mode_14[0]['kills']+mode_14[1]['kills']+mode_14[2]['kills']+mode_14[3]['kills'],
            "killsPerMinute": 1.19,
            "destroyed": mode_14[0]['destroyed']+mode_14[1]['destroyed']+mode_14[2]['destroyed']+mode_14[3]['destroyed'],
            "timeIn": mode_14[0]['timeIn']+mode_14[1]['timeIn']+mode_14[2]['timeIn']+mode_14[3]['timeIn']
        }
        try:
            kpm = ((bomber["kills"]*6000) // bomber["timeIn"])/100
            bomber.update({"killsPerMinute": kpm})
        except:
            bomber.update({"killsPerMinute": 0})

        fight = {
            "vehicleName": "战斗机",
            "type": "戰鬥機",
            "image": "https://eaassets-a.akamaihd.net/battlelog/battlebinary/gamedata/Tunguska/113/96/FRA_SPAD_X_XIII-8f60a194.png",
            "kills": mode_15[0]['kills']+mode_15[1]['kills']+mode_15[2]['kills']+mode_15[3]['kills'],
            "killsPerMinute": 1.19,
            "destroyed": mode_15[0]['destroyed']+mode_15[1]['destroyed']+mode_15[2]['destroyed']+mode_15[3]['destroyed'],
            "timeIn": mode_15[0]['timeIn']+mode_15[1]['timeIn']+mode_15[2]['timeIn']+mode_15[3]['timeIn']
        }
        try:
            kpm = ((fight["kills"]*6000) // fight["timeIn"])/100
            fight.update({"killsPerMinute": kpm})
        except:
            fight.update({"killsPerMinute": 0})

        vehicles.append(attack)
        vehicles.append(bomber)
        vehicles.append(fight)
        
        weapons = sorted(vehicles, key=lambda x: x['kills'],reverse=True)

    for i in range(min(10,len(weapons)-1)):
        textbox3 = Image.new("RGBA", (645,330), (0, 0, 0, 150))
        draw = ImageDraw.Draw(textbox3)

        kill1 = weapons[i]['kills']
        star = kill1 // 100 #★{serverstar
        if star < 50:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 255, 255),font=font_5)
        elif star < 100:
            draw.text(xy=(10,10), text=f'★{star}', fill=(0, 255, 0, 255),font=font_5)
        else:
            draw.text(xy=(10,10), text=f'★{star}', fill=(255, 255, 0, 255),font=font_5)

        try:
            acc = (weapons[i]["shotsHit"]*100)// weapons[i]["shotsFired"]
        except:
            acc = 'infinity'
        
        if mode == 13:
            draw.text(xy=(80,150), text=f'{zhconv.convert(weapons[i]["vehicleName"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(10,177), text=f'-----------------------------------', fill=(255, 255, 255, 150),font=font_5)
            draw.text(xy=(80,225), text=f'击杀:{kill1}', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(80,270), text=f'KPM:{weapons[i]["killsPerMinute"]}', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(380,225), text=f'摧毁:{weapons[i]["destroyed"]}', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(380,270), text=f'时间:{weapons[i]["timeIn"]//3600}h', fill=(255, 255, 255, 255),font=font_5)
        else:
            draw.text(xy=(80,150), text=f'{zhconv.convert(weapons[i]["weaponName"],"zh-cn")}', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(10,177), text=f'-----------------------------------', fill=(255, 255, 255, 150),font=font_5)
            draw.text(xy=(80,210), text=f'击杀:{kill1}\nKPM:{weapons[i]["killsPerMinute"]}\n命中:{str(acc)}%', fill=(255, 255, 255, 255),font=font_5)
            draw.text(xy=(380,210), text=f'效率:{weapons[i]["hitVKills"]}\n爆头:{weapons[i]["headshots"]}\n时间:{weapons[i]["timeEquipped"]//3600}h', fill=(255, 255, 255, 255),font=font_5)

        position3 = (655*(i%2), 260+(i//2)*340)
        img.paste(textbox3, position3, textbox3)

        wp_img = weapons[i]["image"].split('/')
        wp_img = BF1_SERVERS_DATA/'Caches'/'Weapons'/f'{weapons[i]["image"].split("/")[len(wp_img)-1]}'
        img_wp = Image.open(wp_img).resize((400,100)).convert("RGBA")
        img.paste(paste_img(img_wp), (130+650*(i%2), 340*(i//2)+300), img_wp)

    img.paste(img_emb, (0, 0), img_emb)

    draw = ImageDraw.Draw(img)
    font_0 = ImageFont.truetype(font='comic.ttf', size=25, encoding='UTF-8')
    text = f'Powered by Mag1Catz and special thanks to Openblas.QQ Group: 94103090. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
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
    
async def draw_pl(session,pl,gameId,remid, sid, sessionID):

    detailedServer = await upd_detailedServer(remid, sid, sessionID, gameId)
    vipList = detailedServer['result']["rspInfo"]['vipList']
    adminList = detailedServer['result']["rspInfo"]['adminList']

    try:
        with open(BF1_PLAYERS_DATA/'whitelist'/f'{session}.txt') as f:
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
        member_json = upd_getPersonasByIds(remid, sid, sessionID,personaIds)['result']
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

    stat1 = []
    stat2 = []
    for i in range(len(pl_1)):
        stat1.append(json.loads(results[i]))
    stat1 = sorted(stat1, key=lambda x: x['rank'],reverse=True)


    for j in range(len(pl_1),len(pl_1)+len(pl_2)):
        stat2.append(json.loads(results[j])) 
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
    
    img.save(BF1_SERVERS_DATA/f'Caches/{gameId}_pl.jpg')
    return 1

async def draw_r(playerName, res, remid, sid, sessionID):
    name = res['userName']
    tag = res['activePlatoon']['tag']
    personaId = res['id']
    rank = res['rank']
    kpm = res['killsPerMinute']
    win = res['winPercent']
    acc = res['accuracy']
    hs = res['headshots']
    secondsPlayed = res['secondsPlayed']
    kd = res['killDeath']
    k = res['kills']
    d = res['deaths']
    print(datetime.datetime.now())
    emblem = await upd_Emblem(remid, sid, sessionID, personaId)
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
        img_emb = Image.open(requests.get(emblem, stream=True,timeout=20).raw).resize((250,250)).convert("RGBA")
    except:
        img_emb = Image.open(BF1_SERVERS_DATA/'Caches'/'DLC1.jpg')
    print(emblem)
    print(datetime.datetime.now())
    async_result = await async_bftracker_recent(playerName, 10)
    recent = []
    count = 0
    print(datetime.datetime.now())
    if 'player not found' in async_result:
        return 0
    else:
        for i in range(10):
            data = async_result[i]
            if data['Kills'] > 5 or data['Deaths'] > 5:
                recent.append(data)
                count += 1
                if count == 3:
                    break

    try:
        img = Image.open(BF1_PLAYERS_DATA/'Caches'/f'{personaId}.jpg') 
        img = img.resize((1800,1800))
        img = img.crop((250,0,1550,(410*len(recent)+410)))
    except:    
        img = Image.open(BF1_SERVERS_DATA/'Caches'/'DLC1.jpg')
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
    if tag == None:
        draw.text(xy=(290,15), text=f'{name}', fill=(55, 1, 27, 255),font=font_1)
    else:
        draw.text(xy=(290,15), text=f'[{tag}]{name}', fill=(55, 1, 27, 255),font=font_1)
    draw.text(xy=(1000,15), text=f'Rank: {rank}', fill=(55, 1, 27, 255),font=font_1)
    draw.text(xy=(290,95), text=f'游玩时长:{secondsPlayed//3600}小时\n击杀数:{k}\n死亡数:{d}', fill=(66, 112, 244, 255),font=font_2)
    draw.text(xy=(680,95), text=f'获胜率:{win}\n命中率:{acc}\n爆头率:{hs}', fill=(66, 112, 244, 255),font=font_2)
    try:
        draw.text(xy=(1070,95), text=f'K/D:{kd}\nKPM:{kpm}\nDPM:{round((d*60)/secondsPlayed,2)}', fill=(66, 112, 244, 255),font=font_2)
    except:
        draw.text(xy=(1070,95), text=f'K/D:{kd}\nKPM:{kpm}\nDPM:0.00)', fill=(66, 112, 244, 255),font=font_2)
    
    position = (0, 0)
    img.paste(textbox, position, textbox)
    img.paste(img_emb, (0, 0),img_emb)

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
        draw.text(xy=(1070,192), text=f'{recent[i]["kpm"]}', fill=(66, 112, 244, 255),font=font_4)
        
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
    text = f'Powered by Mag1Catz and special thanks to Openblas.QQ Group: 94103090. Update Time:{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    draw.text(xy=(img.width-font_0.getsize(text)[0],410*len(recent)+365), text=text ,fill=(34,139,34, 255),font=font_0)
    draw.line((0, 250, 1300, 250), fill=(55, 1, 27, 120), width=4)
    print(datetime.datetime.now())
    img.save(BF1_SERVERS_DATA/f'Caches/{playerName}_r.jpg')

    return 1