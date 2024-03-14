from io import BytesIO
from clovers_core.plugin import Plugin, Result
from clovers_core.config import config as clovers_config
from clovers_leafgame_core.clovers import Event
from .manager import Manager
from .config import Config

config_key = __package__

config = Config.parse_obj(clovers_config.get(config_key, {}))
"""主配置类"""

clovers_config[config_key] = config.dict()
plugin = Plugin(
    build_event=lambda event: Event(event),
    build_result=lambda result: (
        Result("text", result) if isinstance(result, str) else Result("image", result) if isinstance(result, BytesIO) else result
    ),
)
"""小游戏插件实例"""

manager = Manager(config.main_path)
"""小游戏管理器实例"""

from .module import *

__plugin__ = plugin


"""
恶魔轮盘：

一把只有一发空仓的左轮枪。你可以对自己开一枪，如果你足够幸运躲过一劫，那么你的名下所有账户的金币与股票净值都将翻10倍。
如果你不幸中弹,你将会在这个世界上消失。

绯红迷雾之书：

把你的个人数据回溯到到任意时间节点。
可回溯的时间节点有多少取决于服务器备份设置
    --机器人bug研究中心

手中的左轮没有消失，你的眼前出现了一张纸条。
为了庆祝你活了下来,我们还要送你一份礼物。
你手中的左轮已经重新装好了子弹。
你可以把它扔在仓库里。
但是如果你想继续开枪的话，那就来吧。
*你获得了 【恶魔轮盘】*1

"""
