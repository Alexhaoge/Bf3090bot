import json
import httpx
from pathlib import Path
import os
from .config import Config
from nonebot import get_driver, logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Record

KitDict = {
    "ID_M_ASSAULT": "KitIconAssaultLarge.png",
    "ID_M_MEDIC": "KitIconMedicLarge.png",
    "ID_M_SUPPORT": "KitIconSupportLarge.png",
    "ID_M_SCOUT": "KitIconScoutLarge.png",
    "ID_M_RUNNER": "KitIconInfiltratorLarge.png",
    "ID_M_INFLITRATOR": "KitIconInfiltratorLarge.png",
    "ID_M_FLAMETHROWER": "KitIconFlamethrowerLarge.png",
    "ID_M_TANKER": "KitIconTankerLarge.png",
    "ID_M_PILOT": "KitIconPilotLarge.png",
    "ID_M_RAIDER": "KitIconTrenchRaiderLarge.png",
    "ID_M_TRENCHRAIDER": "KitIconTrenchRaiderLarge.png",
    "ID_M_SENTRY": "KitIconSentryLarge.png",
    "ID_M_RIDER": "KitIconRiderLarge.png",
    "ID_M_ANTITANK": "KitIconAntiTankLarge.png"
}

MapTeamDict = {
        "MP_MountainFort": {"Chinese": "格拉巴山", "Team1": "ITA", "Team2": "AHU"},
        "MP_Forest": {"Chinese": "阿尔贡森林", "Team1": "USA", "Team2": "GER"},
        "MP_ItalianCoast": {"Chinese": "帝国边境", "Team1": "ITA", "Team2": "AHU"},
        "MP_Chateau": {"Chinese": "流血宴厅", "Team1": "USA", "Team2": "GER"},
        "MP_Scar": {"Chinese": "圣康坦的伤痕", "Team1": "GER", "Team2": "UK"},
        "MP_Desert": {"Chinese": "西奈沙漠", "Team1": "UK", "Team2": "OTM"},
        "MP_Amiens": {"Chinese": "亚眠", "Team1": "GER", "Team2": "UK"},
        "MP_Suez": {"Chinese": "苏伊士", "Team1": "UK", "Team2": "OTM"},
        "MP_FaoFortress": {"Chinese": "法欧堡", "Team1": "UK", "Team2": "OTM"},
        "MP_Giant": {"Chinese": "庞然暗影", "Team1": "GER", "Team2": "UK"},
        "MP_Fields": {"Chinese": "苏瓦松", "Team1": "FRA", "Team2": "GER"},
        "MP_Graveyard": {"Chinese": "决裂", "Team1": "FRA", "Team2": "GER"},
        "MP_Underworld": {"Chinese": "法乌克斯要塞", "Team1": "GER", "Team2": "FRA"},
        "MP_Verdun": {"Chinese": "凡尔登高地", "Team1": "GER", "Team2": "FRA"},
        "MP_Trench": {"Chinese": "尼维尔之夜", "Team1": "GER", "Team2": "FRA"},
        "MP_ShovelTown": {"Chinese": "攻占托尔", "Team1": "GER", "Team2": "FRA"},
        "MP_Bridge": {"Chinese": "勃鲁希洛夫关口", "Team1": "RUS", "Team2": "AHU"},
        "MP_Islands": {"Chinese": "阿尔比恩", "Team1": "GER", "Team2": "RUS"},
        "MP_Ravines": {"Chinese": "武普库夫山口", "Team1": "AHU", "Team2": "RUS"},
        "MP_Valley": {"Chinese": "加利西亚", "Team1": "RUS", "Team2": "AHU"},
        "MP_Tsaritsyn": {"Chinese": "察里津", "Team1": "BOL", "Team2": "RUS"},
        "MP_Volga": {"Chinese": "窝瓦河", "Team1": "BOL", "Team2": "RUS"},
        "MP_Beachhead": {"Chinese": "海丽丝岬", "Team1": "UK", "Team2": "OTM"},
        "MP_Harbor": {"Chinese": "泽布吕赫", "Team1": "RM", "Team2": "GER"},
        "MP_Naval": {"Chinese": "黑尔戈兰湾", "Team1": "RM", "Team2": "GER"},
        "MP_Ridge": {"Chinese": "阿奇巴巴", "Team1": "UK", "Team2": "OTM"},
        "MP_Offensive": {"Chinese": "索姆河", "Team1": "UK", "Team2": "GER"},
        "MP_Hell": {"Chinese": "帕斯尚尔", "Team1": "UK", "Team2": "GER"},
        "MP_River": {"Chinese": "卡波雷托", "Team1": "AHU", "Team2": "ITA"},
        "MP_Alps": {"Chinese": "剃刀边缘", "Team1": "GER", "Team2": "UK"},
        "MP_Blitz": {"Chinese": "伦敦的呼唤：夜袭", "Team1": "GER", "Team2": "UK"},
        "MP_London": {"Chinese": "伦敦的呼唤：灾祸", "Team1": "GER", "Team2": "UK"}
    }

UpdateDict = {
        "4": "MP_MountainFort",
        "11": "MP_Forest",
        "2": "MP_ItalianCoast",
        "7": "MP_Chateau",
        "8": "MP_Scar",
        "10": "MP_Desert",
        "1": "MP_Amiens",
        "9": "MP_Suez",
        "6": "MP_FaoFortress",
        "12": "MP_Giant",
        "16": "MP_Fields",
        "5": "MP_Graveyard",
        "15": "MP_Underworld",
        "13": "MP_Verdun",
        "14": "MP_Trench",
        "3": "MP_ShovelTown",
        "18": "MP_Bridge",
        "22": "MP_Islands",
        "20": "MP_Ravines",
        "17": "MP_Valley",
        "19": "MP_Tsaritsyn",
        "21": "MP_Volga",
        "23": "MP_Beachhead",
        "24": "MP_Harbor",
        "29": "MP_Naval",
        "25": "MP_Ridge",
        "28": "MP_Offensive",
        "27": "MP_Hell",
        "26": "MP_River",
        "32": "MP_Alps",
        "30": "MP_Blitz",
        "31": "MP_London",
        "Z": "CQ0",
        "F": "TOW0",
        "S": "TDM0",
        "X": "POS0",
        "Q": "DOM0",
        "R": "R0",
        "K": "ZC0",
        "A": "AA0"
    }

UpdateDict_1 = {value: key for key, value in UpdateDict.items()}

RankList = [0,1000,5000,15000,25000,40000,55000,75000,95000,120000,145000,175000,205000,235000,265000,295000,325000,355000,395000,435000,475000,515000,555000,595000,635000,675000,715000,755000,795000,845000,895000,945000,995000,1045000,1095000,1145000,1195000,1245000,1295000,1345000,1405000,1465000,1525000,1585000,1645000,1705000,1765000,1825000,1885000,1945000,2015000,2085000,2155000,2225000,2295000,2365000,2435000,2505000,2575000,2645000,2745000,2845000,2945000,3045000,3145000,3245000,3345000,3445000,3545000,3645000,3750000,3870000,4000000,4140000,4290000,4450000,4630000,4830000,5040000,5260000,5510000,5780000,6070000,6390000,6730000,7110000,7510000,7960000,8430000,8960000,9520000,10130000,10800000,11530000,12310000,13170000,14090000,15100000,16190000,17380000,20000000,20500000,21000000,21500000,22000000,22500000,23000000,23500000,24000000,24500000,25000000,25500000,26000000,26500000,27000000,27500000,28000000,28500000,29000000,29500000,30000000,30500000,31000000,31500000,32000000,32500000,33000000,33500000,34000000,34500000,35000000,35500000,36000000,36500000,37000000,37500000,38000000,38500000,39000000,39500000,40000000,41000000,42000000,43000000,44000000,45000000,46000000,47000000,48000000,49000000,50000000]

CODE_FOLDER = Path(__file__).parent.resolve()

global_config = get_driver().config
config = Config(**global_config.dict())
PREFIX = config.bfchat_prefix

NONEBOT_PORT = config.port
DATABASE_URL = config.database_url
REDIS_URL = config.redis_url
GAMETOOL_URL = config.gametool_url

CURRENT_FOLDER = Path(config.bfchat_dir).resolve()
CURRENT_FOLDER.mkdir(exist_ok=True)
ASSETS_FOLDER = CODE_FOLDER/'assets'
#BFV_PLAYERS_DATA = CURRENT_FOLDER/'bfv_players'
BF1_PLAYERS_DATA = CURRENT_FOLDER/'bf1_players'
BF1_SERVERS_DATA = CURRENT_FOLDER/'bf1_servers'
#BF2042_PLAYERS_DATA = CURRENT_FOLDER/'bf2042_players'
LOGGING_FOLDER = CURRENT_FOLDER/'log'

#BFV_PLAYERS_DATA.mkdir(exist_ok=True)
BF1_PLAYERS_DATA.mkdir(exist_ok=True)
#BF2042_PLAYERS_DATA.mkdir(exist_ok=True)
LOGGING_FOLDER.mkdir(exist_ok=True)

SUPERUSERS = [int(su) for su in global_config.superusers]
SUDOGROUPS = [int(g) for g in global_config.sudogroups]


with open(CURRENT_FOLDER/"wp_guid.json","r",encoding="utf-8")as f:
    wp_guid = json.load(f)
with open(CURRENT_FOLDER/"skininfo.json","r",encoding="utf-8")as f:
    skininfo = json.load(f)

httpx_gt_client = httpx.AsyncClient(base_url=GAMETOOL_URL, limits=httpx.Limits(max_connections=50))
async def request_GT_API(game, prop='stats', params={}):
    """
    Depreacated
    """
    url = GAMETOOL_URL+f'{game}/{prop}'
    res = await httpx_gt_client.get(url,params=params,timeout=20)
    return res.json()


def get_wp_info(message:str,user_id:int):
    wpmode = 0
    match message:
                case '精英兵':
                    wpmode = 1
                    mode = 2
                    playerName = user_id
                case '配备':
                    wpmode = 2
                    mode = 2
                    playerName = user_id
                case '半自动':
                    wpmode = 3
                    mode = 2
                    playerName = user_id
                case '佩枪':
                    wpmode = 5
                    mode = 2
                    playerName = user_id
                case '手枪':
                    wpmode = 5
                    mode = 2
                    playerName = user_id
                case '机枪':
                    wpmode = 6
                    mode = 2
                    playerName = user_id
                case '轻机枪':
                    wpmode = 6
                    mode = 2
                    playerName = user_id
                case '近战':
                    wpmode = 7
                    mode = 2
                    playerName = user_id
                case '刀':
                    wpmode = 7
                    mode = 2
                    playerName = user_id
                case '霰弹枪':
                    wpmode = 4
                    mode = 2
                    playerName = user_id
                case '霰弹':
                    wpmode = 4
                    mode = 2
                    playerName = user_id
                case '步枪':
                    wpmode = 8
                    mode = 2
                    playerName = user_id
                case '狙击枪':
                    wpmode = 8
                    mode = 2
                    playerName = user_id
                case '手榴弹':
                    wpmode = 10
                    mode = 2
                    playerName = user_id
                case '驾驶员':
                    wpmode = 9
                    mode = 2
                    playerName = user_id
                case '制式步枪':
                    wpmode = 11
                    mode = 2
                    playerName = user_id
                case '冲锋枪':
                    wpmode = 12
                    mode = 2
                    playerName = user_id
                case '突击兵':
                    wpmode = 13
                    mode = 2
                    playerName = user_id
                case '支援兵':
                    wpmode = 14
                    mode = 2
                    playerName = user_id
                case '侦察兵':
                    wpmode = 15
                    mode = 2
                    playerName = user_id
                case '医疗兵':
                    wpmode = 16
                    mode = 2
                    playerName = user_id           
                case '载具':
                    wpmode = 17
                    mode = 2
                    playerName = user_id                                    
                case _:
                    wpmode = 0
                    mode = 1
                    playerName = message
    return [playerName,wpmode,mode]

def special_stat_to_dict1(special_stat):
    List_AS = special_stat['4']
    dict_AS = {
        "name": "信号枪（信号）",
        "category": "戰場裝備",
        "imageUrl": "[BB_PREFIX]/gamedata/Tunguska/26/102/GadgetWebleyScottFlaregunFlash-40b27cca.png",
        "stats": {
            "values": {
                "hits": List_AS[1],
                "shots": List_AS[0],
                "kills": List_AS[3],
                "headshots": List_AS[4],
                "accuracy": 0.0,
                "seconds": List_AS[2]
                }
            }
        }
    return dict_AS

def special_stat_to_dict(special_stat):
    List_AS = special_stat['13']
    dict_AS = {
        "name": "Annihilator（冲锋）",
        "category": "衝鋒槍",
        "imageUrl": "[BB_PREFIX]/gamedata/Tunguska/26/102/ThompsonAnnihilatorTr-1a660e74.png",
        "stats": {
            "values": {
                "hits": List_AS[1],
                "shots": List_AS[0],
                "kills": List_AS[3],
                "headshots": List_AS[4],
                "accuracy": 0.0,
                "seconds": List_AS[2]
                }
            }
        }
    
    List_PK = special_stat['4']
    dict_PK = {
        "name": "Peacekeeper",
        "category": "佩槍",
        "imageUrl": "[BB_PREFIX]/gamedata/Tunguska/26/102/Colt_SAA-ef15294c.png",
        "stats": {
            "values": {
                "hits": List_PK[1],
                "shots": List_PK[0],
                "kills": List_PK[3],
                "headshots": List_PK[4],
                "accuracy": 0.0,
                "seconds": List_PK[2]
                }
            }
        }
    
    List_BD1 = special_stat['9']
    dict_BD1 = {
        "name": "波顿 LMR（战壕）",
        "category": "輕機槍",
        "imageUrl": "[BB_PREFIX]/gamedata/Tunguska/26/102/WinchesterBurton-ce3988cc.png",
        "stats": {
            "values": {
                "hits": List_BD1[1],
                "shots": List_BD1[0],
                "kills": List_BD1[3],
                "headshots": List_BD1[4],
                "accuracy": 0.0,
                "seconds": List_BD1[2]
                }
            }
        }
    List_BD2 = special_stat['8']
    dict_BD2 = {
        "name": "波顿 LMR（瞄准镜）",
        "category": "輕機槍",
        "imageUrl": "[BB_PREFIX]/gamedata/Tunguska/26/102/WinchesterBurton-ce3988cc.png",
        "stats": {
            "values": {
                "hits": List_BD2[1],
                "shots": List_BD2[0],
                "kills": List_BD2[3],
                "headshots": List_BD2[4],
                "accuracy": 0.0,
                "seconds": List_BD2[2]
                }
            }
        }
    return dict_AS,dict_PK,dict_BD1,dict_BD2

def getRank(spm,secondsPlayed):
    Score = spm*secondsPlayed/60

    for i in range(len(RankList)-1):
        if RankList[i] <= Score < RankList[i+1]:
            break
    if Score > 50000000:
        return 150
    else:
        return i
    
def getWeaponSkin(name,res_pre:dict):
    try:
        loadout = res_pre["result"]["weapons"]

        guid = wp_guid[name]["guid"]
        skinlist = wp_guid[name]["info"]

        skin_guid = loadout[guid]["1"]
        skin_name = skininfo["result"][skin_guid]["name"]

        for i in skinlist:
            if i["name"] == skin_name:
                skin_rare = i["rarenessLevel"]
                skin_url = i["images"]["Png300xANY"].replace("[BB_PREFIX]","https://eaassets-a.akamaihd.net/battlelog/battlebinary")
                break
            elif i["name"] == skin_name + " (極稀有)":
                skin_name = skin_name + " (極稀有)"
                skin_rare = i["rarenessLevel"]
                skin_url = i["images"]["Png300xANY"].replace("[BB_PREFIX]","https://eaassets-a.akamaihd.net/battlelog/battlebinary")
                break
        return skin_name,skin_url,skin_rare
    except Exception as e:
        return e
    
def getVehicleSkin(name,res_pre:dict):
    try:
        loadout = res_pre["result"]["kits"]

        guid = wp_guid[name]["guid"]
        skinlist = wp_guid[name]["info"]

        skin_guid = loadout[guid][0]["1"]
        skin_name = skininfo["result"][skin_guid]["name"]

        for i in skinlist:
            if i["name"] == skin_name:
                skin_rare = i["rarenessLevel"]
                skin_url = i["images"]["Png300xANY"].replace("[BB_PREFIX]","https://eaassets-a.akamaihd.net/battlelog/battlebinary")
                break
            elif i["name"] == skin_name + " (極稀有)":
                skin_name = skin_name + " (極稀有)"
                skin_rare = i["rarenessLevel"]
                skin_url = i["images"]["Png300xANY"].replace("[BB_PREFIX]","https://eaassets-a.akamaihd.net/battlelog/battlebinary")
                break

        return skin_name,skin_url,skin_rare
    except Exception as e:
        return e
    
def is_contain_chinese(check_str):
    """
    判断字符串中是否包含中文
    :param check_str: {str} 需要检测的字符串
    :return: {bool} 包含返回True， 不包含返回False
    """
    for ch in check_str:
        if u'\u4e00' <= ch <= u'\u9fff':
            return True
    return False

def getSettings(settings):
    set = json.loads(settings)
    setstr = ""
    if set["kits"]["1"] == "off":
        setstr += "1-off "
    if set["kits"]["2"] == "off":
        setstr += "2-off "
    if set["kits"]["3"] == "off":
        setstr += "3-off "
    if set["kits"]["4"] == "off":
        setstr += "4-off "
    if set["kits"]["HERO"] == "off":
        setstr += "5-off " 
    if set["vehicles"]["L"] == "off":
        setstr += "6-off "
    if set["vehicles"]["A"] == "off":
        setstr += "7-off "
    if set["weaponClasses"]["E"] == "off":
        setstr += "8-off "
    if set["weaponClasses"]["SIR"] == "on":
        setstr += "9-on "
    if set["weaponClasses"]["SAR"] == "off":
        setstr += "10-off "  
    if set["weaponClasses"]["KG"] == "off":
        setstr += "11-off " 
    if set["weaponClasses"]["M"] == "off":
        setstr += "12-off " 
    if set["weaponClasses"]["LMG"] == "off":
        setstr += "13-off " 
    if set["weaponClasses"]["SMG"] == "off":
        setstr += "14-off " 
    if set["weaponClasses"]["H"] == "off":
        setstr += "15-off "
    if set["weaponClasses"]["S"] == "off":
        setstr += "16-off "
    if set["weaponClasses"]["SR"] == "off":
        setstr += "17-off "
    if set["misc"]["RWM"] == "on":
        setstr += "18-on "
    if set["misc"]["UM"] == "on":
        setstr += "19-on "
    if set["misc"]["LL"] == "on":
        setstr += "20-on "
    if set["misc"]["AAS"] == "off":
        setstr += "21-off "
    if set["misc"]["LNL"] == "on":
        setstr += "22-on "
    if set["misc"]["3S"] == "off":
        setstr += "23-off "
    if set["misc"]["KC"] == "off":
        setstr += "24-off "
    if set["misc"]["MV"] == "off":
        setstr += "25-off "
    if set["misc"]["BH"] == "off":
        setstr += "26-off "
    if set["misc"]["F"] == "on":
        setstr += "27-on "
    if set["misc"]["MM"] == "off":
        setstr += "28-off "
    if set["misc"]["DTB"] == "on":
        setstr += "29-on "
    if set["misc"]["FF"] == "on":
        setstr += "30-on "
    if set["misc"]["RH"] == "off":
        setstr += "31-off "
    if set["misc"]["3VC"] == "off":
        setstr += "32-off "
    if set["misc"]["SLSO"] == "on":
        setstr += "33-on "  
    if set["misc"]["DSD"] == "on":
        setstr += "34-on "
    if set["misc"]["AAR"] == "off":
        setstr += "35-off "
    if set["misc"]["NT"] == "off":
        setstr += "36-off "
    if set["misc"]["BPL"] == "on":
        setstr += "37-on "
    if set["misc"]["MS"] == "off":
        setstr += "38-off "
    if set["scales"]["RT2"] == "on":
        setstr += "39-50% "
    if set["scales"]["RT3"] == "on":
        setstr += "39-100% "
    if set["scales"]["RT4"] == "on":
        setstr += "39-200% "
    if set["scales"]["RT5"] == "on":
        setstr += "39-500% "
    if set["scales"]["BD1"] == "on":
        setstr += "40-50% "    
    if set["scales"]["BD3"] == "on":
        setstr += "40-200% " 
    if set["scales"]["BD4"] == "on":
        setstr += "40-125% " 
    if set["scales"]["VR1"] == "on":
        setstr += "41-50% " 
    if set["scales"]["VR3"] == "on":
        setstr += "41-200% " 
    if set["scales"]["TC1"] == "on":
        setstr += "42-50% " 
    if set["scales"]["TC3"] == "on":
        setstr += "42-200% "
    if set["scales"]["SR1"] == "on":
        setstr += "43-50% " 
    if set["scales"]["SR3"] == "on":
        setstr += "43-200% "

    if setstr == "":
        return "默认值"
    else:
        return setstr.rstrip()

def ToSettings(setstrlist:list):
    
    settings = "{\"version\":10,\"kits\":{\"8\":\"off\",\"4\":\"on\",\"9\":\"off\",\"5\":\"off\",\"6\":\"off\",\"HERO\":\"on\",\"1\":\"on\",\"2\":\"on\",\"7\":\"off\",\"3\":\"on\"},\"vehicles\":{\"L\":\"on\",\"A\":\"on\"},\"weaponClasses\":{\"E\":\"on\",\"SIR\":\"off\",\"SAR\":\"on\",\"KG\":\"on\",\"M\":\"on\",\"LMG\":\"on\",\"SMG\":\"on\",\"H\":\"on\",\"S\":\"on\",\"SR\":\"on\"},\"serverType\":{\"SERVER_TYPE_RANKED\":\"on\"},\"misc\":{\"RWM\":\"off\",\"UM\":\"off\",\"LL\":\"off\",\"AAS\":\"on\",\"LNL\":\"off\",\"3S\":\"on\",\"KC\":\"on\",\"MV\":\"on\",\"BH\":\"on\",\"F\":\"off\",\"MM\":\"on\",\"DTB\":\"off\",\"FF\":\"off\",\"RH\":\"on\",\"3VC\":\"on\",\"SLSO\":\"off\",\"DSD\":\"off\",\"AAR\":\"on\",\"NT\":\"on\",\"BPL\":\"off\",\"MS\":\"on\"},\"scales\":{\"RT3\":\"off\",\"BD3\":\"off\",\"VR3\":\"off\",\"BD4\":\"off\",\"BD2\":\"on\",\"TC1\":\"off\",\"SR1\":\"off\",\"SR2\":\"on\",\"VR2\":\"on\",\"RT1\":\"on\",\"BD1\":\"off\",\"RT5\":\"off\",\"RT2\":\"off\",\"TC2\":\"on\",\"TC3\":\"off\",\"SR3\":\"off\",\"RT4\":\"off\",\"VR1\":\"off\"}}"
            
    if "默认值" in setstrlist:
        return settings
    
    set = json.loads(settings)

    if "1-off" in setstrlist:
        set["kits"]["1"] = "off"
    if "2-off" in setstrlist:
        set["kits"]["2"] = "off"
    if "3-off" in setstrlist:
        set["kits"]["3"] = "off"
    if "4-off" in setstrlist:
        set["kits"]["4"] = "off"
    if "5-off" in setstrlist:
        set["kits"]["HERO"] = "off"
    if "6-off" in setstrlist:
        print(set["vehicles"]["L"])
        set["vehicles"]["L"] = "off"
    if "7-off" in setstrlist:
        print(set["vehicles"]["A"])
        set["vehicles"]["A"] = "off"
    if "8-off" in setstrlist:
        set["weaponClasses"]["E"] ="off"
    if "9-on" in setstrlist:
        set["weaponClasses"]["SIR"] = "on"
    if "10-off" in setstrlist:
        set["weaponClasses"]["SAR"] = "off"
    if "11-off" in setstrlist:
        set["weaponClasses"]["KG"] = "off"  
    if "12-off" in setstrlist:
        set["weaponClasses"]["M"] = "off"  
    if "13-off" in setstrlist:
        set["weaponClasses"]["LMG"] = "off" 
    if "14-off" in setstrlist:
        set["weaponClasses"]["SMG"] = "off" 
    if "15-off" in setstrlist:
        set["weaponClasses"]["H"] = "off"  
    if "16-off" in setstrlist:
        set["weaponClasses"]["S"] = "off"  
    if "17-off" in setstrlist:
        set["weaponClasses"]["SR"] = "off"  
    if "18-on" in setstrlist:
        set["misc"]["RWM"] = "on"
    if "19-on" in setstrlist:
        set["misc"]["UM"] = "on"
    if "20-on" in setstrlist:
        set["misc"]["LL"] = "on"
    if "21-off" in setstrlist:
        set["misc"]["AAS"] = "off"
    if "22-on" in setstrlist:
        set["misc"]["LNL"] = "on"
    if "23-off" in setstrlist:
        set["misc"]["3S"] = "off"
    if "24-off" in setstrlist:
        set["misc"]["KC"] = "off"
    if "25-off" in setstrlist:
        set["misc"]["MV"] = "off"
    if "26-off" in setstrlist:
        set["misc"]["BH"] = "off"
    if "27-on" in setstrlist:
        set["misc"]["F"] = "on"
    if "28-off" in setstrlist:
        set["misc"]["MM"] = "off"
    if "29-on" in setstrlist:
        set["misc"]["DTB"] = "on"
    if "30-on" in setstrlist:
        set["misc"]["FF"] = "on"
    if "31-off" in setstrlist:
        set["misc"]["RH"] = "off"
    if "32-off" in setstrlist:
        set["misc"]["3VC"] = "off"
    if "33-on" in setstrlist:
        set["misc"]["SLSO"] = "on"
    if "34-on" in setstrlist:
        set["misc"]["DSD"] = "on"
    if "35-off" in setstrlist:
        set["misc"]["AAR"] = "off"
    if "36-off" in setstrlist:
        set["misc"]["NT"] = "off"
    if "37-on" in setstrlist:
        set["misc"]["BPL"] = "on"
    if "38-off" in setstrlist:
        set["misc"]["MS"] = "off"

    if "39-50%" in setstrlist:
        set["scales"]["RT2"] = "on"
        set["scales"]["RT1"] = "off"
    elif "39-100%" in setstrlist:
        set["scales"]["RT3"] = "on"
        set["scales"]["RT1"] = "off"
    elif "39-200%" in setstrlist:
        set["scales"]["RT4"] = "on"
        set["scales"]["RT1"] = "off"
    elif "39-500%" in setstrlist:
        set["scales"]["RT5"] = "on"
        set["scales"]["RT1"] = "off"

    if "40-50%" in setstrlist:
        set["scales"]["BD1"] = "on"
        set["scales"]["BD2"] = "off"
    elif "40-200%" in setstrlist:
        set["scales"]["BD3"] = "on"
        set["scales"]["BD2"] = "off"
    elif "40-125%" in setstrlist:
        set["scales"]["BD4"] = "on"
        set["scales"]["BD2"] = "off"

    if "41-50%" in setstrlist:
        set["scales"]["VR1"] = "on"
        set["scales"]["VR2"] = "off"
    elif "41-200%" in setstrlist:
        set["scales"]["VR3"] = "on"
        set["scales"]["VR2"] = "off"

    if "42-50%" in setstrlist:
        set["scales"]["TC1"] = "on"
        set["scales"]["TC2"] = "off"
    elif "42-200%" in setstrlist:
        set["scales"]["TC3"] = "on"
        set["scales"]["TC2"] = "off"

    if "43-50%" in setstrlist:
        set["scales"]["SR1"] = "on"
        set["scales"]["SR2"] = "off"
    elif "43-200%" in setstrlist:
        set["scales"]["SR3"] = "on"
        set["scales"]["SR2"] = "off"

    settings = json.dumps(set)
    
    return settings

def main_log_filter(record: "Record"):
    """
        Override default logger filter, level can be change by `config.log_level` in `pyproject.toml`
        For nonebot_plugin_picstatus, only log with level greater than warning (30) will be recorded.
    """
    log_level = record["extra"].get("nonebot_log_level", "INFO")
    levelno = logger.level(log_level).no if isinstance(log_level, str) else log_level
    if record['name'] == 'nonebot_plugin_picstatus':
        return record["level"].no > 30
    return record["level"].no >= levelno
