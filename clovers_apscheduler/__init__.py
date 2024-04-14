from apscheduler.schedulers.asyncio import AsyncIOScheduler
from clovers.core.config import config as clovers_config
from clovers.core.plugin import Plugin
from .config import Config


config_key = __package__
config_data = Config.parse_obj(clovers_config.get(config_key, {}))
clovers_config[config_key] = config_data.dict()

plugin = Plugin()
scheduler = AsyncIOScheduler()
scheduler.configure(**config_data.scheduler_config)


@plugin.startup
async def _():
    if scheduler.running:
        return
    scheduler.start()


@plugin.shutdown
async def _():
    if scheduler.running:
        return
    scheduler.shutdown()


__plugin__ = plugin
