from pathlib import Path


def import_path(path: str | Path):
    """将路径转换成导入名

    Args:
        path (str | Path): 路径

    Returns:
        str: 模块导入名
    """
    path = Path(path) if isinstance(path, str) else path
    return ".".join(path.resolve().relative_to(Path().resolve()).parts)


def import_name(name: str | Path, is_path):
    """获取模块导入名

    Args:
        name (str | Path): 模块名或模块路径
        is_path (bool): 是否为模块路径.

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
        name = x.stem if x.is_file() and x.name.endswith(".py") else x.name
        if name.startswith("_"):
            continue
        namelist.append(f"{namespace}.{name}")
    return namelist
