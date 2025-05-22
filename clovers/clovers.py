import abc
import time
import asyncio
from pathlib import Path
from importlib import import_module
from .utils import import_path
from clovers.core import BaseHandle
from .core import Event, Adapter, CloversCore
from .logger import logger


class Leaf(CloversCore):
    """clovers 响应处理器基类
    Attributes:
        adapter (Adapter): 对接响应的适配器
    """

    adapter: Adapter

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.adapter = Adapter(name)

    def load_adapter(self, name: str | Path, is_path=False):
        """加载 clovers 适配器

        会把目标适配器的方法注册到 self.adapter 中，如有适配器中已有同名方法则忽略

        Args:
            name (str | Path): 适配器的包名或路径
            is_path (bool, optional): 是否为路径
        """

        if is_path or isinstance(name, Path):
            import_name = import_path(name)
        else:
            import_name = name
        logger.info(f"[loading adapter][{self.name}] {import_name} ...")
        try:
            adapter = getattr(import_module(import_name), "__adapter__", None)
            assert isinstance(adapter, Adapter)
        except Exception as e:
            logger.exception(f"adapter {import_name} load failed", exc_info=e)
            return
        self.adapter.remix(adapter)

    def handles_filter(self, handle: BaseHandle) -> bool:
        if method_miss := handle.properties - self.adapter.properties_lib.keys():
            logger.warning(f"Handle ignored: Adapter({self.adapter.name}) is missing required methods: {method_miss}")
            debug_info = {"handle": handle, "method_miss": method_miss}
            logger.debug(repr(debug_info), extra=debug_info)
            return False
        else:
            return True

    async def response_message(self, message: str, /, **extra):
        """响应消息

        Args:
            message (str): 消息内容
            **extra: 额外的参数

        Returns:
            int: 响应数量
        """
        if not message:
            return 0
        count = 0
        temp_event = None
        properties = {}
        calls = self.adapter.calls_lib
        for temp_handles, handles_list in self._handles_queue:
            if temp_handles:
                now = time.time()
                alive_handles = [handle for handle in temp_handles if handle.expiration > now]
                temp_handles.clear()
                if alive_handles:
                    temp_event = temp_event or Event(message, [], properties, calls, extra)
                    temp_handles.extend(alive_handles)
                    blocks = await asyncio.gather(*(self.adapter.response(handle, temp_event, extra) for handle in alive_handles))
                    blocks = [block for block in blocks if block is not None]
                    if blocks:
                        blk_p, blk_h = zip(*blocks)
                        count += len(blocks)
                        if any(blk_p):
                            return count
                        elif any(blk_h):
                            continue
            delay_fuse = False
            for handles in handles_list:
                tasklist = (
                    self.adapter.response(handle, Event(message, args, properties, calls, extra), extra)
                    for handle in handles
                    if (args := handle.match(message)) is not None
                )
                blocks = await asyncio.gather(*tasklist)
                blocks = [block for block in blocks if block]
                if blocks:
                    count += len(blocks)
                    if (True, True) in blocks:
                        return count
                    elif (False, True) in blocks:
                        break
                    elif not delay_fuse and (True, False) in blocks:
                        delay_fuse = True
            if delay_fuse:
                break
        return count

    @abc.abstractmethod
    def extract_message(self, **extra) -> str | None:
        """提取消息

        根据传入的事件参数提取消息

        Args:
            **extra: 额外的参数

        Returns:
            str | None: 消息
        """

        raise NotImplementedError

    async def response(self, **extra) -> int:
        """响应事件

        根据传入的事件参数响应事件。

        如果提取到了消息，则触发消息响应，如果提取到了事件，则触发事件响应。

        否则不会触发响应。

        Args:
            **extra: 额外的参数

        Returns:
            int: 响应数量
        """

        if (message := self.extract_message(**extra)) is not None:
            return await self.response_message(message, **extra)
        else:
            return 0


class Client(CloversCore):
    """clovers 客户端基类

    Attributes:
        running (bool): 客户端运行状态
    """

    def __init__(self) -> None:
        super().__init__()
        self.running = False

    async def startup(self):
        """启动客户端

        如不在 async with 上下文中则要手动调用 startup() 方法，
        """
        if self.running:
            raise RuntimeError("Client is already running")
        self.initialize_plugins()
        tasklist = (asyncio.create_task(task()) for plugin in self.plugins for task in plugin.startup_tasklist)
        await asyncio.gather(*tasklist)
        self.running = True

    async def shutdown(self):
        """关闭客户端

        如不在 async with 上下文中则要手动调用 shutdown() 方法，
        """
        if not self.running:
            raise RuntimeError("Client is not running")
        tasklist = (asyncio.create_task(task()) for plugin in self.plugins for task in plugin.shutdown_tasklist)
        await asyncio.gather(*tasklist)
        self.running = False

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    @abc.abstractmethod
    async def run(self) -> None:
        """
        运行 Clovers Client ，需要在子类中实现。

        .. code-block:: python3
            '''
            async with self:
                while self.running:
                    pass
            '''
        """
        raise NotImplementedError


class LeafClient(Leaf, Client):
    """
    单适配器响应客户端
    """
