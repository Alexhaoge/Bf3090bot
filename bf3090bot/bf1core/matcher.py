from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER
from nonebot import on_command, on_notice, on_request, require, on_shell_command
from nonebot.rule import Rule, to_me, ArgumentParser
from argparse import RawTextHelpFormatter

require("nonebot_plugin_access_control_api")
from nonebot_plugin_access_control_api.service import create_plugin_service

from ..utils import PREFIX
from ..bf1helper import _is_add_user, _is_del_user, _is_get_user

#help
BF1_PING = on_command(f"{PREFIX}ping",aliases={f'{PREFIX}原神'},block=True, priority=1)
BF1_HELP = on_command(f"{PREFIX}help",block=True, priority=1)
BF1_ADMINHELP = on_command(f"{PREFIX}adminhelp",block=True, priority=1)
BF1_FAQ = on_command(f"{PREFIX}FAQ",aliases={f'{PREFIX}常见问题'},block=True, priority=1)
BF1_RADIO = on_command(f"{PREFIX}公告",block=True, priority=1, permission=SUPERUSER)

#info
BF1_CODE = on_command(f"{PREFIX}code", block=True, priority=1)
BF1_ADMIN_ADD_CODE = on_command(f"{PREFIX}addcode", block=True, priority=1, permission=SUPERUSER)
BF1_ADMIN_DEL_CODE = on_command(f"{PREFIX}delcode", block=True, priority=1, permission=SUPERUSER)
BF1_REPORT = on_command(f"{PREFIX}举报",aliases={f'{PREFIX}举办', f'{PREFIX}report'}, block=True, priority=1)
BF1_OSS_TEST = on_command(f"{PREFIX}图床测试", block=True, priority=1)
BF1_BOT = on_command(f"{PREFIX}bot", aliases={f'{PREFIX}管服号'}, block=True, priority=1)
BF1_PLA = on_command(f'{PREFIX}搜战队', block=True, priority=1)
BF1_PLAA = on_command(f'{PREFIX}查战队成员', aliases={f'{PREFIX}查成员'}, block=True, priority=1)
BF_STATUS = on_command(f'{PREFIX}bf status', block=True, priority=1)
BF1_STATUS = on_command(f'{PREFIX}bf1 status', aliases={f'{PREFIX}战地1', f'{PREFIX}status', f'{PREFIX}bf1'}, block=True, priority=1)
BF1_MODE= on_command(f'{PREFIX}bf1 mode', block=True, priority=1)
BF1_MAP= on_command(f'{PREFIX}bf1 map', block=True, priority=1)
BF1_INFO= on_command(f'{PREFIX}info', block=True, priority=1)
BF1_GAMEID_INFO= on_command(f'{PREFIX}gameid', block=True, priority=1)
BF1_EX= on_command(f'{PREFIX}交换', block=True, priority=1)
BF1_DRAW= on_command(f'{PREFIX}draw', block=True, priority=1)
BF1_ADMINDRAW= on_command(f'{PREFIX}admindraw', block=True, priority=1)
BF1_FADMIN = on_command(f'{PREFIX}fadmin', aliases={f'{PREFIX}查服管'}, priority=1)
BF1_F_RET_TXT = on_command(f'{PREFIX}printtextf', aliases={f'{PREFIX}搜服名'}, block=True, priority=1)

#stat
BF1_BIND_PID = on_command(f'{PREFIX}bind', aliases={f'{PREFIX}绑定', f'{PREFIX}绑id'}, block=True, priority=1)
BF1_PID_INFO= on_command(f'{PREFIX}pid', block=True, priority=1)
BF1_SA= on_command(f'{PREFIX}查', block=True, priority=1)
BF1_TYC= on_command(f'{PREFIX}tyc', aliases={f'{PREFIX}天眼查'}, block=True, priority=1)

bf1_wp_parser = ArgumentParser('BF1_WP', formatter_class=RawTextHelpFormatter)
bf1_wp_parser.add_argument('raw_args', metavar='[类型] [EAID] [?行?列]', nargs='*')
bf1_wp_parser.add_argument('-n', '--name', dest='search', default=None, required=False)
BF1_WP= on_shell_command(cmd=f'{PREFIX}武器', 
                         parser=bf1_wp_parser,
                         aliases={f'{PREFIX}w', f'{PREFIX}wp', f'{PREFIX}weapon'}, 
                         block=True, priority=1)

BF1_S= on_command(f'{PREFIX}s', aliases={f'{PREFIX}stat', f'{PREFIX}战绩', f'{PREFIX}查询',f'{PREFIX}生涯'}, block=True, priority=1)
# BF1_R= on_command(f'{PREFIX}r', aliases={f'{PREFIX}对局'}, block=True, priority=1)
# BF1_RE= on_command(f'{PREFIX}最近', block=True, priority=1)
BF1_R= on_command(f'{PREFIX}rrrrrrrrrrrrr', block=True, priority=1)
BF1_RE= on_command(f'{PREFIX}最近', aliases={f'{PREFIX}对局', f'{PREFIX}r'}, block=True, priority=1)
BF1_RANK= on_command(f'{PREFIX}排名', block=True, priority=1)

#serverbind
BF1_INIT = on_command(f'{PREFIX}init', block=True, priority=1, permission=SUPERUSER)
BF1_INIT2 = on_command(f'{PREFIX}sudoinit', block=True, priority=1, permission=SUPERUSER)
BF1_BIND = on_command(f'{PREFIX}绑服', block=True, priority=1, permission=SUPERUSER)
BF1_BIND2 = on_command(f'{PREFIX}管理绑服', block=True, priority=1, permission=SUPERUSER)
BF1_REBIND = on_command(f'{PREFIX}改绑', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_ADDBIND = on_command(f'{PREFIX}添加服别名', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_UNBIND = on_command(f'{PREFIX}解绑',block=True, priority=1, permission=SUPERUSER)
BF1_RMSERVER = on_command(f'{PREFIX}删服',block=True, priority=1, permission=SUPERUSER)
BF1_RMGROUP = on_command(f'{PREFIX}删群', block=True, priority=1, permission=SUPERUSER)
BF1_ADDADMIN = on_command(f'{PREFIX}addadmin', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_DELADMIN = on_command(f'{PREFIX}deladmin', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
BF1_ADMINLIST = on_command(f'{PREFIX}adminlist', aliases={f'{PREFIX}管理列表'}, block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)

############## rsp ################
BF1_ADDBF1ACCOUNT = on_command(f'{PREFIX}bfaccount', block=True, priority=1, permission=SUPERUSER)
BF1_F= on_command(f'{PREFIX}f', block=True, priority=1)
BF1_CHOOSELEVEL = on_command(f'{PREFIX}map', block=True, priority=1)
BF1_MOVE = on_command(f'{PREFIX}move', block=True, priority=1)
BF1_KICK = on_command(f'{PREFIX}k', aliases={f'{PREFIX}kick', f'{PREFIX}踢出'}, block=True, priority=1)
BF1_KICKALL = on_command(f'{PREFIX}kickall', aliases={f'{PREFIX}炸服', f'{PREFIX}清服'}, block=True, priority=1)

BF1_BAN = on_command(f'{PREFIX}ban', block=True, priority=1)
BF1_BANALL = on_command(f'{PREFIX}banall',aliases={f'{PREFIX}bana', f'{PREFIX}ba'}, block=True, priority=1)
BF1_UNBAN = on_command(f'{PREFIX}unban', block=True, priority=1)
BF1_UNBANALL = on_command(f'{PREFIX}unbana',aliases={f'{PREFIX}unbanall', f'{PREFIX}uba'}, block=True, priority=1)
BF1_VBAN = on_command(f'{PREFIX}vban', aliases={f'{PREFIX}vb'}, block=True, priority=1)
BF1_VBANALL = on_command(f'{PREFIX}vbana',aliases={f'{PREFIX}vbanall', f'{PREFIX}vba'}, block=True, priority=1)
BF1_UNVBAN = on_command(f'{PREFIX}unvban', aliases={f'{PREFIX}uvb',f'{PREFIX}uvban'} , block=True, priority=1)
BF1_UNVBANALL = on_command(f'{PREFIX}unvbana',aliases={f'{PREFIX}unvbanall', f'{PREFIX}uvba',f'{PREFIX}unvba'}, block=True, priority=1)

BF1_VIP = on_command(f'{PREFIX}vip', block=True, priority=1)
BF1_VIPLIST = on_command(f'{PREFIX}viplist', block=True, priority=1)
BF1_CHECKVIP = on_command(f'{PREFIX}checkvip', block=True, priority=1)
BF1_UNVIP = on_command(f'{PREFIX}unvip', block=True, priority=1)
BF1_VIPALL = on_command(f'{PREFIX}vipall', block=True, priority=1)
BF1_VIPGM = on_command(f'{PREFIX}vipgm', aliases={f'{PREFIX}暖服恰v'}, block=True, priority=1)

BF1_ADDWL = on_command(f'{PREFIX}addwl', aliases={f'{PREFIX}加白名单', f'{PREFIX}加白', f'{PREFIX}上白'}, block=True, priority=1)
BF1_RMWL = on_command(f'{PREFIX}rmwl', aliases={f'{PREFIX}下白', f'{PREFIX}下白名单'}, block=True, priority=1)
BF1_WHITELIST = on_command(f'{PREFIX}白名单', block=True, priority=1)

BF1_PL = on_command(f'{PREFIX}pl', block=True, priority=1)
BF1_INNERPL = on_command(f'{PREFIX}ipl', block=True, priority=1)
BF1_ADMINPL = on_command(f'{PREFIX}adminpl', block=True, priority=1)
BF1_PLS = on_command(f'{PREFIX}查黑队', block=True, priority=1)
BF1_PLSS = on_command(f'{PREFIX}查战队', block=True, priority=1)
BF1_UPD = on_command(f'{PREFIX}配置', block=True, priority=1)
BF1_INSPECT = on_command(f'{PREFIX}查岗', block=True, priority=1)

#grouprsp
del_user = on_notice(Rule(_is_del_user), priority=2, block=False)
bye_user = on_notice(Rule(_is_del_user), priority=1, block=False)
get_user = on_notice(Rule(_is_get_user), priority=1, block=True)
add_user = on_request(Rule(_is_add_user), priority=1, block=True)
welcome_user = on_command(f'{PREFIX}配置入群欢迎', block=True, priority=1, permission=GROUP_OWNER | SUPERUSER)
approve_req = on_command('y',rule = to_me ,aliases={'n'},priority=1, block=True)

#scheduler
BF1_SERVER_ALARM = on_command(f'{PREFIX}打开预警', block=True, priority=1)
BF1_SERVER_ALARMOFF = on_command(f'{PREFIX}关闭预警', block=True, priority=1)
BF1_SERVER_BFEAC = on_command(f'{PREFIX}打开bfeac', block=True, priority=1)
BF1_SERVER_BFBAN = on_command(f'{PREFIX}打开bfban', block=True, priority=1)
BF1_SERVER_BFEACOFF = on_command(f'{PREFIX}关闭bfeac', block=True, priority=1)
BF1_SERVER_BFBANOFF = on_command(f'{PREFIX}关闭bfban', block=True, priority=1)

#server admin logging query
BF1_SLP = on_command(f'{PREFIX}slog', aliases={f'{PREFIX}搜日志', f'{PREFIX}sl'}, block=True, priority=1)
BF1_SLF = on_command(f'{PREFIX}log', aliases={f'{PREFIX}服务器日志'}, block=True, priority=1)
BF1_SLK = on_command(f'{PREFIX}slogkey', aliases={f'{PREFIX}slk'}, block=True, priority=1)


############# Service groups registration for access control ###############
plugin_service = create_plugin_service("bf3090bot")

# Chat group management 
group_subservice = plugin_service.create_subservice('group')
approve_req_subservice = group_subservice.create_subservice('approv_req')
# approve_req_subservice.patch_matcher(add_user)
# approve_req_subservice.patch_matcher(approve_req)

add_user_subservice = group_subservice.create_subservice('add_user')
#add_user_subservice.patch_matcher(get_user)
add_user_subservice.patch_matcher(welcome_user)

bye_user_subservice = group_subservice.create_subservice('bye_user')
bye_user_subservice.patch_matcher(bye_user)

# Server logging module
adminlog_subservice = plugin_service.create_subservice('adminlog')
adminlog_subservice.patch_matcher(BF1_SLP)
adminlog_subservice.patch_matcher(BF1_SLF)
adminlog_subservice.patch_matcher(BF1_SLK)

# Alarm module
alarm_subservice = plugin_service.create_subservice('alarm')
alarm_subservice.patch_matcher(BF1_SERVER_ALARM)
alarm_subservice.patch_matcher(BF1_SERVER_ALARMOFF)

# Bot admin control and group initialization
bot_admin_initial = plugin_service.create_subservice('bot_admin_initial')
bot_admin_initial.patch_matcher(BF1_INIT)
bot_admin_initial.patch_matcher(BF1_REBIND)
bot_admin_initial.patch_matcher(BF1_ADDBIND)
bot_admin_initial.patch_matcher(BF1_ADDADMIN)
bot_admin_initial.patch_matcher(BF1_DELADMIN)

# Report module
report_subservice = plugin_service.create_subservice('report')
report_subservice.patch_matcher(BF1_REPORT)

# Player statistics query module
stat_subservice = plugin_service.create_subservice('stat')
stat_subservice.patch_matcher(BF1_SA)
stat_subservice.patch_matcher(BF1_TYC)
stat_subservice.patch_matcher(BF1_WP)
stat_subservice.patch_matcher(BF1_S)
recent_subservice = stat_subservice.create_subservice('recent')
recent_subservice.patch_matcher(BF1_R)
recent_subservice.patch_matcher(BF1_RE)
recent_subservice.patch_matcher(BF1_RANK)

# BF global info query module
info_subservice = plugin_service.create_subservice('info')
info_subservice.patch_matcher(BF1_PLA)
info_subservice.patch_matcher(BF1_PLAA)
info_subservice.patch_matcher(BF_STATUS)
info_subservice.patch_matcher(BF1_STATUS)
info_subservice.patch_matcher(BF1_MODE)
info_subservice.patch_matcher(BF1_MAP)
info_subservice.patch_matcher(BF1_INFO)
info_subservice.patch_matcher(BF1_EX)
info_subservice.patch_matcher(BF1_FADMIN)
info_subservice.patch_matcher(BF1_F_RET_TXT)

draw_subservice = info_subservice.create_subservice('draw')
draw_subservice.patch_matcher(BF1_DRAW)
draw_subservice.patch_matcher(BF1_ADMINDRAW)

# BF1 server management module
rsp_subservice = plugin_service.create_subservice('rsp')
# rsp_subservice.patch_matcher(BF1_F) # unsure about access level of .f
rsp_subservice.patch_matcher(BF1_CHOOSELEVEL)
rsp_subservice.patch_matcher(BF1_MOVE)
rsp_subservice.patch_matcher(BF1_KICK)

kickall_subservice = rsp_subservice.create_subservice('kickall')
kickall_subservice.patch_matcher(BF1_KICKALL)

ban_subservice = rsp_subservice.create_subservice('ban')
ban_subservice.patch_matcher(BF1_BAN)
ban_subservice.patch_matcher(BF1_BANALL)
ban_subservice.patch_matcher(BF1_UNBAN)
ban_subservice.patch_matcher(BF1_UNBANALL)

vban_subservice = rsp_subservice.create_subservice('vban')
vban_subservice.patch_matcher(BF1_VBAN)
vban_subservice.patch_matcher(BF1_VBANALL)
vban_subservice.patch_matcher(BF1_UNVBAN)
vban_subservice.patch_matcher(BF1_UNVBANALL)

vip_subservice = rsp_subservice.create_subservice('vip')
vip_subservice.patch_matcher(BF1_VIP)
vip_subservice.patch_matcher(BF1_VIPALL)
vip_subservice.patch_matcher(BF1_UNVIP)
vip_subservice.patch_matcher(BF1_VIPLIST)
vip_subservice.patch_matcher(BF1_CHECKVIP)
vip_gm_subservice = vip_subservice.create_subservice('vipgm')
vip_gm_subservice.patch_matcher(BF1_VIPGM)

wl_subservice = rsp_subservice.create_subservice('wl')
wl_subservice.patch_matcher(BF1_ADDWL)
wl_subservice.patch_matcher(BF1_RMWL)
wl_subservice.patch_matcher(BF1_WHITELIST)

pl_subservice = rsp_subservice.create_subservice('pl')
pl_subservice.patch_matcher(BF1_PL)
pl_subservice.patch_matcher(BF1_ADMINPL)
pl_subservice.patch_matcher(BF1_PLA)
pl_subservice.patch_matcher(BF1_PLAA)
pl_subservice.patch_matcher(BF1_INSPECT)

server_setting_subservice = rsp_subservice.create_subservice('upd')
server_setting_subservice.patch_matcher(BF1_UPD)
