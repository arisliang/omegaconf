import copy
import itertools
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple, Union

from ._utils import _re_parent, isint
from .base import Container, Node
from .basecontainer import BaseContainer
from .errors import ReadonlyConfigError, UnsupportedKeyType, UnsupportedValueType
from .nodes import AnyNode, ValueNode


class ListConfig(BaseContainer):
    def __init__(
        self,
        content: Union[List[Any], Tuple[Any, ...]],
        parent: Optional[Container] = None,
        element_type: type = Any,  # type: ignore
    ) -> None:
        super().__init__(parent=parent, element_type=element_type)
        self.__dict__["content"] = []
        assert isinstance(content, (list, tuple))
        for item in content:
            self.append(item)

    def __deepcopy__(self, memo: Dict[int, Any] = {}) -> "ListConfig":
        res = ListConfig(content=[])
        res.__dict__["content"] = copy.deepcopy(self.__dict__["content"], memo=memo)
        res.__dict__["flags"] = copy.deepcopy(self.__dict__["flags"], memo=memo)
        res.__dict__["_element_type"] = copy.deepcopy(
            self.__dict__["_element_type"], memo=memo
        )
        _re_parent(res)
        return res

    def __getattr__(self, key: str) -> Any:
        if isinstance(key, str) and isint(key):
            return self.__getitem__(int(key))
        else:
            raise AttributeError()

    # hide content while inspecting in debugger
    def __dir__(self) -> Iterable[str]:
        return [str(x) for x in range(0, len(self))]

    def __len__(self) -> int:
        return len(self.content)

    def __getitem__(self, index: int) -> Any:
        assert isinstance(index, (int, slice))
        if isinstance(index, slice):
            result = []
            for slice_idx in itertools.islice(
                range(0, len(self)), index.start, index.stop, index.step
            ):
                val = self._resolve_with_default(
                    key=slice_idx, value=self.content[slice_idx], default_value=None
                )
                result.append(val)
            return result
        else:
            return self._resolve_with_default(
                key=index, value=self.content[index], default_value=None
            )

    def _set_at_index(self, index: int, value: Any) -> None:
        if not isinstance(index, int):
            raise UnsupportedKeyType(f"Key type {type(index).__name__} is not an int")

        if self._get_flag("readonly"):
            raise ReadonlyConfigError(self.get_full_key(str(index)))

        if isinstance(value, BaseContainer):
            value = copy.deepcopy(value)
            value._set_parent(self)

        try:

            self._set_item_impl(index, value)

        except UnsupportedValueType:
            raise UnsupportedValueType(
                "key {}: {} is not a supported type".format(
                    self.get_full_key(str(index)), type(value).__name__
                )
            )

    def __setitem__(self, index: int, value: Any) -> None:
        self._set_at_index(index, value)

    def append(self, item: Any) -> None:
        if self._get_flag("readonly"):
            raise ReadonlyConfigError(self.get_full_key(f"{len(self)}"))

        try:
            from omegaconf.omegaconf import _maybe_wrap

            self.__dict__["content"].append(
                _maybe_wrap(
                    annotated_type=self.__dict__["_element_type"],
                    value=item,
                    is_optional=True,
                    parent=self,
                )
            )
        except UnsupportedValueType:
            full_key = self.get_full_key(f"{len(self)}")
            raise UnsupportedValueType(
                f"key {full_key}: {type(item).__name__} is not a supported type"
            )

    def insert(self, index: int, item: Any) -> None:
        if self._get_flag("readonly"):
            raise ReadonlyConfigError(self.get_full_key(str(index)))
        try:
            self.content.insert(index, AnyNode(None))
            self._set_at_index(index, item)
        except Exception:
            del self.__dict__["content"][index]
            raise

    def extend(self, lst: Union[List[Any], Tuple[Any, ...], "ListConfig"]) -> None:
        assert isinstance(lst, (tuple, list, ListConfig))
        for x in lst:
            self.append(x)

    def remove(self, x: Any) -> None:
        del self[self.index(x)]

    def clear(self) -> None:
        del self[:]

    def index(self, x: Any) -> int:
        found_idx = -1
        for idx, item in enumerate(self):
            if x == item:
                found_idx = idx
                break
        if found_idx != -1:
            return found_idx
        else:
            raise ValueError("Item not found in ListConfig")

    def count(self, x: Any) -> int:
        c = 0
        for item in self:
            if item == x:
                c = c + 1
        return c

    def copy(self) -> "ListConfig":
        return copy.copy(self)

    def get_node(self, index: int) -> Node:
        assert type(index) == int
        return self.__dict__["content"][index]  # type: ignore

    def get(self, index: int, default_value: Any = None) -> Any:
        assert type(index) == int
        return self._resolve_with_default(
            key=index, value=self.content[index], default_value=default_value
        )

    def pop(self, index: int = -1) -> Any:
        if self._get_flag("readonly"):
            raise ReadonlyConfigError(
                self.get_full_key(str(index if index != -1 else ""))
            )
        return self._resolve_with_default(
            key=index, value=self.content.pop(index), default_value=None
        )

    def sort(
        self, key: Optional[Callable[[Any], Any]] = None, reverse: bool = False
    ) -> None:
        if self._get_flag("readonly"):
            raise ReadonlyConfigError()

        if key is None:

            def key1(x: Any) -> Any:
                return x.value()

        else:

            def key1(x: Any) -> Any:
                return key(x.value())  # type: ignore

        self.content.sort(key=key1, reverse=reverse)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, list):
            return BaseContainer._list_eq(self, ListConfig(other))
        if isinstance(other, ListConfig):
            return BaseContainer._list_eq(self, other)
        return NotImplemented

    def __ne__(self, other: Any) -> bool:
        x = self.__eq__(other)
        if x is not NotImplemented:
            return not x
        return NotImplemented

    def __hash__(self) -> int:
        return hash(str(self))

    def __iter__(self) -> Iterator[Any]:
        class MyItems(Iterator[Any]):
            def __init__(self, lst: List[Any]) -> None:
                self.lst = lst
                self.iterator = iter(lst)

            def __next__(self) -> Any:
                return self.next()

            def next(self) -> Any:
                v = next(self.iterator)
                if isinstance(v, ValueNode):
                    v = v.value()
                return v

        return MyItems(self.content)

    def __add__(self, o: List[Any]) -> "ListConfig":
        # res is sharing this list's parent to allow interpolation to work as expected
        res = ListConfig(parent=self._get_parent(), content=[])
        res.extend(self)
        res.extend(o)
        return res
