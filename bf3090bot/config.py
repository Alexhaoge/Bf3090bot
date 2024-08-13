from pydantic import BaseSettings


class Config(BaseSettings):
    # Your Config Here
    bfchat_prefix: str = '.'
    bfchat_dir: str = './bfchat_data/'
    database_url: str = 'sqlite+aiosqlite:///./bfchat_data/bot.db'
    redis_url: str = 'redis://localhost'
    gametool_url: str = 'https://api.gametools.network/'
    port: int = 16000
    oss_access_key_id: str
    oss_access_key_secret: str
    oss_bucket_name: str
    oss_endpoint: str

    class Config:
        extra = "ignore"