# a lot of TODO works here for migration from file data to db
import sqlite3
import asyncio
import os
import json
import re
import datetime
from pathlib import Path

# Change these!
path_to_bfchat_data = "../bfchat_data" 
bf1admin_pid = [
    994371625, 1005935009564, 1006896769855, 1006306480221, 1006197884886, 
    1007408722331, 1007565122039, 1005349638963, 1005440313535, 1005430659208
]

CURRENT_FOLDER = Path(path_to_bfchat_data).resolve()
BF1_PLAYERS_DATA = CURRENT_FOLDER/'bf1_players'
BF1_SERVERS_DATA = CURRENT_FOLDER/'bf1_servers'


from sqlalchemy import (
    Column, Integer, BigInteger, DateTime, String, Boolean,
    func, ForeignKey, PrimaryKeyConstraint
)
from sqlalchemy.orm import declarative_base, relationship, selectinload, sessionmaker 
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

###################### Data Model #########################
Base = declarative_base()

class Bf1Admins(Base):
    __tablename__ = 'bf1admins'
    __table_args__ = ({'sqlite_autoincrement': True}, )
    id = Column(Integer, primary_key=True, autoincrement=True)
    pid = Column(BigInteger, unique=True, nullable=False)
    remid = Column(String, nullable=False)
    sid = Column(String, nullable=False)
    token = Column(String, default=None, nullable=True)
    sessionid = Column(String, default=None, nullable=True)
    managed_servers = relationship("ServerBf1Admins")

class Servers(Base):
    __tablename__ = 'servers'
    guid = Column(String, unique=True, nullable=False)
    # gameid = Column(BigInteger, nullable=False) # We shall record it in redis
    serverid = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    keyword = Column(String, nullable=True)
    opserver = Column(Boolean, nullable=True)

class ServerBf1Admins(Base):
    __tablename__ = 'serverbf1admins'
    serverid = Column(Integer, nullable=False)
    pid = Column(BigInteger, ForeignKey('bf1admins.pid'), nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint(serverid, pid),
        {}
    )

class Players(Base):
    __tablename__ = 'players'
    pid = Column(BigInteger, nullable=False)
    originid = Column(String, nullable=True)
    qq = Column(BigInteger, primary_key=True)


class ChatGroups(Base):
    __tablename__ = 'groups'
    groupqq = Column(BigInteger, primary_key=True)
    owner = Column(BigInteger, nullable=True)
    bind_to_group = Column(BigInteger, ForeignKey(groupqq)) # Primary group qq
    welcome = Column(String, default='', nullable=True)
    members = relationship("GroupMembers")
    admins = relationship("GroupAdmins")
    servers = relationship("GroupServerBind")


class GroupMembers(Base):
    __tablename__ = 'groupmembers'
    qq = Column(BigInteger, nullable=False)
    groupqq = Column(BigInteger, ForeignKey('groups.groupqq'))
    pid = Column(BigInteger, ForeignKey('players.pid'))
    __table_args__ = (
        PrimaryKeyConstraint(groupqq, qq),
        {}
    )


class GroupAdmins(Base):
    __tablename__ = 'groupadmins'
    qq = Column(BigInteger)
    groupqq = Column(BigInteger, ForeignKey('groups.groupqq'))
    perm = Column(Integer, nullable=True, default=0) # Reserved column for finner grade access control
    __table_args__ = (
        PrimaryKeyConstraint(groupqq, qq),
        {}
    )


class GroupServerBind(Base):
    __tablename__ = "groupservers"
    groupqq = Column(BigInteger, ForeignKey('groups.groupqq'))
    serverid = Column(Integer, ForeignKey('servers.serverid'))
    ind = Column(String, nullable=False)
    alias = Column(String, nullable=True)
    whitelist = Column(String, nullable=True)
    perm = Column(Integer, nullable=True, default=1)
    __table_args__ = (
        PrimaryKeyConstraint(groupqq, ind),
        {}
    )
    

class ServerVips(Base):
    __tablename__ = "servervips"
    serverid = Column(Integer, ForeignKey('servers.serverid'))
    pid = Column(BigInteger, ForeignKey('players.pid'))
    originid = Column(String)
    expire = Column(DateTime, nullable=True) # Null can mean a permanent vip
    enabled = Column(Boolean, default=False, nullable=False) 
    __table_args__ = (
        PrimaryKeyConstraint(serverid, pid),
        {}
    )


class ServerVBans(Base):
    __tablename__ = "servervbans"
    serverid = Column(Integer, ForeignKey('servers.serverid'))
    pid = Column(BigInteger, ForeignKey('players.pid'))
    reason = Column(String, default="Virtual Banned")
    processor = Column(BigInteger, nullable=False)
    time = Column(DateTime, nullable=True)
    notify_group = Column(BigInteger, ForeignKey('groups.groupqq'))
    __table_args__ = (
        PrimaryKeyConstraint(serverid, pid),
        {}
    )


###################### DB Helper ###########################
engine = create_async_engine(f"sqlite+aiosqlite:///{path_to_bfchat_data}/bot.db", echo=True)

async def close_db():
    await engine.dispose()


# Generate table
async def init_db2():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(init_db2())
asyncio.run(close_db())

# Helpers for importing data
conn = sqlite3.connect(CURRENT_FOLDER/'bot.db')
def db_op(sql: str, params: list):
    cur = conn.cursor()
    res = conn.execute(sql, params).fetchall()
    cur.connection.commit()
    cur.close()
    return res    

def db_op_many(sql: str, params: list):
    cur = conn.cursor()
    res = conn.executemany(sql, params).fetchall()
    cur.connection.commit()
    cur.close()
    return res    

###################### Migration ###########################
bf1admin_filenames = [f"id{i}.txt" for i in [''] + list(range(1, len(bf1admin_pid)))]
for i in range(len(bf1admin_pid)):
    if not os.path.exists(BF1_SERVERS_DATA/'Caches'/bf1admin_filenames[i]):
        continue
    with open(BF1_SERVERS_DATA/'Caches'/bf1admin_filenames[i],'r' ,encoding='UTF-8') as f:
        remid, sid = f.read().split(',')
        db_op('INSERT INTO bf1admins (pid, remid, sid) VALUES (?, ?, ?);', [int(bf1admin_pid[i]), remid, sid])

wait = input("bf1admin finished. Press Enter to continue.")

# Servers, groups, group server binds
group_servers = []
group_servers_dict = {}
gameid_serverid = {}
for f in os.listdir(BF1_SERVERS_DATA):
    if f.endswith('_jsonBL'):
        for s in os.listdir(BF1_SERVERS_DATA/f):
            groupqq, index = re.split("\_|\.", s)[:-1]
            with open(BF1_SERVERS_DATA/f/s,'r' ,encoding='UTF-8') as fs:
                serverBL = json.load(fs)
                guid = serverBL['result']['serverInfo']['guid']
                gameId = int(serverBL['result']['serverInfo']['gameId'])
                serverid = int(serverBL['result']['rspInfo']['server']['serverId'])
                name = serverBL['result']['serverInfo']['name']
                is_operation_server = serverBL['result']['serverInfo']['mapMode'] == 'BreakthroughLarge'
                keywords = None
                if os.path.exists(BF1_SERVERS_DATA/groupqq/s):
                    with open(BF1_SERVERS_DATA/groupqq/s,'r' ,encoding='UTF-8') as fs_keyword:
                        keyword = fs_keyword.read()
                group_servers.append((groupqq, serverid, index))
                group_servers_dict[f'{groupqq}_{index}'] = serverid
                gameid_serverid[gameId] = serverid
                db_op("INSERT OR IGNORE INTO servers (guid, serverid, name, keyword, opserver) VALUES (?,?,?,?,?);", [guid, int(serverid), name, keyword, is_operation_server])
    elif f.endswith('_session.txt'):
        groupqq = int(f.split('_')[0])
        with open(BF1_SERVERS_DATA/f,'r' ,encoding='UTF-8') as fs_group:
            bind_to_group = int(fs_group.read())
        welcome = ''
        if os.path.exists(BF1_SERVERS_DATA/f'{f}_apply'/'config.txt'):
            with open(BF1_SERVERS_DATA/f'{f}_apply'/'config.txt', 'r', encoding='UTF-8') as fwelcome:
                welcome = fwelcome.read()
        db_op("INSERT INTO groups (groupqq, bind_to_group, welcome) VALUES (?, ?, ?);", [groupqq, bind_to_group, welcome])

db_op_many('INSERT INTO groupservers (groupqq, serverid, ind, perm) VALUES (?,?,?,1);', group_servers)

wait = input("servers, groups, server_group_bind finished. Press Enter to continue.")

# Players and group_members
players = {}
group_members = []
for f in os.listdir(BF1_PLAYERS_DATA):
    if f.endswith('.txt'):
        with open(BF1_PLAYERS_DATA/f, encoding='UTF-8') as fs_player:
            pid = fs_player.read()
            if pid not in players:
                players[pid] = {'qq': f.split('.')[0], 'origin': None}
    elif os.path.isdir(BF1_PLAYERS_DATA/f) and f not in ["whitelist", "Emblem", "Code", "Caches"]:
        for ff in os.listdir(BF1_PLAYERS_DATA/f):
            if not ff.endswith('.txt'):
                continue
            if len(re.split("\_|\.", ff)[:-1]) == 1:
                print(f, ff, len(re.split("\_|\.", ff)[:-1]))
            qq, pid = re.split("\_|\.", ff)[:-1]
            with open(BF1_PLAYERS_DATA/f/ff, encoding='UTF-8') as ffs_player:
                originid = ffs_player.read()
            if pid not in players:
                players[pid] = {'qq': qq}
            else:
                players[pid]['qq'] = qq
            if originid != 'None':
                players[pid]['originid'] = originid
            group_members.append((qq, f, pid))
players_list = []
for k in players:
    v = players[k]
    players_list.append((int(k), int(v['qq']), v['originid'] if 'originid' in v else None))
db_op_many('INSERT INTO players (pid, qq, originid) VALUES (?,?,?);', players_list)
db_op_many('INSERT INTO groupmembers (qq, groupqq, pid) VALUES (?,?,?);', group_members)

wait = input("Players and group_members finished. Press Enter to continue.")

# group admin, group server bind alias
for g in os.listdir(BF1_SERVERS_DATA):
    if g.isdigit():
        for f in os.listdir(BF1_SERVERS_DATA/g):
            groupqq, index = re.split("\_|\.", f)[:-1]
            with open(BF1_SERVERS_DATA/f'{g}_session.txt','r' ,encoding='UTF-8') as fff:
                primary_group = fff.read()
            if (not os.path.exists(BF1_SERVERS_DATA/f'{g}_jsonBL'/f)) and (not os.path.exists(BF1_SERVERS_DATA/f'{primary_group}_jsonBL'/f)):
                with open(BF1_SERVERS_DATA/g/f,'r' ,encoding='UTF-8') as fs_alias:
                    true_index = fs_alias.read()
                    db_op("UPDATE groupservers SET alias=? WHERE groupqq=? AND ind=?;", [str(index), int(groupqq), str(true_index)])

for f in os.listdir(BF1_SERVERS_DATA):
    if f.endswith('admin.txt'):
        groupqq = int(f.split('_')[0])
        main_groupqq = db_op("SELECT bind_to_group FROM groups WHERE groupqq=?", [groupqq])[0][0]
        with open(BF1_SERVERS_DATA/f,'r' ,encoding='UTF-8') as fs_admin:
            for qq in fs_admin.read().split(','):
                if qq.isdigit():
                    db_op("INSERT OR IGNORE INTO groupadmins (qq, groupqq) VALUES (?, ?);", [qq, main_groupqq])

wait = input("group admins and grouperver alias finished. Press Enter to continue.")

# vip, vban, whitelist
for g in os.listdir(BF1_SERVERS_DATA):
    if g.endswith('_vip'):
        for v in os.listdir(BF1_SERVERS_DATA/g):
            try:
                with open(BF1_SERVERS_DATA/g/v, 'r', encoding='UTF-8') as fvip:
                    originid = fvip.read()
            except Exception as e:
                print(g, v)
            vip = v.split('_')
            if len(vip) != 4 and len(vip) !=5:
                continue
            enabled = len(vip) == 4
            serverid = group_servers_dict[f'{vip[0]}_{vip[1]}']
            expire = datetime.datetime.strptime(vip[3], '%Y-%m-%d')
            exists = db_op("SELECT expire, enabled FROM servervips WHERE serverid=? AND pid=?;", [int(serverid), int(vip[2])])
            if len(exists):
                expire = max(expire, datetime.datetime.fromisoformat(exists[0][0]))
                enabled = enabled and exists[0][1]
                db_op("UPDATE servervips SET expire=?, enabled=? WHERE serverid=? AND pid=?;", [expire, enabled, serverid, vip[2]])
            else:
                db_op("INSERT INTO servervips (serverid, pid, expire, enabled, originid) VALUES (?, ?, ?, ?, ?);", [int(serverid), int(vip[2]), expire, enabled, originid])

for s in os.listdir(BF1_SERVERS_DATA/'vban'):
    groupqq, index = s.split('_')[:-1]
    serverid = group_servers_dict[f'{groupqq}_{index}']
    with open(BF1_SERVERS_DATA/'vban'/s, 'r', encoding='UTF-8') as fs_vban:
        data = json.load(fs_vban)
        for pid in data:
            ban = data[pid]
            time = datetime.datetime.fromisoformat(ban['time'])
            db_op("INSERT OR IGNORE INTO servervbans (serverid, pid, time, reason, processor, notify_group) VALUES (?, ?, ?, ?, ?, ?);",
                  [int(serverid), int(pid), time, ban['reason'], ban['qq'], groupqq])
            
for s in os.listdir(BF1_PLAYERS_DATA/'whitelist'):
    groupqq, index = re.split("\_|\.", s)[:-1]
    with open(BF1_PLAYERS_DATA/'whitelist'/s, 'r', encoding='UTF-8') as fs_whitelist:
        white = fs_whitelist.read()
        db_op("UPDATE groupservers SET whitelist=? WHERE groupqq=? AND ind=?;", [white, int(groupqq), str(index)])        
            
wait = input("group whitelist, ban and vip finished. Press Enter to continue.")

# server-bf1admin bindings
server_bf1admin_files = [f"{i}.json" for i in range(len(bf1admin_pid))]
server_bf1admins = {}
for i in range(len(bf1admin_pid)):
    with open(CURRENT_FOLDER/server_bf1admin_files[i], 'r') as f_sba:
        gids = [int(gid_s) for gid_s in f_sba.read().rstrip(',').split(',')]
        for gid in gids:
            if gid in gameid_serverid.keys():
                server_bf1admins[gameid_serverid[gid]]=bf1admin_pid[i]
db_op_many("INSERT INTO serverbf1admins (serverid, pid) VALUES (?, ?);", server_bf1admins.items())
wait = input("server-bf1admin bindings finished. Press Enter to continue.")


conn.close()