"""Jinja2 extensions."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast
import re

from jinja2.ext import Extension
from wiswa.vcs.github import ref_commit_sha

if TYPE_CHECKING:
    from niquests import AsyncSession
    import jinja2

__all__ = ('GithubAPIExtension', 'ParseMarkdownBadgeExtension', 'ShellExtension',
           'SortDictsExtension', 'ToPythonExtension')


def _topython_str(obj: str, *, convert_strings: bool) -> Any:
    if convert_strings:
        if re.match(r'^true|false$', obj, re.IGNORECASE):
            return obj.lower() == 'true'
        if obj.isdigit():
            return int(obj)
    fixed = obj.replace('\\', r'\\').replace("'", r"\'")
    return f"'{fixed}'"


def _topython(obj: Any, *, convert_strings: bool = True, list_to_tuple: bool = False) -> Any:
    """
    Convert a Python object to its string representation as Python source code.

    Parameters
    ----------
    obj : Any
        The object to convert.
    convert_strings : bool
        Whether to convert string values that look like booleans or integers.
    list_to_tuple : bool
        Whether to convert lists to tuples in the output.

    Returns
    -------
    Any
        A string containing the Python source representation of the object, or the object itself if
        it cannot be converted.
    """
    out: Any
    match obj:
        case str():
            out = _topython_str(obj, convert_strings=convert_strings)
        case _ if isinstance(obj, float | int | bool | Decimal | None):
            out = str(obj)
        case list() if not list_to_tuple:
            parts = [_topython(x, list_to_tuple=list_to_tuple) for x in obj]
            out = f'[{", ".join(parts)}]'
        case _ if isinstance(obj, Mapping):
            mapping = {
                str(k).replace('\\', r'\\').replace("'", r"\'"):
                    _topython(v, list_to_tuple=list_to_tuple)
                for k, v in obj.items()
            }
            val = ', '.join(f"'{k}': {v}" for k, v in mapping.items())
            out = f'{{{val}}}'
        case tuple():
            if not obj:
                out = '()'
            else:
                tuple_items = tuple(_topython(x, list_to_tuple=list_to_tuple) for x in obj)
                start = f'({", ".join(tuple_items)}'
                if len(tuple_items) == 1:
                    start += ','
                out = f'{start})'
        case set():
            set_items = {_topython(x, list_to_tuple=list_to_tuple) for x in obj}
            out = f'{{{", ".join(sorted(set_items))}}}'
        case _ if isinstance(obj, Iterable):
            iter_items = [_topython(x, list_to_tuple=list_to_tuple) for x in obj]
            if list_to_tuple:
                if not iter_items:
                    out = '()'
                elif len(iter_items) > 1:
                    out = f'({", ".join(iter_items)})'
                else:
                    out = f'({iter_items[0]},)'
            else:
                out = f'[{", ".join(iter_items)}]'
        case _:
            out = obj
    return out


_MD_BADGE_RE = re.compile(r'^\[!\[(.+?)]\((.+?)\)]$')
_HEREDOC_START = re.compile(r'<<-?\s*\\?[\'"]?(\w+)[\'"]?\s*$')


def _shell_indent(text: str, width: int = 4) -> str:
    prefix = ' ' * width
    lines = text.split('\n')
    result: list[str] = []
    heredoc_end: str | None = None
    for line in lines:
        if heredoc_end is not None:
            result.append(line)
            if line.strip() == heredoc_end:
                heredoc_end = None
        else:
            result.append(prefix + line if line.strip() else line)
            m = _HEREDOC_START.search(line)
            if m:
                heredoc_end = m.group(1)
    return '\n'.join(result)


def _parse_md_badge(anchor: str) -> dict[str, str]:
    m = _MD_BADGE_RE.match(anchor)
    return {'alt': m.group(1), 'image': m.group(2)} if m else {'alt': '', 'image': ''}


class ParseMarkdownBadgeExtension(Extension):
    """Extension that exports the ``parse_md_badge`` :py:class:`~jinja2.Environment` filter."""
    def __init__(self, environment: jinja2.Environment) -> None:
        super().__init__(environment)
        environment.filters['parse_md_badge'] = _parse_md_badge


def _sort_dicts(value: Iterable[Mapping[str, Any]],
                key: str,
                default: Any = 0) -> list[Mapping[str, Any]]:
    """
    Sort an iterable of mappings by *key*, falling back to *default* for entries missing the key.

    Jinja2's built-in ``sort(attribute='...')`` raises ``UndefinedError`` under
    :py:class:`~jinja2.StrictUndefined` when an entry lacks the attribute. This filter mirrors
    that API but tolerates missing keys, which is needed by templates that sort user-supplied
    dictionaries whose contract is "optional with a default" rather than "always present".

    Parameters
    ----------
    value : Iterable[Mapping[str, Any]]
        The sequence of mappings to sort.
    key : str
        The mapping key to sort by.
    default : Any
        Sort-key value used for mappings that do not contain *key*.

    Returns
    -------
    list[Mapping[str, Any]]
        A new list of the input mappings sorted by *key*.
    """
    return sorted(value, key=lambda item: item.get(key, default))


class SortDictsExtension(Extension):
    """Extension that exports the ``sort_dicts`` :py:class:`~jinja2.Environment` filter."""
    def __init__(self, environment: jinja2.Environment) -> None:
        super().__init__(environment)
        environment.filters['sort_dicts'] = _sort_dicts


class ShellExtension(Extension):
    """Extension that exports the ``shell_indent`` :py:class:`~jinja2.Environment` filter."""
    def __init__(self, environment: jinja2.Environment) -> None:
        super().__init__(environment)
        environment.filters['shell_indent'] = _shell_indent


class ToPythonExtension(Extension):
    """Extension that exports the ``topython`` :py:class:`~jinja2.Environment` filter."""
    def __init__(self, environment: jinja2.Environment) -> None:
        super().__init__(environment)
        environment.filters['topython'] = _topython


class GithubAPIExtension(Extension):
    """Extension exporting ``github_latest_action_tag`` to :py:class:`~jinja2.Environment`."""
    def __init__(self, environment: jinja2.Environment) -> None:
        super().__init__(environment)
        # Local import: ``wiswa.utils`` package init imports ``templating``, which only imports
        # this module from inside ``_template_env``, so this module must finish loading first.
        from wiswa.tool.utils.versions import get_github_release_latest_tag  # noqa: PLC0415

        globs = cast('dict[str, Any]', environment.globals)

        async def _github_latest_action_tag(owner: str, repo: str) -> str:
            session = cast('AsyncSession | None', globs.get('_http_session'))
            if session is None:
                msg = 'No HTTP session available for GitHub API calls.'
                raise RuntimeError(msg)
            return await get_github_release_latest_tag(session,
                                                       owner,
                                                       repo,
                                                       skip_releases=True,
                                                       allow_suffixes=False)

        async def _github_latest_action_sha(owner: str, repo: str) -> str:
            session = cast('AsyncSession | None', globs.get('_http_session'))
            if session is None:
                msg = 'No HTTP session available for GitHub API calls.'
                raise RuntimeError(msg)
            tag = await get_github_release_latest_tag(session,
                                                      owner,
                                                      repo,
                                                      skip_releases=True,
                                                      allow_suffixes=False)
            return await ref_commit_sha(session, owner, repo, tag)

        globs['github_latest_action_tag'] = _github_latest_action_tag
        globs['github_latest_action_sha'] = _github_latest_action_sha
