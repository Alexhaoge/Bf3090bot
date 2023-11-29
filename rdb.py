from sqlalchemy import (
    Column, Integer, BigInteger, DateTime, String, Boolean, Index,
    func, ForeignKey, PrimaryKeyConstraint
)
from sqlalchemy.orm import declarative_base, relationship, selectinload, sessionmaker 
from sqlalchemy.sql.base import Executable

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from .utils import DATABASE_URL

###################### Data Model #########################
Base = declarative_base()

# Write your data tables here
class Bf1Admins(Base):
    __tablename__ = 'bf1admins'
    __table_args__ = ({'sqlite_autoincrement': True}, )
    id = Column(Integer, primary_key=True, autoincrement=True)
    pid = Column(BigInteger, unique=True, nullable=False)
    # Affordable to update frequently since this table is very small
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
    """
    Some groups are bound to others, we call the latter as primary group and former as non-primary. 
    Non-primary groups will use the server, admin, and group member information from their bound primary groups.
    """
    __tablename__ = 'groups'
    groupqq = Column(BigInteger, primary_key=True)
    owner = Column(BigInteger, nullable=True)
    bind_to_group = Column(BigInteger, ForeignKey(groupqq)) # Primary group qq
    welcome = Column(String, default='', nullable=True)
    alarm = Column(Boolean, default=0)
    members = relationship("GroupMembers")
    admins = relationship("GroupAdmins")
    servers = relationship("GroupServerBind")


class GroupMembers(Base):
    """
    We do group member and player binding together in this table.
    """
    __tablename__ = 'groupmembers'
    qq = Column(BigInteger, nullable=False)
    groupqq = Column(BigInteger, ForeignKey('groups.groupqq'))
    pid = Column(BigInteger, nullable=False)
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
    # Reserved column for access control group server bind
    # purpose: restrict admin access to a server that does not belong
    # to this chat group yet bind to monitor
    perm = Column(Integer, nullable=True, default=1)
    __table_args__ = (
        PrimaryKeyConstraint(groupqq, ind),
        {}
    )
    

class ServerVips(Base):
    __tablename__ = "servervips"
    serverid = Column(Integer, ForeignKey('servers.serverid'))
    pid = Column(BigInteger, nullable=False)
    originid = Column(String)
    expire = Column(DateTime, nullable=True) # Null can mean a permanent vip
    # Enabled mark for opeation server vip. Set to False for every vip update and set to True after checkvip
    enabled = Column(Boolean, default=False, nullable=False) 
    __table_args__ = (
        PrimaryKeyConstraint(serverid, pid),
        {}
    )


class ServerVBans(Base):
    __tablename__ = "servervbans"
    serverid = Column(Integer, ForeignKey('servers.serverid'))
    pid = Column(BigInteger, nullable=False)
    reason = Column(String, default="Virtual Banned")
    processor = Column(BigInteger, nullable=False)
    time = Column(DateTime, nullable=True)
    notify_group = Column(BigInteger, ForeignKey('groups.groupqq'))
    __table_args__ = (
        PrimaryKeyConstraint(serverid, pid),
        {}
    )


class BotVipCodes(Base):
    __tablename__ = "botvipcodes"
    code = Column(String, primary_key=True)
    pid = Column(BigInteger, nullable=False)

###################### Table Ends ##########################

###################### DB Helper ###########################
engine = create_async_engine(DATABASE_URL)

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    await engine.dispose()

async_db_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db_session() -> AsyncSession:
    async with async_db_session() as session:
        yield session

async def async_db_op(stmt: Executable):
    async with async_db_session() as session:
        result = await session.execute(stmt)
        return result


__all__ = [
    'Bf1Admins', 'Servers', 'ChatGroups', 'Players', 
    'GroupServerBind', 'GroupAdmins', 'GroupMembers', 
    'ServerVips', 'ServerVBans', 'ServerBf1Admins', 'BotVipCodes',
    'engine', 'init_db', 'close_db',
    'async_db_session', 'get_db_session', 'async_db_op'
]