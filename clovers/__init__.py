"""clovers 0.5"""

__version__ = "0.5"
__description__ = "高度自定义的聊天平台 Python 异步机器人指令-响应插件框架"

from .base import Result, Event, Adapter, EventType
from .plugin import Handle, TempHandle, Plugin
from .core import AdapterCore, PluginLoader, CloversCore, CloversMultCore


__all__ = [
    "EventType",
    "Result",
    "Event",
    "Handle",
    "TempHandle",
    "Plugin",
    "Adapter",
    "AdapterCore",
    "PluginLoader",
    "CloversCore",
    "CloversMultCore",
]
