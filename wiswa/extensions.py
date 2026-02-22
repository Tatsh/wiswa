"""Jinja2 extensions."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Any
import re

from jinja2.ext import Extension

from .utils.versions import get_github_release_latest_tag

if TYPE_CHECKING:
    import jinja2

__all__ = ('GithubAPIExtension', 'ToPythonExtension')


def topython(  # noqa: PLR0911
        obj: Any, *, convert_strings: bool = True, list_to_tuple: bool = False) -> Any:
    """Convert an object to a Python representation as a string."""
    data: Any
    if isinstance(obj, str):
        if convert_strings:
            if re.match(r'^true|false$', obj, re.IGNORECASE):
                return obj.lower() == 'true'
            if obj.isdigit():
                return int(obj)
        fixed = obj.replace('\\', r'\\').replace("'", r"\'")
        return f"'{fixed}'"
    if isinstance(obj, float | int | bool | Decimal | None):
        return str(obj)
    if isinstance(obj, list) and not list_to_tuple:
        data = [topython(x, list_to_tuple=list_to_tuple) for x in obj]
        return f'[{", ".join(data)}]'
    if isinstance(obj, Mapping):
        data = {
            str(k).replace('\\', r'\\').replace("'", r"\'"):
                topython(v, list_to_tuple=list_to_tuple)
            for k, v in obj.items()
        }
        val = ', '.join(f"'{k}': {v}" for k, v in data.items())
        return f'{{{val}}}'
    if isinstance(obj, tuple):
        if not obj:
            return '()'
        data = tuple(topython(x, list_to_tuple=list_to_tuple) for x in obj)
        start = f'({", ".join(data)}'
        if len(data) == 1:
            start += ','
        return f'{start})'
    if isinstance(obj, set):
        data = {topython(x, list_to_tuple=list_to_tuple) for x in obj}
        return f'{{{", ".join(sorted(data))}}}'
    if isinstance(obj, Iterable):
        data = [topython(x, list_to_tuple=list_to_tuple) for x in obj]
        if list_to_tuple:
            if not data:
                return '()'
            return f'({", ".join(data)})' if len(data) > 1 else f'({data[0]},)'
        return f'[{", ".join(data)}]'
    return obj


class ToPythonExtension(Extension):  # pragma: no cover
    """Extension class that exports filter ``topython``."""
    def __init__(self, environment: jinja2.Environment) -> None:
        super().__init__(environment)
        environment.filters['topython'] = topython


class GithubAPIExtension(Extension):  # pragma: no cover
    """Extension for Github API calls."""
    def __init__(self, environment: jinja2.Environment) -> None:
        super().__init__(environment)
        environment.globals['github_latest_action_tag'] = partial(get_github_release_latest_tag,
                                                                  actions=True,
                                                                  skip_releases=True,
                                                                  allow_suffixes=False)
