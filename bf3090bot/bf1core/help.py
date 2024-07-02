import nonebot
import asyncio

from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent
from nonebot.typing import T_State
from nonebot.params import _command_arg
from nonebot_plugin_htmlrender import md_to_pic

from ..utils import PREFIX, ASSETS_FOLDER, CURRENT_FOLDER
from ..bf1draw import base64img, draw_faq
from ..bf1helper import check_sudo

from .matcher import BF1_PING, BF1_HELP, BF1_FAQ, BF1_ADMINHELP, BF1_RADIO

from PIL import Image
from pathlib import Path

@BF1_PING.handle()
async def bf1_ping(event:GroupMessageEvent, state:T_State):
    with Image.open(Path('file:///') / CURRENT_FOLDER/'ys.png') as im:
        await BF1_PING.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(base64img(im)))

@BF1_HELP.handle()
async def bf_help(event:GroupMessageEvent, state:T_State):
    with open(ASSETS_FOLDER/'README.md',encoding='utf-8') as f:
        md_help = f.read()
    
    md_help = md_help.format(p=PREFIX)

    pic = await md_to_pic(md_help, css_path=ASSETS_FOLDER/"github-markdown-dark.css",width=900)

    await BF1_HELP.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(pic) + '拉bot/bug反馈/绑服申请/其他需求请加群908813634。\nbot使用完全免费，如果出现付费拉bot的情况请直接联系作者举报，qq120681532。\n捐赠地址：https://afdian.net/a/Mag1Catz，所有收益将用于服务器运行。输入.code [代码]可以更换查战绩背景。\n使用EAC功能请直接输入.举报 id。')

@BF1_ADMINHELP.handle()
async def bf_admin_help(event:GroupMessageEvent, state:T_State):
    if check_sudo(event.group_id, event.user_id):
        with open(ASSETS_FOLDER/'adminhelp.md',encoding='utf-8') as f:
            md_help = f.read()
        md_help = md_help.format(p=PREFIX)
        pic = await md_to_pic(md_help, css_path=ASSETS_FOLDER/"github-markdown-dark.css",width=900)
        await BF1_ADMINHELP.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(pic))

@BF1_FAQ.handle()
async def bf_faq(event:GroupMessageEvent, state:T_State):
    file_dir = await draw_faq()
    #file_dir = Path('file:///') / CURRENT_FOLDER/'Caches'/'faq.png'
    await BF1_FAQ.finish(MessageSegment.reply(event.message_id) + MessageSegment.image(file_dir))

@BF1_RADIO.handle()
async def bf_faq(event:GroupMessageEvent, state:T_State):
    message = _command_arg(state) or event.get_message()
    message = message.extract_plain_text()
    bots = nonebot.get_bots()
    cnt = 0
    for bot in bots.values():
        botlist = await bot.get_group_list()
        for i in botlist:
            group_id = int(i["group_id"])
            try:
                await bot.send_group_msg(group_id=group_id, message=message)
                cnt+=1
            except:
                pass
            await asyncio.sleep(2)
    await BF1_RADIO.finish(f"已发送{cnt}条群消息")
        
            