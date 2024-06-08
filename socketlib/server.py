from tkinter import *
from socket import *
from fastapi import FastAPI, Request, Response
import threading
import uvicorn
import json
import asyncio


address='127.0.0.1'
port=10086
buffsize=655355
s = socket(AF_INET, SOCK_STREAM)
s.bind((address,port))
s.listen(100)     #最大连接数
conn_list = []
conn_dt = {}
gameid_dt = {}
gamedata_dt = {}

def tcplink(sock,addr):
    recvdata_tmp = {}
    while True:
        try:
            recvdata=sock.recv(buffsize).decode('utf-8')
            #print(f'data: {recvdata}, addr: {addr}')
            try:
                recvdata_int = int(recvdata)
                gameid_dt[recvdata] = addr
                recvdata_tmp[recvdata] = ''
                continue
            except:
                pass
            
            for key,value in gameid_dt.items():
                if value == addr:
                    gameid = key
                    break

            try:
                recvdata_tmp[gameid] += recvdata
                dt = json.loads(recvdata_tmp[gameid])
                recvdata_tmp[gameid] = ''
                gamedata_dt[str(gameid)] = dt
            except:
                pass
            if not recvdata:
                break

        except:
            sock.close()
            print(addr,'offline')
            _index = conn_list.index(addr)
            conn_dt.pop(addr)
            conn_list.pop(_index)
            break

def recs():
    while True:
        clientsock,clientaddress=s.accept()
        if clientaddress not in conn_list:
            conn_list.append(clientaddress)
            conn_dt[clientaddress] = clientsock
        print('connect from:',clientaddress)
        t=threading.Thread(target=tcplink,args=(clientsock,clientaddress))
        t.start()



app=FastAPI()
@app.get("/")
async def index():
    return "This is Home Page."

@app.get("/gameid")
async def get_data(gameid):
    try:
        addr = gameid_dt[str(gameid)]
        sock =  conn_dt[addr]
        sock.sendall(str(gameid).encode('utf-8'))
        await(asyncio.sleep(4))
        return gamedata_dt[str(gameid)]
    except Exception as e:
        print(e)
        return None
        

def run_api():
    uvicorn.run(app)

if __name__ == '__main__':
    t1 = threading.Thread(target=recs, args=(), name='rec')
    t1.start()
    t2 = threading.Thread(target=run_api, args=(), name='api')
    t2.start()


