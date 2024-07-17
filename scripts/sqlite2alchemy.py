# Migration scrip from local json file data to db
# Depreacated: should not be used anymore after migration

import asyncio
from typing import TypeVar
from pathlib import Path

# Change these!
path_to_bfchat_data = "bfchat_data" 
DATA_FOLDER = Path(path_to_bfchat_data).resolve()

from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker 
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)
nonebot.load_from_toml("pyproject.toml")

###################### Data Model #########################
from bf3090bot.rdb import (
    Base, Bf1Admins, Servers, ChatGroups, Players,
    GroupServerBind, GroupAdmins, GroupMembers, 
    ServerVips, ServerVBans, ServerBf1Admins, BotVipCodes,
    engine
)

###################### DB Helper ###########################
async_db_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

engine_old = create_async_engine(f"sqlite+aiosqlite:///{path_to_bfchat_data}/bot.db")
async_db_session_old = sessionmaker(
    engine_old, class_=AsyncSession, expire_on_commit=False
)

async def close_db():
    await engine.dispose()
    await engine_old.dispose()

# Generate table
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with engine_old.begin() as conn_old:
        await conn_old.run_sync(Base.metadata.create_all)

T = TypeVar('T')
async def migrate_table(model_class: T):
    async with async_db_session_old() as session_old, async_db_session() as session:
        await session.execute(text('SET CONSTRAINTS ALL DEFERRED'))
        table = (await session_old.execute(select(model_class))).all()
        for r in table:
            new_r = model_class()
            mapper = inspect(model_class)
            for attr in mapper.column_attrs:
                setattr(new_r, attr.key, getattr(r[0], attr.key))
            session.add(new_r)
        await session.commit()
        await session.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))
        
async def migrate_chatgroups():
    async with async_db_session_old() as session_old, async_db_session() as session:
        main_group = (await session_old.execute(
            select(ChatGroups).filter(ChatGroups.groupqq==ChatGroups.bind_to_group)
        )).all()
        for r in main_group:
            new_r = ChatGroups()
            mapper = inspect(ChatGroups)
            for attr in mapper.column_attrs:
                setattr(new_r, attr.key, getattr(r[0], attr.key))
            session.add(new_r)
        await session.commit()

        bind_group = (await session_old.execute(
            select(ChatGroups).filter(ChatGroups.groupqq!=ChatGroups.bind_to_group)
        )).all()
        for r in bind_group:
            new_r = ChatGroups()
            mapper = inspect(ChatGroups)
            for attr in mapper.column_attrs:
                setattr(new_r, attr.key, getattr(r[0], attr.key))
            session.add(new_r)
        await session.commit()


async def migrate_table_check_group(model_class: T, groupqq_name: str = 'groupqq'):
    async with async_db_session_old() as session_old, async_db_session() as session:
        await session.execute(text('SET CONSTRAINTS ALL DEFERRED'))
        table = (await session_old.execute(select(model_class))).all()
        for r in table:
            referenced_group = (await session.execute(select(ChatGroups).filter_by(groupqq=getattr(r[0], groupqq_name)))).first()
            if not referenced_group:
                continue
            new_r = model_class()
            mapper = inspect(model_class)
            for attr in mapper.column_attrs:
                setattr(new_r, attr.key, getattr(r[0], attr.key))
            session.add(new_r)
        await session.commit()
        await session.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))

async def migrate_vban():
    async with async_db_session_old() as session_old, async_db_session() as session:
        await session.execute(text('SET CONSTRAINTS ALL DEFERRED'))
        table = (await session_old.execute(select(ServerVBans))).all()
        for r in table:
            referenced_group = (await session.execute(select(ChatGroups).filter_by(groupqq=r[0].notify_group))).first()
            new_r = ServerVBans(serverid=r[0].serverid, pid=r[0].pid,
                                reason=r[0].reason, processor=r[0].processor,
                                time=r[0].time, 
                                notify_group=r[0].notify_group if referenced_group else None)
            session.add(new_r)
        await session.commit()
        await session.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))

async def migrate_extra():
    async with async_db_session() as session:
        await session.execute(text("SELECT setval('bf1admins_id_seq', (SELECT MAX(id) FROM bf1admins));"))
        await session.commit()

async def main():
    await init_db()
    await migrate_table(Bf1Admins)
    await migrate_table(Servers)
    await migrate_table(ServerBf1Admins)
    await migrate_table(Players)
    await migrate_chatgroups()
    await migrate_table_check_group(GroupMembers)
    await migrate_table_check_group(GroupAdmins)
    await migrate_table_check_group(GroupServerBind)
    await migrate_table(ServerVips)
    await migrate_table_check_group(ServerVBans, 'notify_group')
    await migrate_table(BotVipCodes)
    await migrate_extra()
    await close_db()

###################### Migration ###########################
if __name__ == "__main__":
    asyncio.run(main())
