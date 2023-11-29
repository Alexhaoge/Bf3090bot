from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent
from nonebot.typing import T_State
from nonebot_plugin_htmlrender import md_to_pic, html_to_pic

from ..utils import PREFIX, ASSETS_FOLDER, CURRENT_FOLDER
from ..bf1draw import *

from .matcher import BF1_PING,BF1_HELP,BF1_FAQ

from PIL import Image
from pathlib import Path

@BF1_PING.handle()
async def bf1_ping(event:GroupMessageEvent, state:T_State):
    with Image.open(Path('file:///') / CURRENT_FOLDER/'ys.png') as im:
        await BF1_PING.send(MessageSegment.reply(event.message_id) + MessageSegment.image(base64img(im)))

@BF1_HELP.handle()
async def bf_help(event:MessageEvent, state:T_State):
    with open(ASSETS_FOLDER/'Readme.md',encoding='utf-8') as f:
        md_help = f.read()
    
    md_help = md_help.format(p=PREFIX)

    pic = await md_to_pic(md_help, css_path=ASSETS_FOLDER/"github-markdown-dark.css",width=900)

    await BF1_HELP.send(MessageSegment.reply(event.message_id) + MessageSegment.image(pic) + '捐赠地址：爱发电搜索Mag1Catz，所有收益将用于服务器运行。输入.code [代码]可以更换查战绩背景。\n使用EAC功能请直接输入.举报 id。\n更多问题请输入.FAQ查询或加群908813634问我。')

@BF1_FAQ.handle()
async def bf_faq(event:MessageEvent, state:T_State):
    file_dir = await draw_faq()
    #file_dir = Path('file:///') / CURRENT_FOLDER/'Caches'/'faq.png'
    await BF1_FAQ.send(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))