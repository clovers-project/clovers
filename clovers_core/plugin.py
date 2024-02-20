import sys
import importlib
import importlib.util
import importlib.machinery
import re
from pathlib import Path
from typing import Any
from collections.abc import Callable, Coroutine


class PluginError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class Result:
    def __init__(self, send_method: str, data) -> None:
        self.send_method = send_method
        self.data = data


class Event:
    def __init__(
        self,
        raw_command: str,
        args: list[str] = [],
    ):
        self.raw_command = raw_command
        self.args = args
        self.kwargs = {}


class Handle:
    func: Callable[..., Coroutine]

    def __init__(
        self,
        commands: set[str] | re.Pattern,
        extra_args: list[str],
    ):
        self.commands = commands
        self.extra_args = extra_args

    async def __call__(self, event: Event) -> Result:
        return await self.func(event)


class Plugin:
    build_event: Callable = lambda e: e
    build_result: Callable = lambda r: r

    def __init__(self, name: str = "") -> None:
        self.name: str = name
        self.handles: dict[int, Handle] = {}
        self.command_dict: dict[str, set[int]] = {}
        self.regex_dict: dict[re.Pattern, set[int]] = {}
        self.got_dict: dict = {}
        self.task_list: list[Coroutine] = []

    def handle(
        self,
        commands: str | set[str] | re.Pattern,
        extra_args: list[str] | set[str] | tuple[str] = None,
    ):
        def decorator(func: Callable[..., Coroutine]):
            key = len(self.handles)
            if isinstance(commands, set):
                for command in commands:
                    self.command_dict.setdefault(command, set()).add(key)
            elif isinstance(commands, str):
                self.regex_dict.setdefault(re.compile(commands), set()).add(key)
            elif isinstance(commands, re.Pattern):
                self.regex_dict.setdefault(commands, set()).add(key)
            else:
                raise PluginError(f"指令：{commands} 类型错误：{type(commands)}")

            handle = Handle(commands, list[extra_args])

            async def wrapper(event: Event) -> Result:
                if result := await func(self.build_event(event)):
                    return self.build_result(result)

            handle.func = wrapper
            self.handles[key] = handle

        return decorator

    def task(self, func: Callable[[], Coroutine]):
        self.task_list.append(func())

    def command_check(self, command: str) -> dict[int, Event]:
        kv = {}
        if not (command_list := command.strip().split()):
            return kv
        command_start = command_list[0]
        for cmd, keys in self.command_dict.items():
            if not command_start.startswith(cmd):
                continue
            if command_start == cmd:
                args = command_list[1:]
            else:
                command_list[0] = command_list[0][len(cmd) :]
                args = command_list
            for key in keys:
                kv[key] = Event(command, args)

        return kv

    def regex_check(self, command: str) -> dict[int, Event]:
        kv = {}
        for pattern, keys in self.regex_dict.items():
            if re.match(pattern, command):
                for key in keys:
                    kv[key] = Event(command)
        return kv

    def __call__(self, command: str) -> dict[int, Event]:
        kv = {}
        kv.update(self.command_check(command))
        kv.update(self.regex_check(command))
        return kv


class PluginLoader:
    def __init__(self, plugins_path: Path, plugins_list: list) -> None:
        self.plugins_path: Path = plugins_path
        self.plugins_list: list = plugins_list

    @staticmethod
    def load(name: str) -> Plugin:
        print(f"【loading plugin】 {name} ...")
        return importlib.import_module(name).__plugin__

    def load_plugins_from_path(self):
        plugins_raw_path = str(self.plugins_path)
        sys.path.insert(0, plugins_raw_path)
        plugins = []
        for x in self.plugins_path.iterdir():
            name = x.stem if x.is_file() and x.name.endswith(".py") else x.name
            if name.startswith("_"):
                continue
            plugins.append(self.load(name))
        sys.path = [path for path in sys.path if path != plugins_raw_path]
        return [plugin for plugin in plugins if plugin]

    def load_plugins_from_list(self):
        plugins = []
        for x in self.plugins_list:
            plugins.append(self.load(x))
        return [plugin for plugin in plugins if plugin]

    def load_plugins(self) -> list[Plugin]:
        return self.load_plugins_from_list() + self.load_plugins_from_path()
