from collections.abc import Iterable
from typing import overload


class Library[K, V]:
    """多键字典"""

    @overload
    def __init__(self, data: Iterable[tuple[K, Iterable[K], V]]) -> None: ...
    @overload
    def __init__(self) -> None: ...

    def __init__(self, data=None) -> None:
        self._key_data: dict[K, V] = {}
        self._index_key: dict[K, K] = {}
        self._key_indices: dict[K, set[K]] = {}
        if not data:
            return
        for key, alias, value in data:
            self.set_item(key, alias, value)

    def __getitem__(self, index: K) -> V:
        return self._key_data.get(index) or self._key_data[self._index_key[index]]

    def __setitem__(self, index: K, data: V):
        key = self._index_key.get(index, index)
        self._key_data[key] = data

    def __contains__(self, key):
        return key in self._key_indices or key in self._index_key

    def __iter__(self):
        return iter((key, self._key_indices[key], value) for key, value in self._key_data.items())

    def keys(self):
        return self._key_data.keys()

    def values(self):
        return self._key_data.values()

    def items(self):
        return self._key_data.items()

    def set_item(self, key: K, indices: Iterable[K], data: V):
        if old_indices := self._key_indices.get(key):
            for i in old_indices:
                del self._index_key[i]
        self._key_data[key] = data
        indices = set(indices)
        self._key_indices[key] = indices
        for i in indices:
            self._index_key[i] = key

    def __delitem__(self, index: K):
        if index in self._key_data:
            del self._key_data[index]
            if indices := self._key_indices.get(index):
                for i in indices:
                    del self._index_key[i]
                del self._key_indices[index]
            return
        if key := self._index_key[index]:
            del self._index_key[index]
            self._key_indices[key].discard(index)
            return
        raise KeyError(index)

    def update(self, data: "Library[K, V]"):
        for key, indices, value in data:
            self.set_item(key, indices, value)

    @overload
    def get(self, index: K) -> V | None: ...
    @overload
    def get(self, index: K, default: V) -> V: ...

    def get(self, index: K, default=None):
        if key := self._index_key.get(index):
            return self._key_data[key]
        return self._key_data.get(index, default)

    def setdefault(self, index: K, default: V):
        if key := self._index_key.get(index):
            return self._key_data[key]
        return self._key_data.setdefault(index, default)
