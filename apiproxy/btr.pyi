import httpx
from typing import Awaitable

btr_url: str
async def fetch_re(origin_id: str, client: httpx.AsyncClient) -> Awaitable[dict]: ...
async def fetch_id(report_id: str|int, pid: int, client: httpx.AsyncClient) -> Awaitable[dict]: ...