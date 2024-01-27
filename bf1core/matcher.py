from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER
from nonebot import on_command,on_notice, on_request
from nonebot.rule import Rule,to_me

from ..utils import PREFIX
from ..bf1helper import *

#help
BF1_PING = on_command(f"{PREFIX}ping",aliases={f'{PREFIX}原神'},block=True, priority=1)
BF1_HELP = on_command(f"{PREFIX}help",block=True, priority=1)
BF1_FAQ = on_command(f"{PREFIX}FAQ",block=True, priority=1)

#info
BF1_CODE = on_command(f"{PREFIX}code", block=True, priority=1)
BF1_ADMIN_ADD_CODE = on_command(f"{PREFIX}addcode", block=True, priority=1, permission=SUPERUSER)
BF1_ADMIN_DEL_CODE = on_command(f"{PREFIX}delcode", block=True, priority=1, permission=SUPERUSER)
BF1_REPORT = on_command(f"{PREFIX}举报",aliases={f'{PREFIX}举办', f'{PREFIX}report'}, block=True, priority=1)
BF1_BOT = on_command(f"{PREFIX}bot", aliases={f'{PREFIX}管服号'}, block=True, priority=1)
BF1_PLA = on_command(f'{PREFIX}搜战队', block=True, priority=1)
BF1_PLAA = on_command(f'{PREFIX}查战队成员', aliases={f'{PREFIX}查成员'}, block=True, priority=1)
BF_STATUS = on_command(f'{PREFIX}bf status', block=True, priority=1)
BF1_STATUS = on_command(f'{PREFIX}bf1 status', aliases={f'{PREFIX}战地1', f'{PREFIX}status', f'{PREFIX}bf1'}, block=True, priority=1)
BF1_MODE= on_command(f'{PREFIX}bf1 mode', block=True, priority=1)
BF1_MAP= on_command(f'{PREFIX}bf1 map', block=True, priority=1)
BF1_INFO= on_command(f'{PREFIX}info', block=True, priority=1)
BF1_EX= on_command(f'{PREFIX}交换', block=True, priority=1)
BF1_DRAW= on_command(f'{PREFIX}draw', block=True, priority=1)
BF1_ADMINDRAW= on_command(f'{PREFIX}admindraw', block=True, priority=1)

#stat
BF1_BIND_PID = on_command(f'{PREFIX}bind', aliases={f'{PREFIX}绑定', f'{PREFIX}绑id'}, block=True, priority=1)
BF1_SA= on_command(f'{PREFIX}查', block=True, priority=1)
BF1_TYC= on_command(f'{PREFIX}tyc', aliases={f'{PREFIX}天眼查'}, block=True, priority=1)
BF1_WP= on_command(f'{PREFIX}武器', aliases={f'{PREFIX}w', f'{PREFIX}wp', f'{PREFIX}weapon'}, block=True, priority=1)
BF1_S= on_command(f'{PREFIX}s', aliases={f'{PREFIX}stat', f'{PREFIX}战绩', f'{PREFIX}查询',f'{PREFIX}生涯'}, block=True, priority=1)
BF1_R= on_command(f'{PREFIX}r', aliases={f'{PREFIX}对局'}, block=True, priority=1)
BF1_RE= on_command(f'{PREFIX}最近', block=True, priority=1)

#serverbind
BF1_INIT = on_command(f'{PREFIX}init', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_BIND = on_command(f'{PREFIX}绑服', block=True, priority=1, permission=SUPERUSER)
BF1_REBIND = on_command(f'{PREFIX}改绑', block=True, priority=1, permission=SUPERUSER)
BF1_ADDBIND = on_command(f'{PREFIX}添加服别名', block=True, priority=1, permission=SUPERUSER)
BF1_ADDADMIN = on_command(f'{PREFIX}addadmin', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_DELADMIN = on_command(f'{PREFIX}deladmin', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_ADMINLIST = on_command(f'{PREFIX}adminlist', aliases={f'{PREFIX}管理列表'}, block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)

#rsp
BF1_ADDBF1ACCOUNT = on_command(f'{PREFIX}bfaccount', block=True, priority=1, permission=SUPERUSER)
BF1_F= on_command(f'{PREFIX}f', block=True, priority=1)
BF1_CHOOSELEVEL = on_command(f'{PREFIX}map', block=True, priority=1)
BF1_KICK = on_command(f'{PREFIX}k', aliases={f'{PREFIX}kick', f'{PREFIX}踢出'}, block=True, priority=1)
BF1_KICKALL = on_command(f'{PREFIX}kickall', aliases={f'{PREFIX}炸服', f'{PREFIX}清服'}, block=True, priority=1)
BF1_BAN = on_command(f'{PREFIX}ban', block=True, priority=1)
BF1_BANALL = on_command(f'{PREFIX}bana',aliases={f'{PREFIX}banall', f'{PREFIX}ba'}, block=True, priority=1)
BF1_UNBAN = on_command(f'{PREFIX}unban', block=True, priority=1)
BF1_UNBANALL = on_command(f'{PREFIX}unbana',aliases={f'{PREFIX}unbanall', f'{PREFIX}uba'}, block=True, priority=1)
BF1_VBAN = on_command(f'{PREFIX}vban', aliases={f'{PREFIX}vb'}, block=True, priority=1)
BF1_VBANALL = on_command(f'{PREFIX}vbana',aliases={f'{PREFIX}vbanall', f'{PREFIX}vba'}, block=True, priority=1)
BF1_UNVBAN = on_command(f'{PREFIX}unvban', aliases={f'{PREFIX}uvb',f'{PREFIX}uvban'} , block=True, priority=1)
BF1_UNVBANALL = on_command(f'{PREFIX}unvbana',aliases={f'{PREFIX}unvbanall', f'{PREFIX}uvba',f'{PREFIX}unvba'}, block=True, priority=1)
BF1_MOVE = on_command(f'{PREFIX}move', block=True, priority=1)
BF1_VIP = on_command(f'{PREFIX}vip', block=True, priority=1)
BF1_VIPLIST = on_command(f'{PREFIX}viplist', block=True, priority=1)
BF1_CHECKVIP = on_command(f'{PREFIX}checkvip', block=True, priority=1)
BF1_UNVIP = on_command(f'{PREFIX}unvip', block=True, priority=1)
BF1_PL = on_command(f'{PREFIX}pl', block=True, priority=1)
BF1_ADMINPL = on_command(f'{PREFIX}adminpl', block=True, priority=1)
BF1_PLS = on_command(f'{PREFIX}查黑队', block=True, priority=1)
BF1_PLSS = on_command(f'{PREFIX}查战队', block=True, priority=1)
BF1_UPD = on_command(f'{PREFIX}配置', block=True, priority=1)
BF1_INSPECT = on_command(f'{PREFIX}查岗', block=True, priority=1)

#grouprsp
del_user = on_notice(Rule(_is_del_user), priority=1, block=True)
get_user = on_notice(Rule(_is_get_user), priority=1, block=True)
add_user = on_request(Rule(_is_add_user), priority=1, block=True)
welcome_user = on_command(f'{PREFIX}配置入群欢迎', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
approve_req = on_command('y',rule = to_me ,aliases={'n'},priority=1, block=True)

#scheduler
BF1_SERVER_ALARM = on_command(f'{PREFIX}打开预警', block=True, priority=1)
BF1_SERVER_ALARMOFF = on_command(f'{PREFIX}关闭预警', block=True, priority=1)

#serverlog
BF1_SLP = on_command(f'{PREFIX}slog', aliases={f'{PREFIX}搜日志', f'{PREFIX}sl'}, block=True, priority=1)
BF1_SLF = on_command(f'{PREFIX}log', aliases={f'{PREFIX}服务器日志'}, block=True, priority=1)
BF1_SLK = on_command(f'{PREFIX}slogkey', aliases={f'{PREFIX}slk'}, block=True, priority=1)