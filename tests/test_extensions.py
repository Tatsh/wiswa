"""Tests for Jinja2 extensions."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from wiswa.extensions import ShellExtension, ToPythonExtension, topython
import jinja2
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    ('obj', 'expected'),
    [
        ('true', True),
        ('false', False),
        ('TRUE', True),
        ('FALSE', False),
        ('123', 123),
        ('hello', "'hello'"),
        ("he'llo", "'he\\'llo'"),
        ('back\\slash', "'back\\\\slash'"),
        (123, '123'),
        (12.34, '12.34'),
        (True, 'True'),
        (False, 'False'),
        (None, 'None'),
        (Decimal('1.23'), '1.23'),
        ([1, 2, 3], '[1, 2, 3]'),
        ((1, 2), '(1, 2)'),
        ((1,), '(1,)'),
        ([], '[]'),
        ((), '()'),
        ({
            'a': 1,
            'b': 2
        }, "{'a': 1, 'b': 2}"),
        ({
            'a': [1, 2]
        }, "{'a': [1, 2]}"),
        ({
            'a': {
                'b': 2
            }
        }, "{'a': {'b': 2}}"),
        ({1, 2}, '{1, 2}'),
        (set(), '{}'),
    ],
)
def test_topython_basic(obj: object, expected: str) -> None:
    assert topython(obj) == expected


@pytest.mark.parametrize(
    ('obj', 'expected'),
    [
        ([1, 2, 3], '(1, 2, 3)'),
        ([], '()'),
        ([1], '(1,)'),
        ((1, 2), '(1, 2)'),
        ((1,), '(1,)'),
    ],
)
def test_topython_list_to_tuple(obj: object, expected: str) -> None:
    assert topython(obj, list_to_tuple=True) == expected


@pytest.mark.parametrize(
    ('obj', 'expected'),
    [
        ('true', "'true'"),
        ('false', "'false'"),
        ('123', "'123'"),
    ],
)
def test_topython_convert_strings_false(obj: object, expected: str) -> None:
    assert topython(obj, convert_strings=False) == expected


def test_topython_mapping_with_special_chars() -> None:
    obj = {"a'b": 1, 'c\\d': 2}
    result = topython(obj)
    assert result == "{'a\\'b': 1, 'c\\\\d': 2}"


def test_topython_iterable_non_list() -> None:
    class CustomIterable:
        def __iter__(self) -> Iterator[int]:
            yield 1
            yield 2

    result = topython(CustomIterable())
    assert result == '[1, 2]'


def test_topython_returns_obj_for_unknown_type() -> None:
    class Dummy:
        pass

    dummy = Dummy()
    assert topython(dummy) is dummy


def test_topython_set_sorted_output() -> None:
    obj = {'b', 'a'}
    result = topython(obj)
    assert result == "{'a', 'b'}"


def test_topython_tuple_empty() -> None:
    assert topython(()) == '()'


def test_topython_tuple_single() -> None:
    assert topython((1,)) == '(1,)'


def test_topython_tuple_multi() -> None:
    assert topython((1, 2)) == '(1, 2)'


def test_topython_nested_structures() -> None:
    obj = {'a': [1, (2, 3), {'b': 'true'}]}
    result = topython(obj)
    assert result == "{'a': [1, (2, 3), {'b': True}]}"


def test_topython_extension_registers_filter(mocker: MockerFixture) -> None:
    env = mocker.MagicMock(filters={})
    ToPythonExtension(env)
    assert 'topython' in env.filters
    assert env.filters['topython'] is topython


def test_topython_iterable_list_to_tuple_empty() -> None:
    class CustomIterable:
        def __iter__(self) -> Iterator[int]:
            return iter([])

    result = topython(CustomIterable(), list_to_tuple=True)
    assert result == '()'


def test_topython_iterable_list_to_tuple_single() -> None:
    class CustomIterable:
        def __iter__(self) -> Iterator[int]:
            yield 1

    result = topython(CustomIterable(), list_to_tuple=True)
    assert result == '(1,)'


def test_topython_iterable_list_to_tuple_multi() -> None:
    class CustomIterable:
        def __iter__(self) -> Iterator[int]:
            yield 1
            yield 2

    result = topython(CustomIterable(), list_to_tuple=True)
    assert result == '(1, 2)'


def test_shell_indent_basic() -> None:
    env = jinja2.Environment(extensions=[ShellExtension], autoescape=True)
    indent = env.filters['shell_indent']
    result = indent('echo hello\necho world')
    assert result == '    echo hello\n    echo world'


def test_shell_indent_preserves_empty_lines() -> None:
    env = jinja2.Environment(extensions=[ShellExtension], autoescape=True)
    indent = env.filters['shell_indent']
    result = indent('echo hello\n\necho world')
    assert result == '    echo hello\n\n    echo world'


def test_shell_indent_heredoc_not_indented() -> None:
    env = jinja2.Environment(extensions=[ShellExtension], autoescape=True)
    indent = env.filters['shell_indent']
    result = indent('cat <<EOF\nhello\nworld\nEOF\necho done')
    assert result == '    cat <<EOF\nhello\nworld\nEOF\n    echo done'


def test_shell_indent_custom_width() -> None:
    env = jinja2.Environment(extensions=[ShellExtension], autoescape=True)
    indent = env.filters['shell_indent']
    result = indent('echo hello', 2)
    assert result == '  echo hello'


def test_shell_indent_heredoc_with_quotes() -> None:
    env = jinja2.Environment(extensions=[ShellExtension], autoescape=True)
    indent = env.filters['shell_indent']
    result = indent("cat <<'EOF'\nhello\nEOF\necho done")
    assert result == "    cat <<'EOF'\nhello\nEOF\n    echo done"


def test_github_api_extension_registers_global(mocker: MockerFixture) -> None:
    from wiswa.extensions import GithubAPIExtension

    env = jinja2.Environment(extensions=[GithubAPIExtension], autoescape=True)
    assert 'github_latest_action_tag' in env.globals


def test_parse_md_badge_valid() -> None:
    from wiswa.extensions import ParseMarkdownBadgeExtension

    env = jinja2.Environment(extensions=[ParseMarkdownBadgeExtension], autoescape=True)
    parse_badge = env.filters['parse_md_badge']
    result = parse_badge('[![alt text](https://img.shields.io/badge.svg)]')
    assert result == {'alt': 'alt text', 'image': 'https://img.shields.io/badge.svg'}


def test_parse_md_badge_no_match() -> None:
    from wiswa.extensions import ParseMarkdownBadgeExtension

    env = jinja2.Environment(extensions=[ParseMarkdownBadgeExtension], autoescape=True)
    parse_badge = env.filters['parse_md_badge']
    result = parse_badge('not a badge')
    assert result == {'alt': '', 'image': ''}


async def test_github_latest_action_tag_no_session() -> None:
    from typing import Any, cast

    from wiswa.extensions import GithubAPIExtension

    env = jinja2.Environment(extensions=[GithubAPIExtension], autoescape=True)
    func = cast('Any', env.globals['github_latest_action_tag'])
    with pytest.raises(RuntimeError, match='No HTTP session'):
        await func('owner', 'repo')


async def test_github_latest_action_tag_with_session(mocker: MockerFixture) -> None:
    from typing import Any, cast
    from unittest.mock import AsyncMock

    from wiswa.extensions import GithubAPIExtension

    mocker.patch('wiswa.utils.versions.get_github_release_latest_tag',
                 new_callable=AsyncMock,
                 return_value='v4')
    env = jinja2.Environment(extensions=[GithubAPIExtension], autoescape=True)
    mock_session = mocker.MagicMock()
    env.globals['_http_session'] = mock_session
    func = cast('Any', env.globals['github_latest_action_tag'])
    result = await func('owner', 'repo')
    assert result == 'v4'
