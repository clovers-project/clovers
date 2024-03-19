from .main import plugin as __plugin__
from pathlib import Path
from clovers_core.plugin import PluginLoader

for x in (Path(__file__).parent / "modules").iterdir():
    name = x.stem if x.is_file() and x.name.endswith(".py") else x.name
    PluginLoader.load(f"{__package__}.modules.{name}")


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
