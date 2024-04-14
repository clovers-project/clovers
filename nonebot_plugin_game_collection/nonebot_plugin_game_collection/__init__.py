from clovers.core.plugin import PluginLoader
from nonebot_plugin_clovers import adapter

loader = PluginLoader(plugins_list=["clovers_leafgame"])
plugin = loader.plugins[0]
if plugin not in adapter.plugins:
    adapter.plugins.append(plugin)
