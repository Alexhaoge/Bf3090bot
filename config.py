from pydantic import BaseSettings


class Config(BaseSettings):
    # Your Config Here
    bfchat_prefix: str = '.'
    bfchat_dir: str = './bfchat_data/'
    database_url: str = 'sqlite+aiosqlite:///./bfchat_data/bot.db'
    redis_url: str = 'redis://localhost'
    gametool_url: str = 'https://api.gametools.network/'
    class Config:
        extra = "ignore"