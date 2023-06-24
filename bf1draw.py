from PIL import Image, ImageDraw, ImageFilter, ImageFont
import requests
import json
import uuid
import re

from .bf1rsp import upd_detailedServer, upd_servers
from .utils import BF1_SERVERS_DATA

async def draw_f(server_id:int,session:int,remid, sid, sessionID):
    # 打开图片文件
    img = Image.open(BF1_SERVERS_DATA/'Caches/DLC1.jpg')
    img = img.resize((753,978))
    img = img.crop((0,0,753,190*server_id))
    # 将原始图片模糊化
    img = img.filter(ImageFilter.GaussianBlur(radius=15))
    for id in range(server_id):
        with open(BF1_SERVERS_DATA/f'{session}_jsonGT'/f'{session}_{id+1}.json','r', encoding='utf-8') as f:
            serverGT = json.load(f)
            gameId = serverGT['gameId']
            
        res =  upd_detailedServer(remid, sid, sessionID, gameId)
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
        status2 = f'{serveramount}/{servermaxamount}[{serverque}({serverspect})]'
        status3 = f'★{serverstar}'

        # 创建一个矩形图形
        textbox0 = Image.new("RGBA", (693,40), (0, 0, 0, 200))
        textbox = Image.new("RGBA", (693,150), (0, 0, 0, 200))

        # 在矩形图形上添加文字
        draw0 = ImageDraw.Draw(textbox0)
        draw = ImageDraw.Draw(textbox)
        font_1 = ImageFont.truetype(font='comic.ttf', size=22, encoding='UTF-8')
        font_2 = ImageFont.truetype(font='msyhbd.ttc', size=22, encoding='UTF-8')
        font_3 = ImageFont.truetype(font='msyhbd.ttc', size=14, encoding='UTF-8')
        font_4 = ImageFont.truetype(font='comic.ttf', size=36, encoding='UTF-8')
        draw0.text(xy=(40,4), text=servername, fill=(255, 255, 255, 255),font=font_1)
        draw.text(xy=(280,5), text=status1, fill=(255, 255, 0, 200),font=font_2)
        draw.text(xy=(580,5), text=status3, fill=(0, 255, 255, 200),font=font_2)
        draw.text(xy=(250,20), text='------------------------------------------------------', fill=(0, 255, 0, 100),font=font_1)
        draw.text(xy=(480,65), text=status2, fill=(0, 255, 0, 255),font=font_4)

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
            draw.text(xy=(260,45+i*20), text=result.split('\n')[i], fill=(255, 255, 255, 255),font=font_3)
            if i == 4:
                break

        # 将矩形图形添加到原始图片的指定位置
        position0 = (30, 190*id)
        position = (30, 40+190*id)
        img.paste(textbox0, position0, textbox0)
        img.paste(textbox, position, textbox)

        background = Image.open(serverimg).resize((240,150))
        img.paste(background, position)

    img.save(BF1_SERVERS_DATA/f'Caches/{session}.jpg')
    return 1

async def draw_server(remid, sid, sessionID, serverName):
    img = Image.open(BF1_SERVERS_DATA/f'Caches/DLC1.jpg')
    img = img.resize((753,950))
    img = img.filter(ImageFilter.GaussianBlur(radius=15))
    res = upd_servers(remid, sid, sessionID, serverName)['result']['gameservers']
    if (len(res)) <5:
        img = img.crop((0,0,753,190*len(res)))
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
        res_0 =  upd_detailedServer(remid, sid, sessionID, gameId)
        serverstar = res_0['result']['serverInfo']['serverBookmarkCount']

        status1 = servermode + '-' +servermap
        status2 = f'{serveramount}/{servermaxamount}[{serverque}({serverspect})]'
        status3 = f'★{serverstar}'

        # 创建一个矩形图形
        textbox0 = Image.new("RGBA", (693,40), (0, 0, 0, 200))
        textbox = Image.new("RGBA", (693,150), (0, 0, 0, 200))

        # 在矩形图形上添加文字
        draw0 = ImageDraw.Draw(textbox0)
        draw = ImageDraw.Draw(textbox)
        font_1 = ImageFont.truetype(font='comic.ttf', size=22, encoding='UTF-8')
        font_2 = ImageFont.truetype(font='msyhbd.ttc', size=22, encoding='UTF-8')
        font_3 = ImageFont.truetype(font='msyh.ttc', size=14, encoding='UTF-8')
        font_4 = ImageFont.truetype(font='comic.ttf', size=36, encoding='UTF-8')
        draw0.text(xy=(40,4), text=servername, fill=(255, 255, 255, 255),font=font_1)
        draw.text(xy=(280,5), text=status1, fill=(255, 255, 0, 200),font=font_2)
        draw.text(xy=(580,5), text=status3, fill=(0, 255, 255, 200),font=font_2)
        draw.text(xy=(250,20), text='------------------------------------------------------', fill=(0, 255, 0, 100),font=font_1)
        draw.text(xy=(480,65), text=status2, fill=(0, 255, 0, 255),font=font_4)

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
            draw.text(xy=(260,45+i*20), text=result.split('\n')[i], fill=(255, 255, 255, 255),font=font_3)
            if i == 4:
                break

        # 将矩形图形添加到原始图片的指定位置
        position0 = (30, 190*ij)
        position = (30, 40+190*ij)
        img.paste(textbox0, position0, textbox0)
        img.paste(textbox, position, textbox)

        background = Image.open(serverimg).resize((240,150))
        img.paste(background, position)

        if ij == 4:
            break

    img.save(BF1_SERVERS_DATA/f'Caches/{serverName}.jpg')
    return 1

#draw_f(4,248966716,remid, sid, sessionID)
