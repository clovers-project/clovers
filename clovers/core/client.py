import asyncio
from abc import ABC, abstractmethod
from .core import CloversCore


class ClientCore(ABC):

    def __init__(self):
        self.tasks = set()

    def function(self, func: CloversCore) -> CloversCore:
        self.tasks.add(task := asyncio.create_task(self.response(recv=recv, send=send, ws=ws, client=self)))
        task.add_done_callback(self.tasks.discard)

    @abstractmethod
    async def startup(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        raise NotImplementedError

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()
        if not self.tasks:
            return
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


class SingleCoreClient:
    """单核心客户端

    Attributes:
        core (CloversCore): 核心
    """

    def __init__(self, core: CloversCore):
        self.core = core


class MultiCoreClient:
    """多核心客户端

    Attributes:
        cores (list[CloversCore]): 核心列表
    """

    def __init__(self, cores: list[CloversCore]):
        self.cores = cores
