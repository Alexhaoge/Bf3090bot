import json
import numpy as np
import matplotlib.dates as mdates
import asyncio
import time
import httpx
import uuid

from io import BytesIO
from base64 import b64encode
from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from datetime import datetime, timezone, timedelta
from PIL import Image

from .utils import BF1_SERVERS_DATA
from .bf1draw import base64img

async def upd_servers1(remid, sid, sessionID):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url="https://sparta-gw.battlelog.com/jsonrpc/pc/api",
            json = {
	            "jsonrpc": "2.0",
	            "method": "GameServer.searchServers",
	            "params": {
		        "filterJson": "{\"serverType\":{\"OFFICIAL\": \"off\"}}",
                "game": "tunguska",
                "limit": 200,
                "protocolVersion": "3779779"
	            },
                "id": str(uuid.uuid4())
            },
            headers= {
                'Cookie': f'remid={remid};sid={sid}',
                'X-GatewaySession': sessionID
            },
            timeout=None
        )
    return response.json()

async def upd_draw(remid,sid,sessionID):
    time_start = time.time()
    print(datetime.now())
    nameList = []
    gameIdList = []
    mapList = []
    maxList = []
    numList = []
    tasks = []
    for _ in range(30):
        tasks.append(upd_servers1(remid, sid, sessionID))
    results = await asyncio.gather(*tasks)
    for result in results:
        if isinstance(result, str):
            continue
        result: list = result["result"]
        server_list = result['gameservers']
        for server in server_list:
            if server["gameId"] not in gameIdList and int(server["slots"]["Soldier"]["current"])!=0:
                nameList.append(server["name"])
                gameIdList.append(server["gameId"])
                numList.append(server["slots"]["Soldier"]["current"])
                maxList.append(server["slots"]["Soldier"]["max"])
                mapList.append(server["mapName"])

    print(f"共获取{len(gameIdList)}个私服")
    
    draw_dict = {}

    for i in range(len(gameIdList)):
        serverInfo = {
            "server_name": f"{nameList[i]}",
            "serverMax": f"{maxList[i]}",
            "serverAmount": f"{numList[i]}",
            "map": f"{mapList[i]}"
            }
        draw_dict[f"{gameIdList[i]}"] = serverInfo

    with open(BF1_SERVERS_DATA/'draw.json','r',encoding='UTF-8') as f:
        data = json.load(f)
    data[f"{datetime.now().isoformat()}"] = draw_dict    
    for i in list(data.keys()):    
        if (datetime.now() - datetime.fromisoformat(i)).days >= 1:
            del data[i]
    
    with open(BF1_SERVERS_DATA/'draw.json','w',encoding='UTF-8') as f:
        json.dump(data,f,indent=4,ensure_ascii=False)
    
    return draw_dict

def draw_server_array_matplotlib(res: dict) -> str:
    local_tz = datetime.now(timezone.utc).astimezone().tzinfo
    times = [datetime.fromisoformat(t) for t in res['timeStamps']]
    fig, ax = plt.subplots(1)
    fig.autofmt_xdate()
    plt.plot(times, res['soldierAmount'])
    xfmt = mdates.DateFormatter('%m-%d %H:%M', tz=local_tz)
    ax.xaxis.set_major_formatter(xfmt)
    img = BytesIO()
    plt.savefig(img, format='png')
    return 'base64://' + b64encode(img.getvalue()).decode('ascii')

def draw_server_array2(gameid: str, endtime: datetime = None) -> str:
    # Read raw data
    with open(BF1_SERVERS_DATA/'draw.json', 'r',encoding='UTF-8') as f:
        d = dict(sorted(json.load(f).items())) # sort the list based on key(time)
    # Set time window
    if endtime is None:
        endtime = datetime.now()
    xlim_date = [0, endtime]
    xlim_date[0] = xlim_date[1] - timedelta(days=1)

    # Pre-processing
    server_name = None
    times = [] # list of time w.r.t. player ammount
    players = [] # list of player ammount
    maps = [] # list of maps
    map_times = [] # times correpond to the change of map
    for ts in d.keys():
        ts_dt = datetime.fromisoformat(ts) # current time as datetime object
        ts_dict = d[ts] # current time dict of all servers
        if ts_dt < xlim_date[0] or ts_dt > xlim_date[1]:
            continue # if not in window ignore
        times.append(ts_dt) # always append the time
        if gameid in ts_dict.keys():
            players.append(int(ts_dict[gameid]['serverAmount']))
            # record map change
            if len(maps):
                if ts_dict[gameid]['map'] != maps[-1]:
                    # if the current map is the same as last element in maps list, add new map
                    maps.append(ts_dict[gameid]['map'])
                    map_times.append(ts_dt)
            else:
                # if map list in non-empty, add first map
                maps.append(ts_dict[gameid]['map'])
                map_times.append(ts_dt)
            if not server_name:
                server_name = ts_dict[gameid]['server_name']
        else:
            players.append(0)
    maps.append('') # Add end boundary for map list
    map_times.append(xlim_date[1])
    first_nonzero_player_ind = np.where(np.array(players) != 0)[0]
    if len(first_nonzero_player_ind):
        xlim_date[0] = times[first_nonzero_player_ind[0]]

    with open(BF1_SERVERS_DATA/'zh-cn.json', 'r',encoding='UTF-8') as f:
        map_dict = json.load(f)
    
    # Plotting initilization
    fig, ax = plt.subplots(1)
    fig.set_size_inches(12, 8)
    ax.set_xlim(xlim_date[0], xlim_date[1])
    ax.set_ylim(0, 65)
    fig.autofmt_xdate()
    # Convert date to num for axis config
    xlim_num = mdates.date2num(xlim_date)
    xrange = xlim_num[1] - xlim_num[0]
    map_times_num = mdates.date2num(map_times)

    # Render piecewise background from map images
    for i in range(len(maps)-1):
        full_map_img = Image.open(BF1_SERVERS_DATA/'Caches'/'Maps1'/f'{map_dict[maps[i]]}.jpg')
        width_ratio = (map_times_num[i+1] - map_times_num[i]) / xrange
        crop_map_img = full_map_img.crop((0, 0, full_map_img.size[0] * width_ratio, full_map_img.size[1]))
        map_img = np.array(crop_map_img)
        axes_new = inset_axes(ax, width="100%", height="100%",
                            bbox_to_anchor=((map_times_num[i] - xlim_num[0]) / xrange, 0, width_ratio, 1),
                            bbox_transform=ax.transAxes,
                            borderpad=0,
                            loc=3)
        axes_new.imshow(map_img, alpha=0.8, aspect='auto', zorder=0)
        axes_new.set_axis_off()

    xfmt = mdates.DateFormatter('%H:%M')
    ax.xaxis.set_major_formatter(xfmt)

    # Plot playeramount line with a new axes
    # TODO: it's not a good solution but we need the line to be above all backgrounds
    axes_line = inset_axes(ax, width="100%", height="100%",
                            bbox_to_anchor=(0, 0, 1, 1),
                            bbox_transform=ax.transAxes,
                            borderpad=0,
                            loc=3)
    axes_line.plot(times, players, c='limegreen', zorder=2, linewidth=2)
    axes_line.set_xlim(xlim_date[0], xlim_date[1])
    axes_line.set_ylim(0, 65)
    axes_line.axhline(y=20, c='grey', linestyle='--')
    axes_line.axhline(y=54, c='grey', linestyle='--')
    axes_line.set_axis_off()

    ax.set_title(f'{server_name}\n{datetime.strftime(xlim_date[0], "%Y/%m/%d")}-{datetime.strftime(xlim_date[1], "%Y/%m/%d")}')
    ax.set_yticks([0, 10, 20, 32, 40, 54, 64])
    fig.tight_layout()

    # Save figure and return in base64
    img = BytesIO()
    plt.savefig(img, format='png')
    return 'base64://' + b64encode(img.getvalue()).decode('ascii')