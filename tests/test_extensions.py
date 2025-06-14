from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from wiswa.extensions import ToPythonExtension, topython
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
