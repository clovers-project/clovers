"""clovers 0.4"""

__version__ = "0.4"
__description__ = "高度自定义的聊天平台 Python 异步机器人指令-响应插件框架"

from .core import Result, Event
from .core import BaseHandle, Handle, TempHandle
from .core import Plugin, Adapter, Leaf, Client
from .core import EventProtocol


class LeafClient(Leaf, Client):
    """
    单适配器响应客户端
    """


__all__ = [
    "Result",
    "Event",
    "BaseHandle",
    "Handle",
    "TempHandle",
    "Plugin",
    "Adapter",
    "Leaf",
    "Client",
    "LeafClient",
    "EventProtocol",
]
