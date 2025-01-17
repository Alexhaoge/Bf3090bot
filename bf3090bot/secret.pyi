from typing import Awaitable, List, Any

async def upd_blazestat(personaId: int | str, method: str) -> Awaitable[dict | int]: ...
async def upd_blazepl(gameId: int | str) -> Awaitable[dict]: ...
async def Blaze2788Pro(gameIds: List[int]) -> Awaitable[dict]: ...
async def upd_blazeplforvban(gameIds: List[int]) -> Awaitable[dict]: ...
async def get_blazeplbyid(remid: str, sid: str, sessionID: str, gameId: int | str) -> Awaitable[dict]: ...
async def get_blazepl(remid: str, sid: str, sessionID: str, gameId: int | str) -> Awaitable[dict]: ...

async def bfeac_checkBan(personaId: int) -> Awaitable[dict]: ...
async def bfeac_checkBanMulti(pids: list) -> Awaitable[list]: ...
async def bfeac_report(playerName: str, case_body: str) -> Awaitable[dict | bytes]: ...
async def bfban_report(playerName: str,
                       case_body: str,
                       cheat_number: int,
                       videoLink: str,
                       bfban_token: str) -> Awaitable[dict | bytes]: ...
async def bfban_checkBan(player_pid: str) -> Awaitable[dict]: ...

async def record_api(player_pid: int | str) -> Awaitable[dict]: ...

async def tyc(remid: str, sid: str, sessionID: str, id: int, name: str, pidid: int) -> Awaitable[str]: ...

async def upd_updateServer(remid: str, sid: str, sessionID: str,
                           rspInfo: dict,
                           maps: List[dict],
                           name: str,
                           description: str,
                           settings: str) -> Awaitable[Any]: ...

async def get_inner_pl(gameid: int) -> Awaitable[dict]: ...