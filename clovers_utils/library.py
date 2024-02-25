class Library[K, V]:
    """多键字典"""

    def __init__(self, data: list[tuple[K, set[K], V]] = None) -> None:
        self._key_data: dict[K, V] = {}
        self._index_key: dict[K, K] = {}
        self._key_indices: dict[K, set[K]] = {}
        if data:
            for key, value in data:
                self.set_item(key, value)

    def __getitem__(self, index: K) -> V:
        return self._key_data.get(index) or self._key_data[self._index_key[index]]

    def __setitem__(self, index: K, data: V):
        key = self._index_key.get(index, index)
        self._key_data[key] = data

    def set_item(self, key: K, indices: set[K], data: V):
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

    def update(self, data):
        return self._key_data.update(data)
