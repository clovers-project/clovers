import importlib
from pathlib import Path


def load_module(name: str, attr: str | None = None):
    module = importlib.import_module(name)
    if attr:
        return getattr(module, attr, None)
    return module


def list_modules(path: str | Path) -> list[str]:
    path = Path(path) if isinstance(path, str) else path
    import_path = ".".join(path.relative_to(Path()).parts)
    namelist = []
    for x in path.iterdir():
        name = x.stem if x.is_file() and x.name.endswith(".py") else x.name
        if name.startswith("_"):
            continue
        namelist.append(f"{import_path}.{name}")
    return namelist
