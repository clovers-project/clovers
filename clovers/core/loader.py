from pathlib import Path
from importlib import import_module
from functools import partial
from collections.abc import Iterable
from ..logger import logger


def import_path(path: str | Path):
    """将路径转换成导入名

    Args:
        path (str | Path): 路径

    Returns:
        str: 模块导入名
    """
    path = Path(path) if isinstance(path, str) else path
    return ".".join(path.resolve().relative_to(Path().resolve()).parts)


def import_name(name: str | Path, is_path: bool):
    """获取模块导入名

    Args:
        name (str | Path): 模块名或模块路径
        is_path (bool): 是否为模块路径

    Returns:
        str: 模块导入名
    """

    if is_path or isinstance(name, Path):
        return import_path(name)
    else:
        return name.replace("-", "_")


def list_modules(path: str | Path) -> list[str]:
    """获取路径下的模块名

    Args:
        path (str | Path): 路径

    Returns:
        list[str]: 模块名列表
    """
    path = Path(path) if isinstance(path, str) else path
    namespace = ".".join(path.resolve().relative_to(Path().resolve()).parts)
    namelist = []
    for x in path.iterdir():
        if x.is_file():
            if not x.name.endswith(".py"):
                continue
            name = x.stem
        else:
            name = x.name
        if name.startswith("_"):
            continue
        namelist.append(f"{namespace}.{name}")
    return namelist


class LoadingError(Exception): ...


class ModuleLoader[T]:
    def __init__(self, _attrs: list[str], _type: type[T]):
        self._attrs = _attrs
        self._type = _type

    @staticmethod
    def load(package: str, _attrs: list[str], _type: type[T]) -> T:
        try:
            module = import_module(package)
        except ImportError as e:
            raise LoadingError(f'Failed to import module "{package}": {e}') from e
        except SyntaxError as e:
            raise LoadingError(f'Module "{package}" contains a syntax error') from e
        attr_name = next((x for x in _attrs if hasattr(module, x)), None)
        if attr_name is None:
            raise LoadingError(f'Module "{package}" does not define any of the required attributes: {", ".join(_attrs)}')
        attr = getattr(module, attr_name)
        if not isinstance(attr, _type):
            expected_type = _type.__name__ if hasattr(_type, "__name__") else str(_type)
            raise LoadingError(f'Attribute "{attr_name}" in "{package}" is a {type(attr).__name__}, ' f"but expected type {expected_type}")
        return attr

    def _load(self, package: str):
        try:
            return self.load(package, self._attrs, self._type)
        except LoadingError as e:
            logger.warning(f'Failed to load "{package}": {e}')

    def load_from_list(self, import_list: Iterable[str]):
        """从包名列表加载"""
        for package in import_list:
            self._load(package.replace("-", "_"))

    def load_from_dirs(self, import_dirs: Iterable[str]):
        """从本地目录列表加载"""
        for import_dir in import_dirs:
            dir = Path(import_dir)
            if not dir.exists():
                continue
            self.load_from_list(list_modules(dir))
