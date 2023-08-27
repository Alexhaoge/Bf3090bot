## bf1追加指令 ！！！重要！！！服务器改行动后请重新绑服！！！

| 命令                                                       | 作用                                                                         | 备注                                                      |
| --------------------------------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------- |
| `{p}bf status`               | 查看bf系列游玩人数                                                                                | 使用. bf1查询战地1当前游玩                                                    |
| `{p}bf1 mode`                 | 查看不同模式的人数                                                                           |                                                                              |
| `{p}bf1 map`                  | 查看地图热度前十                                                                             |                                                                              |
| `{p}交换`     | 查看交换信息                                                                                               |                                                  |
| `{p}map <服名> <地图>`     | 切图                                                                                              | 可以在结尾添加模式名称                                                 |
| `{p}f <服务器>`                  | 查看服务器信息                                | 可以输入 .info <服务器>查询详细信息                                                                           |
| `{p}bind <id>`               | 绑定玩家id                               |                                                    |
| `{p}查a/b/o/v <玩家名称>`               | 查看玩家相关信息                               | a:管理 b:ban o:服主 v:vip                                                    |
| `{p}s <玩家名称>`               | 查看战绩信息                               |                                                  |
| `{p}tyc <玩家名称>`               | 查看天眼查信息                               |                                                  |
| `{p}w <类别> <玩家名称>`               | 查看武器信息                         |  可以在结尾添加行列参数，比如：.w 7行5列                                          |
| `{p}r <玩家名称>`               | 查看对局信息                               | 查最近双k请输入.最近，查对局请输入.r或.对局                                                 |
| `{p}move <服名> <玩家名称>` | 换边                                                                                               |             |
| `{p}ban <服名> <玩家名称> <理由>`  | 上ban                                                                                         | 缺点：没连接vban数据库  |
| `{p}unban <服名> <玩家名称>`| 解除ban                                               |                                                                   |
| `{p}vip <服名> <玩家名称> <时间>`     | 上vip | 缺点：bot之间数据库不通用
| `{p}unvip <服名> <玩家名称>`| 解除vip                                               |                                                                  |
| `{p}k <服名> <玩家名称> <理由>`| 踢人                                               | 可以发送.kickall [服名] [理由]或.炸服进行清服                                                                  |
| `{p}pl <服名>`| 查询玩家列表                                               | 1.可以回复 .k [序号] [理由] 或 .k [rank/kd/kp>数<br />值]或.k all [理由]进行联动踢人。<br />2.可以回复.s/.w/.tyc [序号]进行单次战绩查询。 <br />3.可以回复.vip [序号] [天数]进行单次vip添加。<br />4.可以回复.move [序号]进行批量挪人。 <br />5.可以回复.ban [序号] [理由]进行单次ban人。                                                              |
| `{p}打开/关闭预警`              | 开启/关闭人数监控                       | 1分钟1次，15分钟最多报3次                                                   |

bot每次重启默认预警状态为关闭。如果发现预警掉了重新输入此指令即可

alias [别名]=[指令名称]: 添加别名; alias [别名]: 查看别名; alias -p: 查看所有别名; 

unalias [别名]: 删除别名; unalias -a: 删除所有别名

第一次使用需要群主发送：

（1）. addadmin <管理QQ> 添加管理，可以使用服管指令的qq；. deladmin <管理QQ> 删除管理

（2）服管功能需要添加bot服管号为服务器管理。通过. bot或. 管服号查看服管号eaid

如果没回消息可能是HTTP ERROR网络异常，多试几次，还不回就是风控了，如果确定没风控请直接联系我。