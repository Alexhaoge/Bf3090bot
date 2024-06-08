import socket
import httpx
import json
import asyncio

async def get_pl():
    url = 'http://127.0.0.1:10086/Player/GetAllPlayerList'
    async with httpx.AsyncClient() as client:
        res = await client.get(url,timeout = 5)
    return res.json()

async def get_server():
    url = 'http://127.0.0.1:10086/Server/GetServerData'
    async with httpx.AsyncClient() as client:
        res = await client.get(url,timeout = 5)
    return res.json()


async def connect_to_bot():
    inp = input("请确认战地1客户端API在运行状态, 且管服机账号已进入服务器中!\n确认后请输入1: \n")
    if str(inp) == '1':
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('1.tcp.vip.cpolar.top',11595))
        res_server = await get_server()
        gameid = res_server["data"]["gameId"]
        name = res_server["data"]["name"]
        print(f"已识别服务器: {name} \nGameId: {gameid}")
        client_socket.sendall(str(gameid).encode('utf-8'))
        while True:
            recv_data = client_socket.recv(1024)
            data = recv_data.decode('utf-8')
            res_pl = await get_pl()
            res_server = await get_server()
            post_dict = {
                "server": res_server,
                "pl": res_pl
            }
            client_socket.sendall(json.dumps(post_dict).encode('utf-8'))
    else:
        pass


asyncio.run(connect_to_bot())