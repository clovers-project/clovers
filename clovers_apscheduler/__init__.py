from apscheduler.schedulers.asyncio import AsyncIOScheduler
from clovers_core.config import config as clovers_config
from clovers_core.plugin import Plugin
from .config import Config


config_key = __package__
config = Config.parse_obj(clovers_config.get(config_key, {}))
clovers_config[config_key] = config.dict()
clovers_config.save()

plugin = Plugin()
scheduler = AsyncIOScheduler()
scheduler.configure(**config.scheduler_config)


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
